PY ?= .venv/bin/python

.PHONY: install setup test eval ui api docker
install:
	uv venv --python 3.11 .venv && uv pip install --python $(PY) -r requirements.txt
setup:            ## generate synthetic sources, run ETL, write data dictionary
	$(PY) -m opsintel.cli setup
test:
	$(PY) -m pytest -q
eval:             ## benchmark + reconciliation + risk model -> docs/evaluation_report.md
	$(PY) -m eval.run_eval
ui:
	$(PY) -m streamlit run app/streamlit_app.py
api:
	$(PY) -m uvicorn opsintel.api.main:app --reload
docker:
	docker compose up --build
