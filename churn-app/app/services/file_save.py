
import uuid
from pathlib import Path
from app.const import STAGING_DIR
import os
from fastapi import HTTPException, UploadFile

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

async def save_file_to_staging(file: UploadFile) -> str:
    """
    Saves a file to the /uploads/staging folder and returns a file_id.
    The file is renamed to the file_id before saving.

    Args:
        file: The UploadFile object to save

    Returns:
        str: The file_id (UUID) used as the new filename
    """
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    file_path = STAGING_DIR / file_id
    tmp_path = STAGING_DIR / f".{file_id}.tmp"

    try:
        size = 0
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:

                    if tmp_path.exists():
                        os.remove(tmp_path)
                    raise HTTPException(status_code=413, detail=f"File too large: {file.filename}")
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, file_path)
        
        if not file_path.exists():
            raise IOError(f"File was not created at {file_path}")
        
        return file_id
    except HTTPException:
        raise
    except Exception as e:
        if tmp_path.exists():
            os.remove(tmp_path)
        raise
