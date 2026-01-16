import os
from pathlib import Path

# Determine the base directory for uploads
# In Docker, the volume is mounted at /app/uploads
# Locally, it's relative to the app directory
if os.path.exists("/app/uploads"):
    # Docker container: volume is mounted at /app/uploads
    STAGING_DIR = Path("/app/uploads/staging")
else:
    # Local development: relative to app directory
    BASE_DIR = Path(__file__).resolve().parent
    STAGING_DIR = BASE_DIR / "uploads" / "staging"

STAGING_DIR.mkdir(parents=True, exist_ok=True)