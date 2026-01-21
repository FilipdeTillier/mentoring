import os
import logging
from typing import List, Dict, Any, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", 6333))
        self.collection_name = "churn_app_docs"
    
        try:
            self.client = QdrantClient(host=self.host, port=self.port)
            logger.info(f"Connected to Qdrant at {self.host}:{self.port}")
            self._create_collection_if_not_exists()
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    def _create_collection_if_not_exists(self):
        """Create the collection if it doesn't exist."""
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=self.client.get_fastembed_vector_params()
                )
                logger.info(f"Created collection {self.collection_name}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            logger.error(f"Error creating collection: {e}")

    def upsert_chunks(self, job_id: str, chunks: List[Any]):
        """
        Upsert document chunks into Qdrant.
        
        Args:
            job_id: The job ID associated with these chunks.
            chunks: List of chunk objects (expected to have content and metadata).
        """
        if not chunks:
            return

        try:
            documents = []
            metadata = []
            ids = []

            for chunk in chunks:
                if isinstance(chunk, dict):
                    meta = chunk.get('metadata', {}).copy()
                    content = chunk.get('content', '')
                    section = chunk.get('section', '')
                    index = chunk.get('index', 0)
                else:
                    meta = getattr(chunk, 'metadata', {}).copy()
                    content = getattr(chunk, 'content', '')
                    section = getattr(chunk, 'section_title', '')
                    index = getattr(chunk, 'chunk_index', 0)
                
                meta['job_id'] = job_id
                meta['section'] = section
                meta['index'] = index
                
                documents.append(content)
                metadata.append(meta)
                ids.append(str(uuid4()))

            self.client.add(
                collection_name=self.collection_name,
                documents=documents,
                metadata=metadata,
                ids=ids
            )
            logger.info(f"Upserted {len(documents)} chunks to Qdrant for job {job_id}")

        except Exception as e:
            logger.error(f"Error upserting chunks to Qdrant: {e}")
            raise

    def search_context(self, query: str, limit: int = 3) -> str:
        """
        Search for relevant context for a given query.
        
        Args:
            query: The user's query.
            limit: Number of chunks to retrieve.
            
        Returns:
            Formatted context string.
        """
        try:
            search_result = self.client.query(
                collection_name=self.collection_name,
                query_text=query,
                limit=limit
            )
            
            context_parts = []
            for hit in search_result:
                content = hit.document
                meta_context = hit.metadata.get('context', '')
                section = hit.metadata.get('section', '')
                
                part = f"Section: {section}\n"
                if meta_context:
                    part += f"Context: {meta_context}\n"
                part += f"Content: {content}"
                
                context_parts.append(part)
                
            return "\n\n---\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")
            return ""
