import os
from dotenv import load_dotenv

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ASSERT_API = True
if ASSERT_API and not POLYGON_API_KEY:
    raise RuntimeError("Set POLYGON_API_KEY in .env")
