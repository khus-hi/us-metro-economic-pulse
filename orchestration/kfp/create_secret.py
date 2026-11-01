"""Copy the API keys from your git-ignored .env into a Kubernetes secret.

    python orchestration/kfp/create_secret.py            # namespace kubeflow

Why a script and not `kubectl create secret --from-env-file=.env`? That flag
keeps inline comments (`KEY=   # url`) as part of the value. python-dotenv
parses .env the same way the ingest code does. Keys are passed straight to
kubectl and never printed. Every key is created, even empty ones (CENSUS_API_KEY
may be blank; the ingest code then uses the keyless Census route).
"""
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

KEYS = ["FRED_API_KEY", "BLS_API_KEY", "BEA_API_KEY", "CENSUS_API_KEY", "CONTACT_EMAIL"]
REPO_ROOT = Path(__file__).resolve().parents[2]


def main(namespace: str = "kubeflow") -> int:
    env = dotenv_values(REPO_ROOT / ".env")
    missing = [k for k in KEYS if k != "CENSUS_API_KEY" and not (env.get(k) or "").strip()]
    if missing:
        print(f"Fill these in .env first: {missing}")
        return 1
    literals = [f"--from-literal={k}={(env.get(k) or '').strip()}" for k in KEYS]
    yaml = subprocess.run(
        ["kubectl", "create", "secret", "generic", "pulse-api-keys", "-n", namespace,
         *literals, "--dry-run=client", "-o", "yaml"],
        check=True, capture_output=True, text=True).stdout
    # apply (not create) so re-running after you change a key updates the secret.
    subprocess.run(["kubectl", "apply", "-f", "-"], input=yaml, check=True, text=True)
    print(f"secret pulse-api-keys set in namespace {namespace} with keys: {', '.join(KEYS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
