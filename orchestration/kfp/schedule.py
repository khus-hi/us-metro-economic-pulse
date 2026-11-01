"""Upload the compiled pipeline to your local KFP and create a monthly recurring run.

    kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80     # other terminal
    python orchestration/kfp/schedule.py                              # schedule monthly
    python orchestration/kfp/schedule.py --now                        # also run once now

Cron: KFP uses 6 fields (seconds first). "0 0 14 20 * *" = 14:00 UTC on the 20th
of every month, the same time as the GitHub Actions workflow. Monthly BLS, CPI
and FRED series all publish at different points in the month; one fixed date
picks up whatever was released since the last run, and the freshness tests
flag any source that has fallen behind.
"""
import argparse
from pathlib import Path

import kfp

PIPELINE = Path(__file__).with_name("pulse_pipeline.yaml")
CRON = "0 0 14 20 * *"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://localhost:8080")
    p.add_argument("--now", action="store_true", help="also start one run immediately")
    a = p.parse_args()

    client = kfp.Client(host=a.host)
    exp = client.create_experiment(name="metro-pulse")
    exp_id = exp.experiment_id

    if a.now:
        run = client.create_run_from_pipeline_package(
            str(PIPELINE), arguments={}, run_name="metro-pulse-manual",
            experiment_name="metro-pulse", enable_caching=False)
        print(f"started run {run.run_id}")

    job = client.create_recurring_run(
        experiment_id=exp_id,
        job_name="metro-pulse-monthly",
        description="Monthly ingest -> dbt run -> dbt test -> export marts",
        cron_expression=CRON,
        max_concurrency=1,          # never two runs writing the same DuckDB file
        no_catchup=True,            # laptop was off on the 20th? run once, don't backfill every missed month
        pipeline_package_path=str(PIPELINE),
        enable_caching=False,
    )
    print(f"recurring run {job.recurring_run_id} scheduled: {CRON} (UTC)")


if __name__ == "__main__":
    main()
