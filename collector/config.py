import os

from dotenv import load_dotenv

load_dotenv()

if os.getenv("OPENAI_BASE_URL", "").strip() == "":
    os.environ.pop("OPENAI_BASE_URL", None)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None) or None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-thinking")

WIKI_API = "https://dungeon-crawler-carl.fandom.com/api.php"
CRAWLER_CONTACT_EMAIL = os.getenv("CRAWLER_CONTACT_EMAIL", "you@example.com")
USER_AGENT = f"dcc-dnd-collector/1.0 ({CRAWLER_CONTACT_EMAIL})"

DATA_DIR = os.path.join("data", "v1", "items")
RAW_DIR = os.path.join("data", "v1", "raw")
SCHEMA_PATH = os.path.join("schemas", "dcc-record.schema.json")
CATEGORY_ROOT = "Items"
RATE_LIMIT_SECONDS = 0.7
