from typing import List, Dict, Any, Optional
import logging
import json
from pathlib import Path

from app.services.document_processor import DocumentProcessor
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


async def process_saved_files(
    job_id: str,
    file_paths: List[Path],
    local_llm: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background task to process already-saved files with Docling.

    This function runs AFTER the response is sent to the user.
    It processes files that were already saved to disk:
    1. Processes each file with Docling
    2. Splits content by sections/paragraphs using docling's native structure
    3. Creates paragraph-based chunks with section context

    Args:
        job_id: Unique identifier for this job
        file_paths: List of paths to already-saved files
        local_llm: Optional Ollama model name. If provided, uses local Ollama
                  instead of OpenAI for context and keyword generation.

    Returns:
        Dictionary with processing results
    """
    llm_provider = f"Ollama ({local_llm})" if local_llm else "OpenAI"
    print(f"[BACKGROUND JOB] Starting job {job_id} with {len(file_paths)} files using {llm_provider}", flush=True)
    logger.info(f"Starting job {job_id} with {len(file_paths)} files using {llm_provider}")

    processor = DocumentProcessor(local_llm=local_llm)

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

                # Save chunks to Qdrant
                try:
                    logger.info(f"Starting embedding and Qdrant storage for {len(chunks)} chunks from {file_path.name}")
                    print(f"[BACKGROUND JOB] Starting embedding and Qdrant storage for {file_path.name}...", flush=True)
                    qdrant_service = QdrantService()
                    qdrant_service.upsert_chunks(job_id, chunks, local_llm=local_llm)
                    logger.info(f"Successfully completed embedding and stored {len(chunks)} chunks in Qdrant for {file_path.name}")
                    print(f"[BACKGROUND JOB] Stored chunks in Qdrant for {file_path.name}", flush=True)
                except Exception as q_error:
                    logger.error(f"Failed to save chunks to Qdrant for {file_path.name}: {q_error}")
                    print(f"[BACKGROUND JOB] Failed to store chunks in Qdrant for {file_path.name}: {q_error}", flush=True)
                    # We don't fail the whole job if vector store fails, but we should log it
                    file_result['error'] = f"Processed but vector store failed: {q_error}"

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
