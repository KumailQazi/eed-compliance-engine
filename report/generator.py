"""Report generator: Jinja2 → Markdown / HTML.

Produces investor-grade compliance reports from computed metrics and telemetry.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.validators import TelemetryBundle


TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report(
    bundle: TelemetryBundle,
    metrics: Dict[str, Any],
    record_id: str,
    template_name: str = "compliance_report.md",
) -> str:
    """Render a compliance report from a Jinja2 template.

    Returns the rendered Markdown string.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(),
    )
    template = env.get_template(template_name)

    context = {
        "entity": bundle.period.reporting_entity,
        "facility_id": bundle.period.facility_id,
        "start_date": bundle.period.start.strftime("%Y-%m-%d"),
        "end_date": bundle.period.end.strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "record_id": record_id,
        "pue": metrics.get("pue"),
        "erf": metrics.get("erf"),
        "ere": metrics.get("ere"),
        "wue": metrics.get("wue"),
        "cue": metrics.get("cue"),
        "recovered_thermal_power_kw": metrics.get("recovered_thermal_power_kw"),
        "annual_recovered_energy_kwh": metrics.get("annual_recovered_energy_kwh"),
    }

    return template.render(context)
