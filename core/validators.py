"""Pydantic schemas for data-center telemetry and boundary definitions.

All physical quantities use SI units internally:
  - Energy: kWh
  - Power: kW
  - Temperature: Celsius (delta calculations handle conversion internally)
  - Volume: litres (L); volumetric flow: L/h
  - Time: hours
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from .exceptions import ValidationError


class EnergyMeters(BaseModel):
    """Raw energy readings from the facility boundary."""
    it_equipment_energy_kwh: float = Field(..., ge=0, description="IT load energy over the period")
    total_facility_energy_kwh: float = Field(..., ge=0, description="Total facility energy (IT + cooling + aux)")
    cooling_energy_kwh: Optional[float] = Field(default=None, ge=0, description="Cooling-system energy consumption")
    reused_energy_kwh: Optional[float] = Field(default=None, ge=0, description="Energy reused outside the boundary")
    renewable_energy_kwh: Optional[float] = Field(default=None, ge=0, description="On-site renewable energy generated")

    @model_validator(mode="after")
    def check_it_not_exceeds_total(self):
        if self.it_equipment_energy_kwh > self.total_facility_energy_kwh:
            raise ValidationError(
                f"it_equipment_energy ({self.it_equipment_energy_kwh}) cannot exceed "
                f"total_facility_energy ({self.total_facility_energy_kwh})"
            )
        return self


class CoolingTelemetry(BaseModel):
    """Liquid-cooling telemetry for waste-heat recovery calculations."""
    inlet_temp_c: float = Field(..., ge=-40, le=120, description="Coolant inlet temperature (°C)")
    outlet_temp_c: float = Field(..., ge=-40, le=120, description="Coolant outlet temperature (°C)")
    flow_rate_lph: float = Field(..., ge=0, description="Volumetric flow rate (L/h)")
    coolant_specific_heat_kj_kg_k: float = Field(default=4.18, ge=0.5, le=10, description="Specific heat capacity (kJ/kg·K)")
    coolant_density_kg_l: float = Field(default=1.0, ge=0.5, le=10, description="Coolant density (kg/L)")

    @model_validator(mode="after")
    def check_outlet_above_inlet(self):
        if self.outlet_temp_c <= self.inlet_temp_c:
            raise ValidationError(
                f"outlet_temp_c ({self.outlet_temp_c}) must be greater than "
                f"inlet_temp_c ({self.inlet_temp_c}) for heat recovery."
            )
        return self


class WaterUsage(BaseModel):
    """Water-consumption telemetry for WUE calculation."""
    annual_water_usage_litres: float = Field(..., ge=0, description="Total annual water consumption (L)")


class CarbonIntensity(BaseModel):
    """Grid and on-site carbon intensity factors."""
    grid_carbon_intensity_g_co2_kwh: float = Field(..., ge=0, description="Grid carbon intensity (g CO₂/kWh)")
    on_site_renewable_fraction: float = Field(..., ge=0, le=1, description="Fraction of energy from on-site renewables")


class ReportingPeriod(BaseModel):
    """Temporal bounds for a compliance report."""
    start: datetime
    end: datetime
    reporting_entity: str = Field(..., min_length=1, description="Legal entity name (KvK-registered)")
    facility_id: str = Field(..., min_length=1, description="Unique facility identifier")

    @model_validator(mode="after")
    def check_chronology(self):
        if self.end <= self.start:
            raise ValidationError("Reporting period end must be after start.")
        return self


class TelemetryBundle(BaseModel):
    """Top-level input container for a single reporting period."""
    period: ReportingPeriod
    energy: EnergyMeters
    cooling: Optional[CoolingTelemetry] = None
    water: Optional[WaterUsage] = None
    carbon: Optional[CarbonIntensity] = None
