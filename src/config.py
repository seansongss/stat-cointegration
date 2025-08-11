import os
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not POLYGON_API_KEY:
    raise RuntimeError(
        "POLYGON_API_KEY not set. Copy .env.example to .env and paste your key."
    )

MARKET_TZ = "America/New_York"

REGULAR_OPEN = "09:30"
REGULAR_CLOSE = "16:00"

DATA_DIR = os.path.join("data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
META_DIR = os.path.join(DATA_DIR, "meta")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)
