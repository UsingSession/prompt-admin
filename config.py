import json
import os
from pathlib import Path


PORT = int(os.getenv("PROMPT_ADMIN_PORT", "8090"))
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATABASE_DIR = BASE_DIR / "database"
SCHEMA_SQL_PATH = DATABASE_DIR / "schema.sql"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"
SEED_PROMPTS_PATH = DATABASE_DIR / "seed_prompts.json"

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "local_password"),
}


def load_seed_prompt_keys():
    if not SEED_PROMPTS_PATH.exists():
        return []

    data = json.loads(SEED_PROMPTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("seed_prompts.json must contain a JSON array.")

    return [str(item).strip() for item in data if str(item).strip()]
