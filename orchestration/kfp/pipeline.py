"""Monthly US Metro Economic Pulse pipeline for Kubeflow Pipelines (KFP v2).

Graph (one component per step):

    crosswalk --> ingest(bls) ----------\
              --> ingest(fred) ----------\
              --> ingest(census_acs) -----> dbt_run --> dbt_test --> export_marts
              --> ingest(bea) -----------/
              --> ingest(oews) ---------/
              --> ingest(postings) ----/

Design notes (interview talking points):
- Container components: every step runs the same image (repo Dockerfile) with a
  different command, so the pipeline runs exactly the code you test on your laptop.
- Shared volume: steps run in separate pods, so raw files and the DuckDB file
  live on one PersistentVolumeClaim (`pulse-data`) mounted at /data. It persists
  between monthly runs, which keeps the postings history (first_seen/last_seen).
- Secrets: API keys come from the Kubernetes secret `pulse-api-keys` as env vars,
  and only the ingest steps get them. Nothing secret is in the image or the YAML.
- Caching is off: the inputs live outside KFP (public APIs), so a cached
  "same inputs" result would silently skip new data.
- Sources ingest in parallel after the crosswalk because each depends only on
  the metro list; one failing source fails the run before dbt touches the data.

# KFP reads the type hints at runtime, so no `from __future__ import annotations` here.
Compile:  python orchestration/kfp/pipeline.py   -> orchestration/kfp/pulse_pipeline.yaml
"""

import os
from pathlib import Path

from kfp import compiler, dsl, kubernetes

IMAGE = os.environ.get("PULSE_IMAGE", "pulse-pipeline:0.1")  # loaded into kind, no registry needed
PVC = "pulse-data"
SECRET = "pulse-api-keys"
KEYS = ["FRED_API_KEY", "BLS_API_KEY", "BEA_API_KEY", "CENSUS_API_KEY", "CONTACT_EMAIL"]
SOURCES = ["bls", "fred", "census_acs", "bea", "oews", "postings"]
DBT = "cd /app/models && mkdir -p /data/warehouse && "


@dsl.container_component
def ingest(source: str, start_year: int):
    """Pull one source into /data/raw/{source}/{run_date}/ (or build the crosswalk)."""
    return dsl.ContainerSpec(
        image=IMAGE,
        command=["python", "-m", "ingest", "run"],
        args=[source, "--start-year", start_year],
    )


@dsl.container_component
def dbt_run():
    """Load reference seeds, then build staging -> intermediate -> marts in DuckDB."""
    return dsl.ContainerSpec(
        image=IMAGE, command=["sh", "-c"],
        args=[DBT + "dbt seed --profiles-dir . && dbt run --profiles-dir ."],
    )


@dsl.container_component
def dbt_test():
    """Source freshness (did every source land recently?) then every dbt data test."""
    return dsl.ContainerSpec(
        image=IMAGE, command=["sh", "-c"],
        args=[DBT + "dbt source freshness --profiles-dir . && dbt test --profiles-dir ."],
    )


@dsl.container_component
def export_marts(marts: dsl.Output[dsl.Artifact]):
    """Write each mart to CSV, saved as a KFP artifact you can download from the UI."""
    return dsl.ContainerSpec(
        image=IMAGE,
        command=["python", "/app/dashboard/export_marts.py"],
        args=["--out", marts.path],
    )


def _prepare(task: dsl.PipelineTask, name: str, secrets: bool = False) -> dsl.PipelineTask:
    task.set_display_name(name)
    task.set_caching_options(False)
    kubernetes.mount_pvc(task, pvc_name=PVC, mount_path="/data")
    kubernetes.set_image_pull_policy(task, "IfNotPresent")
    if secrets:
        kubernetes.use_secret_as_env(task, secret_name=SECRET,
                                     secret_key_to_env={k: k for k in KEYS})
    return task


@dsl.pipeline(
    name="us-metro-economic-pulse",
    description="Monthly: ingest public economic data for the top 50 US metros, "
                "build the dbt marts in DuckDB, test them, export mart CSVs.",
)
def pulse_pipeline(start_year: int = 2015):
    crosswalk = _prepare(ingest(source="crosswalk", start_year=start_year), "crosswalk", secrets=True)

    landed = []
    for source in SOURCES:
        t = _prepare(ingest(source=source, start_year=start_year), f"ingest {source}", secrets=True)
        t.after(crosswalk)
        landed.append(t)

    run = _prepare(dbt_run(), "dbt run").after(*landed)
    test = _prepare(dbt_test(), "dbt test").after(run)
    _prepare(export_marts(), "export marts").after(test)


if __name__ == "__main__":
    out = Path(__file__).with_name("pulse_pipeline.yaml")
    compiler.Compiler().compile(pulse_pipeline, str(out))
    print(f"compiled {out}")
