from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://wfw:wfw@localhost:5432/wildfirewatch"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "wfwminio"
    s3_secret_key: str = "wfwminio123"
    s3_raw_bucket: str = "wildfirewatch-raw"
    s3_processed_bucket: str = "wildfirewatch-processed"
    s3_region: str = "us-east-1"

    stac_api_url: str = "https://earth-search.aws.element84.com/v1"
    stac_collection: str = "sentinel-2-l2a"

    log_format: str = "console"  # "console" (dev) or "json" (production/containers)
    pushgateway_url: str | None = None  # e.g. http://pushgateway:9091; unset disables metric push


@lru_cache
def get_settings() -> Settings:
    return Settings()
