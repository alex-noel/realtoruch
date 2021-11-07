from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    service_role: str = "api"
    database_url: str = "sqlite:///./realtoruch.db"
    auth_database_url: str = "sqlite:///./auth.db"
    demo_mode: bool = False
    phone_hash_key: str = "local-demo-phone-key-change-before-deployment"
    internal_api_key: str = "local-demo-internal-key-change-before-deployment"
    jwt_secret: str = "local-demo-jwt-key-change-before-deployment-32-chars"
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_issuer: str = "realtoruch-auth"
    cors_origins: str = "http://localhost:8081,http://localhost:8082,http://localhost:19006"
    elasticsearch_url: str = ""
    elasticsearch_api_key: str = ""
    elasticsearch_ca_file: str = ""
    search_service_url: str = ""
    api_base_url: str = "http://localhost:8000"
    connectors_config: str = "../config/sources.json"
    request_limit_per_minute: int = 120
    contact_retention_days: int = 90
    gcp_project: str = ""
    pubsub_topic: str = "rental-observations"
    bigtable_instance: str = "realtoruch-raw"
    bigtable_table: str = "observations"
    cloudsql_connection_name: str = ""

    @model_validator(mode="after")
    def production_configuration(self):
        if self.environment == "production":
            required_secrets = []
            if self.service_role in ("api", "collector", "dataflow"):
                required_secrets.append("phone_hash_key")
            if self.service_role == "api":
                required_secrets.append("internal_api_key")
            for field in required_secrets:
                value = getattr(self, field)
                if value.startswith("local-demo") or len(value) < 32:
                    raise ValueError(f"Production requires a unique {field} of at least 32 characters")
            if self.service_role in ("api", "auth") and not self.jwt_public_key:
                raise ValueError("Production requires an RSA JWT public key")
            if self.demo_mode or (
                self.service_role in ("api", "indexer", "dataflow") and self.database_url.startswith("sqlite")
            ):
                raise ValueError("Production requires PostgreSQL and DEMO_MODE=false")
            if self.service_role == "auth" and self.auth_database_url.startswith("sqlite"):
                raise ValueError("Production authentication requires PostgreSQL")
        return self


@lru_cache
def get_settings():
    return Settings()
