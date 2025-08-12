import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
META_DIR = os.path.join(DATA_DIR, "meta")
RAW_DIR  = os.path.join(DATA_DIR, "raw")
os.makedirs(META_DIR, exist_ok=True)
os.makedirs(RAW_DIR,  exist_ok=True)

WRDS_USERNAME = os.getenv("WRDS_USERNAME")
WRDS_POSTGRES_HOST = os.getenv("WRDS_POSTGRES_HOST", "wrds-pgdata.wharton.upenn.edu")
WRDS_POSTGRES_PORT = int(os.getenv("WRDS_POSTGRES_PORT", "9737"))

# Exchanges: NYSE(1), AMEX(2), NASDAQ(3)
VALID_EXCHCD = (1, 2, 3)

# Share codes: 10, 11 = common stocks
VALID_SHRCD = (10, 11)
