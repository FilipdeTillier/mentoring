from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STAGING_DIR = BASE_DIR / "uploads" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)