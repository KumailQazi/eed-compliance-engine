# EED Article 26 Compliance Report

**Reporting Entity:** {{ entity }}  
**Facility ID:** {{ facility_id }}  
**Reporting Period:** {{ start_date }} to {{ end_date }}  
**Generated:** {{ generated_at }}  
**Audit Record:** `{{ record_id }}`

---

## Executive Summary

This report presents the EED Article 26 sustainability metrics for the specified facility and reporting period. All calculations are deterministic, reproducible, and logged to an immutable audit trail.

| Metric | Value | Unit | Notes |
|--------|-------|------|-------|
| PUE | {{ pue }} | — | Power Usage Effectiveness |
| ERF | {{ erf }} | — | Energy Reuse Factor |
| ERE | {{ ere }} | — | Energy Reuse Effectiveness |
{% if wue %}| WUE | {{ wue }} | L/kWh | Water Usage Effectiveness |{% endif %}
{% if cue %}| CUE | {{ cue }} | kg CO₂/kWh | Carbon Usage Effectiveness |{% endif %}
{% if recovered_thermal_power_kw %}| Recovered Thermal Power | {{ recovered_thermal_power_kw }} | kW | From liquid cooling loop |{% endif %}
{% if annual_recovered_energy_kwh %}| Annual Recovered Energy | {{ annual_recovered_energy_kwh }} | kWh | Assumes continuous operation |{% endif %}

---

## Methodology

### PUE (Power Usage Effectiveness)

$$\text{PUE} = \frac{\text{Total Facility Energy}}{\text{IT Equipment Energy}}$$

Reference: ISO/IEC 30134-2:2016

### ERF (Energy Reuse Factor)

$$\text{ERF} = \frac{\text{Reused Energy}}{\text{Total Facility Energy}}$$

Reused energy is energy recovered and used *outside* the data-center boundary (e.g., district heating, industrial process heat).

Reference: ISO/IEC 30134-3:2016

### ERE (Energy Reuse Effectiveness)

$$\text{ERE} = (1 - \text{ERF}) \times \text{PUE}$$

Interpretation:
  - ERE < PUE: heat reuse is improving overall efficiency
  - ERE = PUE: no heat reuse (ERF = 0)

### WUE (Water Usage Effectiveness)

$$\text{WUE} = \frac{\text{Annual Water Usage (L)}}{\text{IT Equipment Energy (kWh)}}$$

Reference: ISO/IEC 30134-9

### CUE (Carbon Usage Effectiveness)

$$\text{CUE} = \frac{\text{Total CO}_2 \text{ Emissions (kg)}}{\text{IT Equipment Energy (kWh)}}$$

Total emissions = (grid energy × grid carbon intensity) − renewable offset.

Reference: ISO/IEC 30134-4

### Recovered Thermal Power

$$Q = \dot{m} \times c_p \times \Delta T$$

Where:
  - $\dot{m}$ = mass flow rate (kg/h) = density × volumetric flow
  - $c_p$ = specific heat capacity (kJ/kg·K)
  - $\Delta T$ = outlet temperature − inlet temperature (K)

---

## Assumptions & Limitations

1. All energy values are reported in kWh for the specified period.
2. Cooling telemetry assumes continuous operation unless otherwise specified.
3. Grid carbon intensity is treated as constant over the reporting period.
4. This report is generated from deterministic calculations with no LLM inference or stochastic components.

---

## Audit Trail

This calculation is recorded in the immutable audit log with record ID `{{ record_id }}`. The log entry includes the full input telemetry, formula version, timestamp, and all outputs for reproducibility and regulatory inspection.
