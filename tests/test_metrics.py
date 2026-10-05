"""pytest suite for EED compliance metric calculations.

All tests use exact Decimal comparisons to guarantee deterministic behaviour.
"""
import pytest
from decimal import Decimal
from core.metrics import (
    calculate_pue,
    calculate_erf,
    calculate_ere,
    calculate_wue,
    calculate_cue,
    calculate_recovered_thermal_power,
    calculate_annual_recovered_energy,
    generate_compliance_metrics,
)
from core.validators import EnergyMeters, CoolingTelemetry, WaterUsage, CarbonIntensity, ReportingPeriod, TelemetryBundle
from core.exceptions import CalculationError, ValidationError
from datetime import datetime


# ---------------------------------------------------------------------------
# PUE
# ---------------------------------------------------------------------------
class TestPUE:
    def test_typical_efficient_facility(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1250.0,
            reused_energy_kwh=0.0,
        )
        assert calculate_pue(e) == Decimal("1.250")

    def test_dit_claim_level(self):
        """d.i.t. claims PUE ~1.1. Verify the math."""
        e = EnergyMeters(
            it_equipment_energy_kwh=10000.0,
            total_facility_energy_kwh=11000.0,
            reused_energy_kwh=500.0,
        )
        assert calculate_pue(e) == Decimal("1.100")

    def test_it_zero_raises(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=0.0,
            total_facility_energy_kwh=100.0,
            reused_energy_kwh=0.0,
        )
        with pytest.raises(CalculationError, match="IT equipment energy is zero"):
            calculate_pue(e)

    def test_it_exceeds_total_raises(self):
        with pytest.raises(ValidationError):
            EnergyMeters(
                it_equipment_energy_kwh=2000.0,
                total_facility_energy_kwh=1000.0,
                reused_energy_kwh=0.0,
            )


# ---------------------------------------------------------------------------
# ERF
# ---------------------------------------------------------------------------
class TestERF:
    def test_no_reuse(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1200.0,
            reused_energy_kwh=0.0,
        )
        assert calculate_erf(e) == Decimal("0.0000")

    def test_german_enefg_2026_threshold(self):
        """10% ERF = Germany EnEfG minimum from July 2026."""
        e = EnergyMeters(
            it_equipment_energy_kwh=9000.0,
            total_facility_energy_kwh=10000.0,
            reused_energy_kwh=1000.0,
        )
        assert calculate_erf(e) == Decimal("0.1000")

    def test_german_enefg_2028_threshold(self):
        """20% ERF = Germany EnEfG minimum from 2028."""
        e = EnergyMeters(
            it_equipment_energy_kwh=8000.0,
            total_facility_energy_kwh=10000.0,
            reused_energy_kwh=2000.0,
        )
        assert calculate_erf(e) == Decimal("0.2000")

    def test_reuse_exceeds_total_raises(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1200.0,
            reused_energy_kwh=1300.0,
        )
        with pytest.raises(ValidationError, match="cannot exceed total facility energy"):
            calculate_erf(e)

    def test_none_reused_raises(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1200.0,
            reused_energy_kwh=None,
        )
        with pytest.raises(CalculationError, match="reused_energy_kwh is required"):
            calculate_erf(e)


# ---------------------------------------------------------------------------
# ERE
# ---------------------------------------------------------------------------
class TestERE:
    def test_no_reuse_ere_equals_pue(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1250.0,
            reused_energy_kwh=0.0,
        )
        assert calculate_ere(e) == Decimal("1.2500")

    def test_heat_reuse_improves_ere(self):
        """ERE < PUE when ERF > 0."""
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1250.0,
            reused_energy_kwh=250.0,
        )
        ere = calculate_ere(e)
        pue = calculate_pue(e)
        assert ere < pue
        assert ere == Decimal("1.0000")  # (1 - 250/1250) * (1250/1000) = 0.8 * 1.25 = 1.0000


# ---------------------------------------------------------------------------
# WUE
# ---------------------------------------------------------------------------
class TestWUE:
    def test_typical(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=10000.0,
            total_facility_energy_kwh=12000.0,
            reused_energy_kwh=0.0,
        )
        w = WaterUsage(annual_water_usage_litres=500_000.0)
        assert calculate_wue(e, w) == Decimal("50.0000")


# ---------------------------------------------------------------------------
# CUE
# ---------------------------------------------------------------------------
class TestCUE:
    def test_fully_grid_powered(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1200.0,
            reused_energy_kwh=0.0,
        )
        c = CarbonIntensity(
            grid_carbon_intensity_g_co2_kwh=350.0,
            on_site_renewable_fraction=0.0,
        )
        # 1200 kWh * 350 g/kWh = 420,000 g = 420 kg / 1000 kWh = 0.42 kg/kWh
        assert calculate_cue(e, c) == Decimal("0.4200")

    def test_half_renewable(self):
        e = EnergyMeters(
            it_equipment_energy_kwh=1000.0,
            total_facility_energy_kwh=1200.0,
            reused_energy_kwh=0.0,
        )
        c = CarbonIntensity(
            grid_carbon_intensity_g_co2_kwh=350.0,
            on_site_renewable_fraction=0.5,
        )
        # 600 kWh grid * 350 g = 210,000 g = 210 kg / 1000 = 0.21
        assert calculate_cue(e, c) == Decimal("0.2100")


# ---------------------------------------------------------------------------
# Recovered Thermal Power
# ---------------------------------------------------------------------------
class TestRecoveredThermalPower:
    def test_water_loop_10k_delta(self):
        """10 K delta, 1000 L/h water flow."""
        c = CoolingTelemetry(
            inlet_temp_c=40.0,
            outlet_temp_c=50.0,
            flow_rate_lph=1000.0,
            coolant_specific_heat_kj_kg_k=4.18,
            coolant_density_kg_l=1.0,
        )
        # ṁ = 1000 kg/h; Q = 1000 * 4.18 * 10 = 41,800 kJ/h = 11.611... kW
        power = calculate_recovered_thermal_power(c)
        assert power == Decimal("11.611")

    def test_negative_delta_raises(self):
        # Schema validation catches it at boundary
        with pytest.raises(ValidationError, match="must be greater than"):
            CoolingTelemetry(
                inlet_temp_c=50.0,
                outlet_temp_c=40.0,
                flow_rate_lph=1000.0,
            )
        # Direct function check defends if schema validation was bypassed
        c = CoolingTelemetry.model_construct(
            inlet_temp_c=50.0,
            outlet_temp_c=40.0,
            flow_rate_lph=1000.0,
            coolant_specific_heat_kj_kg_k=4.18,
            coolant_density_kg_l=1.0,
        )
        with pytest.raises(CalculationError, match="Temperature delta must be positive"):
            calculate_recovered_thermal_power(c)

    def test_equal_temp_raises(self):
        # Schema validation catches it at boundary
        with pytest.raises(ValidationError, match="must be greater than"):
            CoolingTelemetry(
                inlet_temp_c=45.0,
                outlet_temp_c=45.0,
                flow_rate_lph=1000.0,
            )
        # Direct function check defends if schema validation was bypassed
        c = CoolingTelemetry.model_construct(
            inlet_temp_c=45.0,
            outlet_temp_c=45.0,
            flow_rate_lph=1000.0,
            coolant_specific_heat_kj_kg_k=4.18,
            coolant_density_kg_l=1.0,
        )
        with pytest.raises(CalculationError, match="Temperature delta must be positive"):
            calculate_recovered_thermal_power(c)


# ---------------------------------------------------------------------------
# Annual Recovered Energy
# ---------------------------------------------------------------------------
class TestAnnualRecoveredEnergy:
    def test_full_year_continuous(self):
        c = CoolingTelemetry(
            inlet_temp_c=40.0,
            outlet_temp_c=50.0,
            flow_rate_lph=1000.0,
        )
        energy = calculate_annual_recovered_energy(c, uptime_hours=8760.0)
        # 11.611 kW * 8760 h = 101,712.36 kWh
        assert energy == Decimal("101712.360")

    def test_partial_year(self):
        c = CoolingTelemetry(
            inlet_temp_c=40.0,
            outlet_temp_c=50.0,
            flow_rate_lph=1000.0,
        )
        energy = calculate_annual_recovered_energy(c, uptime_hours=4380.0)
        assert energy == Decimal("50856.180")


# ---------------------------------------------------------------------------
# Integration: Full Bundle
# ---------------------------------------------------------------------------
class TestComplianceBundle:
    def test_full_bundle(self):
        bundle = TelemetryBundle(
            period=ReportingPeriod(
                start=datetime(2026, 1, 1),
                end=datetime(2026, 12, 31),
                reporting_entity="d.i.t. B.V.",
                facility_id="AMS-HVN-01",
            ),
            energy=EnergyMeters(
                it_equipment_energy_kwh=10_000_000.0,
                total_facility_energy_kwh=11_000_000.0,
                reused_energy_kwh=1_500_000.0,
            ),
            cooling=CoolingTelemetry(
                inlet_temp_c=45.0,
                outlet_temp_c=60.0,
                flow_rate_lph=50_000.0,
            ),
            water=WaterUsage(annual_water_usage_litres=20_000_000.0),
            carbon=CarbonIntensity(
                grid_carbon_intensity_g_co2_kwh=236.0,
                on_site_renewable_fraction=0.40,
            ),
        )

        result = generate_compliance_metrics(bundle)

        assert result["pue"] == Decimal("1.100")
        assert result["erf"] == Decimal("0.1364")
        assert result["ere"] == Decimal("0.9500")
        assert result["wue"] == Decimal("2.0000")
        assert result["cue"] == Decimal("0.1558")
        assert result["recovered_thermal_power_kw"] == Decimal("870.833")
        assert result["annual_recovered_energy_kwh"] is not None
