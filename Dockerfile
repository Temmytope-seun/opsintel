FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY opsintel ./opsintel
COPY app ./app
COPY knowledge ./knowledge
COPY eval ./eval
COPY tests ./tests
RUN mkdir -p docs data && python -m opsintel.cli setup
RUN useradd --create-home opsintel && chown -R opsintel /app
USER opsintel
EXPOSE 8000 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--theme.base=light"]
