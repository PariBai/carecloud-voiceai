# Container image for the FastAPI patient-registration API.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app
COPY scripts ./scripts
COPY vapi ./vapi

# SQLite lives here; mounted as a volume so data survives container restarts.
RUN mkdir -p data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
