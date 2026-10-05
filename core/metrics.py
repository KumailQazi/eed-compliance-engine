"""Deterministic EED Article 26 metric calculator.

All calculations are pure functions with no side effects and no non-deterministic
components (no LLM inference, no stochastic sampling, no external API calls).
This guarantees auditability: the same inputs always produce the same outputs.

References:
  - EU Energy Efficiency Directive (EED) 2023/1791, Article 26
  - ISO/IEC 30134-2:2016 (PUE)
  - ISO/IEC 30134-3:2016 (ERF)
  - The Green Grid: ERE = (1 − ERF) × PUE
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from .validators import TelemetryBundle, EnergyMeters, CoolingTelemetry, WaterUsage, CarbonIntensity
from .exceptions import CalculationError, ValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LITRES_TO_CUBIC_METRES = Decimal("0.001")   # 1 L = 0.001 m³
SPECIFIC_HEAT_WATER_KJ_M3_K = Decimal("4180")  # ~4.18 MJ/m³·K (water)
HOURS_PER_YEAR = Decimal("8760")


def _to_decimal(value: Optional[float]) -> Decimal:
    """Convert float to Decimal with exact representation."""
    if value is None:
        raise CalculationError("Required numeric field is None.")
    return Decimal(str(value))


def _round_metric(value: Decimal, precision: str = "1.000") -> Decimal:
    """Round to a fixed decimal precision for reporting consistency."""
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Core EED Article 26 Metrics
# ---------------------------------------------------------------------------

def calculate_pue(energy: EnergyMeters) -> Decimal:
    """Power Usage Effectiveness (PUE).

    PUE = Total Facility Energy / IT Equipment Energy

    Typical efficient facilities: 1.20 – 1.40
    d.i.t. claim: ~1.1 (requires measured evidence)
    """
    total = _to_decimal(energy.total_facility_energy_kwh)
    it = _to_decimal(energy.it_equipment_energy_kwh)

    if it == 0:
        raise CalculationError("IT equipment energy is zero; PUE is undefined.")

    pue = total / it
    return _round_metric(pue, "1.000")


def calculate_erf(energy: EnergyMeters) -> Decimal:
    """Energy Reuse Factor (ERF).

    ERF = Reused Energy / Total Facility Energy

    Reused energy is energy recovered and used *outside* the data-center
    boundary (e.g., district heating, industrial process heat).

    Germany EnEfG mandates:
      - 10 % from July 2026
      - 15 % from 2027
      - 20 % from 2028
    """
    if energy.reused_energy_kwh is None:
        raise CalculationError(
            "reused_energy_kwh is required for ERF. "
            "If no heat is reused, explicitly set to 0."
        )

    total = _to_decimal(energy.total_facility_energy_kwh)
    reused = _to_decimal(energy.reused_energy_kwh)

    if reused < 0:
        raise CalculationError("Reused energy cannot be negative.")
    if reused > total:
        raise ValidationError(
            f"Reused energy ({reused}) cannot exceed total facility energy ({total})."
        )

    erf = reused / total
    return _round_metric(erf, "1.0000")


def calculate_ere(energy: EnergyMeters) -> Decimal:
    """Energy Reuse Effectiveness (ERE).

    ERE = (1 − ERF) × PUE

    Interpretation:
      - ERE < PUE  → heat reuse is improving overall efficiency
      - ERE = PUE  → no heat reuse (ERF = 0)
      - ERE > PUE  → should not occur with valid inputs
    """
    pue = calculate_pue(energy)
    erf = calculate_erf(energy)

    ere = (Decimal("1") - erf) * pue
    return _round_metric(ere, "1.0000")


def calculate_wue(energy: EnergyMeters, water: WaterUsage) -> Decimal:
    """Water Usage Effectiveness (WUE).

    WUE = Annual Water Usage (L) / IT Equipment Energy (kWh)

    Units: L/kWh  (reported as L/kWh or converted to m³/MWh for EED database)
    """
    annual_water = _to_decimal(water.annual_water_usage_litres)
    it = _to_decimal(energy.it_equipment_energy_kwh)

    if it == 0:
        raise CalculationError("IT equipment energy is zero; WUE is undefined.")

    wue = annual_water / it
    return _round_metric(wue, "1.0000")


def calculate_cue(energy: EnergyMeters, carbon: CarbonIntensity) -> Decimal:
    """Carbon Usage Effectiveness (CUE).

    CUE = Total CO₂ Emissions (kg) / IT Equipment Energy (kWh)

    Total emissions = (grid_energy × grid_carbon_intensity) − renewable_offset

    Note: On-site renewable generation reduces grid-drawn energy.
    """
    total = _to_decimal(energy.total_facility_energy_kwh)
    it = _to_decimal(energy.it_equipment_energy_kwh)
    grid_ci = _to_decimal(carbon.grid_carbon_intensity_g_co2_kwh)
    renewable_frac = _to_decimal(carbon.on_site_renewable_fraction)

    if it == 0:
        raise CalculationError("IT equipment energy is zero; CUE is undefined.")
    if not (0 <= renewable_frac <= 1):
        raise ValidationError("Renewable fraction must be between 0 and 1.")

    # Effective grid-drawn energy after on-site renewable offset
    grid_energy = total * (Decimal("1") - renewable_frac)

    # CO₂ in grams, then convert to kg
    total_co2_g = grid_energy * grid_ci
    total_co2_kg = total_co2_g / Decimal("1000")

    cue = total_co2_kg / it
    return _round_metric(cue, "1.0000")


# ---------------------------------------------------------------------------
# Waste-Heat Recovery Physics (ORC / Liquid Cooling)
# ---------------------------------------------------------------------------

def calculate_recovered_thermal_power(cooling: CoolingTelemetry) -> Decimal:
    """Recoverable thermal power from liquid-cooling loop (kW).

    Q = ṁ × cp × ΔT

    Where:
      - ṁ = ρ × V̇   (mass flow rate, kg/h)
      - cp = specific heat (kJ/kg·K)
      - ΔT = outlet − inlet (K or °C, same delta)

    Returns power in kW (kJ/s).
    """
    flow_lph = _to_decimal(cooling.flow_rate_lph)
    rho = _to_decimal(cooling.coolant_density_kg_l)
    cp = _to_decimal(cooling.coolant_specific_heat_kj_kg_k)
    dt = _to_decimal(cooling.outlet_temp_c - cooling.inlet_temp_c)

    if dt <= 0:
        raise CalculationError(
            "Temperature delta must be positive for heat recovery. "
            f"Got inlet={cooling.inlet_temp_c}, outlet={cooling.outlet_temp_c}"
        )

    # mass flow (kg/h) = L/h × kg/L
    mass_flow_kg_h = flow_lph * rho

    # Thermal power (kJ/h) = kg/h × kJ/kg·K × K
    thermal_power_kj_h = mass_flow_kg_h * cp * dt

    # Convert to kW (kJ/s): divide by 3600 s/h
    thermal_power_kw = thermal_power_kj_h / Decimal("3600")

    return _round_metric(thermal_power_kw, "1.000")


def calculate_annual_recovered_energy(cooling: CoolingTelemetry, uptime_hours: float = 8760.0) -> Decimal:
    """Annual recovered energy (kWh) assuming continuous operation.

    For intermittent operation, pass actual uptime_hours < 8760.
    """
    power_kw = calculate_recovered_thermal_power(cooling)
    hours = _to_decimal(uptime_hours)

    if hours < 0 or hours > HOURS_PER_YEAR:
        raise ValidationError(f"uptime_hours ({uptime_hours}) must be between 0 and 8760.")

    energy_kwh = power_kw * hours
    return _round_metric(energy_kwh, "1.000")


# ---------------------------------------------------------------------------
# Composite Report (all metrics in one deterministic call)
# ---------------------------------------------------------------------------

def generate_compliance_metrics(bundle: TelemetryBundle) -> Dict[str, Optional[Decimal]]:
    """Compute the full EED Article 26 metric set from a telemetry bundle.

    Returns a dictionary with guaranteed keys:
      - pue
      - erf
      - ere
      - wue  (None if water telemetry missing)
      - cue  (None if carbon telemetry missing)
      - recovered_thermal_power_kw  (None if cooling telemetry missing)
      - annual_recovered_energy_kwh (None if cooling telemetry missing)

    Every successful call is guaranteed to be reproducible from the same inputs.
    """
    result: Dict[str, Optional[Decimal]] = {}

    # Mandatory metrics (EED Art. 26 baseline)
    result["pue"] = calculate_pue(bundle.energy)
    result["erf"] = calculate_erf(bundle.energy)
    result["ere"] = calculate_ere(bundle.energy)

    # Optional metrics (reported if telemetry available)
    if bundle.water:
        result["wue"] = calculate_wue(bundle.energy, bundle.water)
    else:
        result["wue"] = None

    if bundle.carbon:
        result["cue"] = calculate_cue(bundle.energy, bundle.carbon)
    else:
        result["cue"] = None

    if bundle.cooling:
        result["recovered_thermal_power_kw"] = calculate_recovered_thermal_power(bundle.cooling)
        result["annual_recovered_energy_kwh"] = calculate_annual_recovered_energy(bundle.cooling)
    else:
        result["recovered_thermal_power_kw"] = None
        result["annual_recovered_energy_kwh"] = None

    return result
