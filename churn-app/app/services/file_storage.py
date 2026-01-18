import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
import logging

logger = logging.getLogger(__name__)

# Allowed file extensions for security
ALLOWED_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.txt', '.md',
    '.pptx', '.ppt', '.xlsx', '.xls', '.html'
}

# Maximum file size in bytes (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class FileStorageService:
    """Secure file storage service with validation."""

    def __init__(self, base_path: str = "/tmp/uploads"):
        """
        Initialize file storage service.

        Args:
            base_path: Base directory for storing files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _validate_filename(self, filename: str) -> bool:
        """
        Validate filename for security.

        Args:
            filename: The filename to validate

        Returns:
            True if valid, False otherwise
        """
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False

        return True

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing dangerous characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Keep only safe characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
        sanitized = ''.join(c if c in safe_chars else '_' for c in filename)
        return sanitized

    async def save_file(
        self,
        file: UploadFile,
        job_id: str
    ) -> Optional[Path]:
        """
        Save uploaded file securely.

        Args:
            file: The uploaded file
            job_id: Job identifier for organization

        Returns:
            Path to saved file, or None if validation failed
        """
        try:
            # Validate filename
            if not self._validate_filename(file.filename):
                logger.warning(f"Invalid filename: {file.filename}")
                return None

            # Create job directory
            job_dir = self.base_path / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            sanitized_name = self._sanitize_filename(file.filename)
            unique_id = str(uuid.uuid4())[:8]
            file_ext = Path(sanitized_name).suffix
            safe_filename = f"{Path(sanitized_name).stem}_{unique_id}{file_ext}"

            file_path = job_dir / safe_filename

            # Read and validate file size
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                logger.warning(f"File too large: {len(content)} bytes")
                return None

            # Save file
            with open(file_path, 'wb') as f:
                f.write(content)

            logger.info(f"Saved file: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return None

    def cleanup_job_files(self, job_id: str) -> bool:
        """
        Clean up files for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            job_dir = self.base_path / job_id
            if job_dir.exists():
                for file in job_dir.iterdir():
                    file.unlink()
                job_dir.rmdir()
                logger.info(f"Cleaned up files for job: {job_id}")
                return True
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {str(e)}")
        return False
