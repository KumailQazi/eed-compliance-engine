"""Streamlit dashboard for EED compliance metric exploration.

Upload a telemetry CSV, compute metrics, and download an investor-grade report.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from decimal import Decimal

from core.validators import (
    TelemetryBundle,
    ReportingPeriod,
    EnergyMeters,
    CoolingTelemetry,
    WaterUsage,
    CarbonIntensity,
)
from core.metrics import generate_compliance_metrics
from audit.logger import log_calculation
from report.generator import generate_report

st.set_page_config(page_title="EED Compliance Engine", layout="wide")

st.title("EED Article 26 Compliance Engine")
st.markdown("Deterministic metric calculator for data-center sustainability reporting.")

with st.sidebar:
    st.header("Reporting Period")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start", value=datetime(2026, 1, 1).date())
    with col2:
        end_date = st.date_input("End", value=datetime(2026, 12, 31).date())
    entity = st.text_input("Reporting Entity", value="d.i.t. B.V.")
    facility_id = st.text_input("Facility ID", value="AMS-HVN-01")

st.header("Energy Meters")
col1, col2, col3 = st.columns(3)
with col1:
    it_energy = st.number_input("IT Energy (kWh)", min_value=0.0, value=10_000_000.0, step=100_000.0)
with col2:
    total_energy = st.number_input("Total Facility Energy (kWh)", min_value=0.0, value=11_000_000.0, step=100_000.0)
with col3:
    reused_energy = st.number_input("Reused Energy (kWh)", min_value=0.0, value=1_500_000.0, step=100_000.0)

st.header("Liquid Cooling Telemetry (Optional)")
col1, col2, col3 = st.columns(3)
with col1:
    inlet_temp = st.number_input("Inlet Temp (°C)", value=45.0)
with col2:
    outlet_temp = st.number_input("Outlet Temp (°C)", value=60.0)
with col3:
    flow_rate = st.number_input("Flow Rate (L/h)", min_value=0.0, value=50_000.0, step=1_000.0)

st.header("Water & Carbon (Optional)")
col1, col2 = st.columns(2)
with col1:
    annual_water = st.number_input("Annual Water Usage (L)", min_value=0.0, value=20_000_000.0, step=100_000.0)
with col2:
    grid_ci = st.number_input("Grid Carbon Intensity (g CO₂/kWh)", min_value=0.0, value=236.0)
    renewable_frac = st.slider("On-site Renewable Fraction", 0.0, 1.0, 0.40)

if st.button("Calculate Metrics", type="primary"):
    try:
        bundle = TelemetryBundle(
            period=ReportingPeriod(
                start=datetime.combine(start_date, datetime.min.time()),
                end=datetime.combine(end_date, datetime.min.time()),
                reporting_entity=entity,
                facility_id=facility_id,
            ),
            energy=EnergyMeters(
                it_equipment_energy_kwh=it_energy,
                total_facility_energy_kwh=total_energy,
                reused_energy_kwh=reused_energy,
            ),
            cooling=CoolingTelemetry(
                inlet_temp_c=inlet_temp,
                outlet_temp_c=outlet_temp,
                flow_rate_lph=flow_rate,
            ) if flow_rate > 0 else None,
            water=WaterUsage(annual_water_usage_litres=annual_water) if annual_water > 0 else None,
            carbon=CarbonIntensity(
                grid_carbon_intensity_g_co2_kwh=grid_ci,
                on_site_renewable_fraction=renewable_frac,
            ) if grid_ci > 0 else None,
        )

        result = generate_compliance_metrics(bundle)
        record_id = log_calculation(bundle, result, caller="streamlit-dashboard")

        st.success(f"Metrics computed. Audit record: `{record_id[:16]}...`")

        col1, col2, col3, col4 = st.columns(4)
        metrics_display = [
            ("PUE", result.get("pue")),
            ("ERF", result.get("erf")),
            ("ERE", result.get("ere")),
            ("WUE (L/kWh)", result.get("wue")),
        ]
        for col, (label, value) in zip([col1, col2, col3, col4], metrics_display):
            if value is not None:
                col.metric(label, f"{float(value):.4f}")

        if result.get("recovered_thermal_power_kw"):
            st.metric("Recovered Thermal Power", f"{float(result['recovered_thermal_power_kw']):.3f} kW")
        if result.get("annual_recovered_energy_kwh"):
            st.metric("Annual Recovered Energy", f"{float(result['annual_recovered_energy_kwh']):,.0f} kWh")

        report_md = generate_report(bundle, result, record_id)
        st.download_button(
            label="Download Report (Markdown)",
            data=report_md,
            file_name=f"{facility_id}_compliance_report.md",
            mime="text/markdown",
        )

    except Exception as exc:
        st.error(f"Calculation failed: {exc}")
