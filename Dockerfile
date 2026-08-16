FROM python:3.11-slim

# rasterio's manylinux wheels bundle GDAL/PROJ (see Dockerfile.airflow), but
# still dynamically link libexpat, which python:3.11-slim doesn't ship.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY scripts ./scripts
COPY demo ./demo

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "wildfirewatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
