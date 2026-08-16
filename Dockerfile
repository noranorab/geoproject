FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

# rasterio's manylinux wheels bundle GDAL/PROJ, and the API doesn't touch
# rasterio directly anyway (see Dockerfile.airflow for the same reasoning).
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "wildfirewatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
