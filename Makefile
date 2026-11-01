# Shortcuts. Run from the repo root with the virtualenv active.
.PHONY: ingest warehouse freshness docs test all

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
