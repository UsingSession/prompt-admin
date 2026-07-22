import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATABASE_DIR = BASE_DIR / "database"
SCHEMA_SQL_PATH = DATABASE_DIR / "schema.sql"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str = "0.0.0.0"
    port: int = Field(default=8090, ge=1, le=65535)
    postgres_host: str = "postgres"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str = "local_password"

    @field_validator(
        "host",
        "postgres_host",
        "postgres_db",
        "postgres_user",
        "postgres_password",
    )
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Configuration value must not be empty.")
        return value

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = env if env is not None else os.environ
        return cls(
            host=values.get("PROMPT_ADMIN_HOST", "0.0.0.0"),
            port=values.get("PROMPT_ADMIN_PORT", "8090"),
            postgres_host=values.get("POSTGRES_HOST", "postgres"),
            postgres_port=values.get("POSTGRES_PORT", "5432"),
            postgres_db=values.get("POSTGRES_DB", "postgres"),
            postgres_user=values.get("POSTGRES_USER", "postgres"),
            postgres_password=values.get(
                "POSTGRES_PASSWORD",
                "local_password",
            ),
        )

    @property
    def database_config(self) -> dict[str, str | int]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }


SETTINGS = Settings.from_env()
PORT = SETTINGS.port
DB_CONFIG = SETTINGS.database_config
