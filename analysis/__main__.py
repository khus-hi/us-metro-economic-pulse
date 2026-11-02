"""python -m analysis run [--weights job_growth=0.5,openings=0] [--duckdb warehouse/pulse.duckdb]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import data, findings, memo, nowcast, pulse

CONFIG = Path(__file__).with_name("config.yml")


def parse_weights(text: str) -> dict[str, float]:
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        k, v = part.split("=")
        out[k.strip()] = float(v)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--weights", help="override weights, e.g. job_growth=0.5,openings=0")
    ap.add_argument("--openings-source", choices=["jolts_state", "postings"])
    ap.add_argument("--duckdb", help="read marts from this DuckDB file instead of dashboard/data CSVs")
    ap.add_argument("--data-dir", default=str(data.CSV_DIR))
    ap.add_argument("--out", default=str(data.OUT_DIR))
    a = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(a.config).read_text())
    if a.weights:
        cfg["pulse"]["weights"].update(parse_weights(a.weights))
    if a.openings_source:
        cfg["pulse"]["openings_source"] = a.openings_source
    load = lambda t: data.load(t, Path(a.data_dir), a.duckdb)  # noqa: E731
    monthly, pay, dim = load("fct_metro_monthly"), load("fct_analyst_pay"), load("dim_metro")
    postings = load("fct_postings") if cfg["pulse"].get("openings_source") == "postings" else None

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    p = pulse.compute(monthly, cfg["pulse"], postings)
    keep = ["cbsa_code", "month_date", "pulse", "pulse_rank", "weight_coverage", "components_used",
            *[c for c in p.columns if c.startswith("z_")], "nonfarm_jobs_yoy_pct", "unemployment_rate",
            "unemployment_change_yoy_pp", "real_wage_growth_pp", "real_wage_is_carried", "openings", "openings_month",
            *[c for c in p.columns if c.startswith(("pulse_change_", "job_growth_change_"))]]
    p_out = p[keep].dropna(subset=["pulse"]).sort_values(["month_date", "pulse_rank"])
    p_out.to_csv(out / "pulse_monthly.csv", index=False, float_format="%.4f")
    latest = pulse.latest_month(p)
    p_out[p_out["month_date"] == latest].to_csv(out / "pulse_latest.csv", index=False, float_format="%.4f")

    panel = nowcast.build_panel(monthly)
    cv, preds = nowcast.cross_validate(panel, cfg["nowcast"])
    cv.to_csv(out / "nowcast_cv.csv", index=False, float_format="%.4f")
    preds.to_csv(out / "nowcast_cv_predictions.csv", index=False, float_format="%.4f")
    now, coefs = nowcast.nowcast_next(panel, cfg["nowcast"])
    now.to_csv(out / "nowcast_next_month.csv", index=False, float_format="%.4f")

    md, facts = findings.build(p, cv, now, coefs, pay, dim, cfg["findings"], cfg["pulse"])
    (out / "findings.md").write_text(md)
    (out / "findings.json").write_text(json.dumps(facts, indent=2, default=str))
    m = memo.build(p, now, cv, pay, load("fct_postings"), load("fct_posting_tools"), dim,
                   cfg["findings"], cfg["pulse"])
    (out / "memo.md").write_text(m)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
