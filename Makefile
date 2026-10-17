PY ?= .venv/bin/python

.PHONY: install setup test eval ui api docker sn-test sn-sync sn-ui
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
sn-test:          ## check ServiceNow credentials (.env) and read access
	$(PY) -m opsintel.cli servicenow-test
sn-sync:          ## extract the ServiceNow instance into data_servicenow/ and run the ETL
	$(PY) -m opsintel.cli servicenow-sync
sn-ui:            ## dashboard on the ServiceNow-sourced data
	OPSINTEL_DATA_DIR=data_servicenow $(PY) -m streamlit run app/streamlit_app.py --server.port 8502
