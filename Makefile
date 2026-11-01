# Shortcuts. Run from the repo root with the virtualenv active.
.PHONY: ingest warehouse freshness docs test all export image kfp-compile

DBT = cd models && dbt

ingest:          ## pull every source into data/raw
	python -m ingest run all

warehouse:       ## load seeds, build every model, run every dbt test
	mkdir -p warehouse
	$(DBT) build --profiles-dir .

freshness:       ## how old is each source's latest pull?
	$(DBT) source freshness --profiles-dir .

docs:            ## build the dbt docs site (lineage graph + column docs)
	$(DBT) docs generate --profiles-dir . --static
	cp models/target/static_index.html docs/dbt_docs.html
	@echo "Open docs/dbt_docs.html in a browser, or run: cd models && dbt docs serve --profiles-dir ."

test:            ## python tests for the ingest layer
	pytest

all: ingest warehouse freshness docs test

export:          ## write every mart to dashboard/data/*.csv
	python dashboard/export_marts.py

PULSE_IMAGE ?= pulse-pipeline:0.1
image:           ## build the pipeline image and load it into the kind cluster "pulse"
	docker build -t $(PULSE_IMAGE) .
	kind load docker-image $(PULSE_IMAGE) --name pulse

kfp-compile:     ## compile the Kubeflow pipeline to orchestration/kfp/pulse_pipeline.yaml
	PULSE_IMAGE=$(PULSE_IMAGE) python orchestration/kfp/pipeline.py
