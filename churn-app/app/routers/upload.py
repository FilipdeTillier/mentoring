from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid
import json
from pathlib import Path
from app.services.upload_service import process_saved_files
from app.services.file_storage import FileStorageService

router = APIRouter()


class UploadResponse(BaseModel):
    message: str
    job_id: str
    file_count: int


class JobResultResponse(BaseModel):
    job_id: str
    files_processed: int
    total_chunks: int
    files: List[Dict[str, Any]]
    status: Optional[str] = "completed"
    error: Optional[str] = None


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload files for processing",
    description="Accept a list of files and create a background job to process them. Returns a job_id to track the processing status.",
    response_description="Confirmation message with job_id and file count.",
    tags=["upload"]
)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="List of files to upload")
):
    """
    Upload endpoint that accepts multiple files and processes them in the background.

    - **files**: List of files to upload

    Returns a job_id that can be used to track the processing status.
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Quickly save files to disk first (this is fast)
    storage = FileStorageService()
    saved_file_paths = []

    for file in files:
        file_path = await storage.save_file(file, job_id)
        if file_path:
            saved_file_paths.append(file_path)

    # Add background task for processing the saved files
    # This happens AFTER the response is sent
    background_tasks.add_task(process_saved_files, job_id, saved_file_paths)

    return UploadResponse(
        message="Files received successfully",
        job_id=job_id,
        file_count=len(saved_file_paths)
    )


@router.get(
    "/job/{job_id}",
    response_model=JobResultResponse,
    summary="Get job processing results",
    description="Retrieve the processing results for a specific job by job_id.",
    response_description="Job processing results with chunks information.",
    tags=["upload"]
)
async def get_job_results(job_id: str):
    """
    Get the results of a file processing job.

    - **job_id**: The unique job identifier returned from the upload endpoint

    Returns detailed information about processed files and chunks.
    """
    results_path = Path(f"/tmp/uploads/{job_id}/results.json")

    if not results_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found or still processing"
        )

    try:
        with open(results_path, 'r') as f:
            results = json.load(f)

        return JobResultResponse(**results)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading job results: {str(e)}"
        )
