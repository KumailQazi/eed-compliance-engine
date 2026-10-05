# eed-compliance-engine

Deterministic EED Article 26 compliance calculator for data-center sustainability metrics — PUE, ERF, WUE, CUE with immutable audit trails. No LLMs. No black boxes.

## Why deterministic?

Compliance metrics like PUE and ERF are arithmetic, not inference. An LLM can describe what PUE means; it cannot guarantee that the same inputs always produce the same output, reproducibly, to a decimal place that satisfies an auditor. This engine treats that guarantee as the core feature, not an afterthought.

Every calculation is a pure function with no side effects, no external API calls, no stochastic sampling, and no LLM inference. The same inputs always produce the same outputs.

## Metrics supported

| Metric | Formula | EED / Standard Reference |
|--------|---------|--------------------------|
| PUE | Total Facility Energy / IT Equipment Energy | ISO/IEC 30134-2:2016 |
| ERF | Reused Energy / Total Facility Energy | ISO/IEC 30134-3:2016 |
| ERE | (1 − ERF) × PUE | The Green Grid |
| WUE | Annual Water Usage (L) / IT Energy (kWh) | ISO/IEC 30134-9 |
| CUE | Total CO₂ Emissions (kg) / IT Energy (kWh) | ISO/IEC 30134-4 |
| Recovered Thermal Power | Q = ṁ·cp·ΔT | First-principles physics |

## Quick start

```bash
pip install -r requirements.txt
pytest tests/test_metrics.py -v
streamlit run app/dashboard.py
```

## Architecture

```
Telemetry (CSV / API / Sensors)
    |
    v
[ ingest / normalizer ]  →  Schema validation (Pydantic)
    |
    v
[ core / metrics ]       →  Deterministic calculation (Decimal)
    |
    v
[ audit / logger ]       →  Immutable append-only JSONL trail
    |
    v
[ report / generator ]   →  Jinja2 → Markdown / HTML
```

## Sample output

See `data/sample_telemetry.csv` for mock data-center telemetry. Running the dashboard or pytest exercises all code paths.

See `notebooks/compliance_analysis.ipynb` for a worked comparison of three facility profiles, including PUE vs ERF trade-offs and German EnEfG threshold analysis.

## Roadmap

- ETS-2 carbon price integration (2027)
- Real-time telemetry ingestion via Azure Event Hubs
- EU database export format for EED Article 26 reporting

## License

MIT
