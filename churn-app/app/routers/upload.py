from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form
from pydantic import BaseModel
import uuid
import json
from pathlib import Path
from app.services.upload_service import process_saved_files
from app.services.file_storage import FileStorageService
from app.services.qdrant_service import QdrantService

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
    description="Accept a list of files and create a background job to process them. Returns a job_id to track the processing status. Use 'local_llm' parameter to use a local Ollama model for context and keyword generation instead of OpenAI.",
    response_description="Confirmation message with job_id and file count.",
    tags=["upload"]
)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="List of files to upload"),
    local_llm: Optional[str] = Form(
        default=None,
        description="Local Ollama model name (e.g., 'llama2', 'mistral'). If provided, uses Ollama instead of OpenAI for context and keyword generation."
    )
):
    """
    Upload endpoint that accepts multiple files and processes them in the background.

    - **files**: List of files to upload
    - **local_llm**: Optional local Ollama model name for processing

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

    background_tasks.add_task(process_saved_files, job_id, saved_file_paths, local_llm)

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


class FileInfo(BaseModel):
    file_id: str
    file_name: str


class FilesListResponse(BaseModel):
    files: List[FileInfo]
    count: int


@router.get(
    "/files",
    response_model=FilesListResponse,
    summary="List all uploaded files",
    description="Retrieve a list of all files stored in Qdrant.",
    response_description="List of files with file_id and file_name.",
    tags=["upload"]
)
async def list_files():
    """
    List all files that have been uploaded and processed.

    Returns a list of files with their IDs for use in chat filtering.
    """
    try:
        qdrant_service = QdrantService()
        files = qdrant_service.list_files()

        return FilesListResponse(
            files=[FileInfo(**f) for f in files],
            count=len(files)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing files: {str(e)}"
        )
