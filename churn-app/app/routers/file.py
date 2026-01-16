from fastapi import HTTPException, APIRouter, UploadFile, BackgroundTasks
from typing import List, Dict, Any
from app.services.file_save import save_file_to_staging
from app.services.file_process import process_file_background

router = APIRouter()

@router.post("/upload", tags=["Files"])
async def upload(files: List[UploadFile], background_tasks: BackgroundTasks) -> Dict[str, Any]:
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")

    file_ids = []
    try:
        for file in files:
            file_id = await save_file_to_staging(file)
            file_ids.append({"filename": file.filename, "file_id": file_id})
            
            background_tasks.add_task(process_file_background, file_id, file.filename)
        
        return {"files": file_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving files: {str(e)}")
