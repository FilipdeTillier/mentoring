from typing import List, Dict, Any
import logging
import json
from pathlib import Path

from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


async def process_saved_files(
    job_id: str,
    file_paths: List[Path],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Dict[str, Any]:
    """
    Background task to process already-saved files with Docling.

    This function runs AFTER the response is sent to the user.
    It processes files that were already saved to disk:
    1. Processes each file with Docling
    2. Splits content by sections
    3. Creates overlapping chunks

    Args:
        job_id: Unique identifier for this job
        file_paths: List of paths to already-saved files
        chunk_size: Size of each chunk in characters (default: 1000)
        chunk_overlap: Number of overlapping characters (default: 200)

    Returns:
        Dictionary with processing results
    """
    print(f"[BACKGROUND JOB] Starting job {job_id} with {len(file_paths)} files", flush=True)
    logger.info(f"Starting job {job_id} with {len(file_paths)} files")

    # Initialize processor
    processor = DocumentProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    results = {
        'job_id': job_id,
        'files_processed': 0,
        'total_chunks': 0,
        'files': []
    }

    try:
        for file_path in file_paths:
            file_result = {
                'filename': file_path.name,
                'status': 'processing',
                'chunks': []
            }

            try:
                print(f"[BACKGROUND JOB] Processing file: {file_path.name}", flush=True)
                logger.info(f"Processing file: {file_path.name}")

                # Process with Docling
                print(f"[BACKGROUND JOB] Processing with Docling...", flush=True)
                chunks = await processor.process_document(file_path)

                print(f"[BACKGROUND JOB] Created {len(chunks)} chunks", flush=True)
                logger.info(f"Created {len(chunks)} chunks from {file_path.name}")

                # Store chunk information
                for chunk in chunks:
                    chunk_data = {
                        'section': chunk.section_title,
                        'index': chunk.chunk_index,
                        'content': chunk.content[:200] + '...' if len(chunk.content) > 200 else chunk.content,
                        'length': len(chunk.content),
                        'metadata': chunk.metadata
                    }
                    file_result['chunks'].append(chunk_data)

                file_result['status'] = 'completed'
                file_result['total_chunks'] = len(chunks)
                results['files_processed'] += 1
                results['total_chunks'] += len(chunks)

                # TODO: Store chunks in vector database (Qdrant)
                # This is where you would insert chunks into your vector store
                # Example:
                # await vector_store.insert_chunks(chunks, job_id, file.filename)

            except Exception as file_error:
                logger.error(f"Error processing file {file_path.name}: {str(file_error)}")
                file_result['status'] = 'failed'
                file_result['error'] = str(file_error)

            results['files'].append(file_result)

        # Save results to file for later retrieval
        results_path = Path(f"/tmp/uploads/{job_id}/results.json")
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"[BACKGROUND JOB] Job {job_id} completed successfully", flush=True)
        print(f"[BACKGROUND JOB] Processed {results['files_processed']} files, created {results['total_chunks']} chunks", flush=True)
        logger.info(f"Job {job_id} completed: {results['files_processed']} files, {results['total_chunks']} chunks")

        return results

    except Exception as e:
        print(f"[BACKGROUND JOB] Job {job_id} failed: {str(e)}", flush=True)
        logger.error(f"Job {job_id} failed: {str(e)}")
        results['status'] = 'failed'
        results['error'] = str(e)
        return results
