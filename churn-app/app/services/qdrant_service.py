import os
import logging
from typing import List, Dict, Any, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.services.llm_service import generate_keywords

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

    def upsert_chunks(
        self,
        job_id: str,
        chunks: List[Any],
        local_llm: Optional[str] = None
    ):
        """
        Upsert document chunks into Qdrant.

        For each chunk:
        - Combines context with content for embedding
        - Generates keywords using LLM (OpenAI or Ollama)
        - Stores page_numbers, file_name, and keywords in metadata

        Args:
            job_id: The job ID associated with these chunks.
            chunks: List of chunk objects (expected to have content and metadata).
            local_llm: Optional Ollama model name for keyword generation.
        """
        if not chunks:
            logger.warning(f"No chunks provided for job {job_id}, skipping upsert")
            return

        try:
            logger.info(f"Starting upsert process for job {job_id}: preparing {len(chunks)} chunks for embedding and storage")
            documents = []
            metadata = []
            ids = []

            for chunk_idx, chunk in enumerate(chunks):
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

                # Extract context and file_name from existing metadata
                context = meta.get('context', '')
                file_name = meta.get('filename', '')
                page_numbers = meta.get('page_numbers', [1])

                # Combine context with content for embedding
                if context:
                    combined_content = f"Context: {context}\n\nContent: {content}"
                else:
                    combined_content = content

                logger.debug(f"Processing chunk {chunk_idx + 1}/{len(chunks)} (index: {index}, section: {section}, file: {file_name})")

                # Generate keywords using LLM
                logger.debug(f"Generating keywords for chunk {chunk_idx + 1}")
                keywords = generate_keywords(content, local_llm)

                # Generate file_id from job_id and filename
                file_id = f"{job_id}_{file_name}" if file_name else job_id

                # Build metadata with all required fields
                meta['job_id'] = job_id
                meta['file_id'] = file_id
                meta['section'] = section
                meta['index'] = index
                meta['file_name'] = file_name
                meta['page_numbers'] = page_numbers
                meta['keywords'] = keywords

                documents.append(combined_content)
                metadata.append(meta)
                ids.append(str(uuid4()))

                if (chunk_idx + 1) % 10 == 0:
                    logger.info(f"Prepared {chunk_idx + 1}/{len(chunks)} chunks for embedding")

            logger.info(f"Prepared all {len(documents)} chunks. Starting embedding and creating records in Qdrant collection '{self.collection_name}'")
            
            self.client.add(
                collection_name=self.collection_name,
                documents=documents,
                metadata=metadata,
                ids=ids
            )
            
            logger.info(f"Successfully upserted {len(documents)} chunks to Qdrant for job {job_id} in collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Error upserting chunks to Qdrant for job {job_id}: {e}")
            raise

    def search_context(
        self,
        query: str,
        limit: int = 3,
        file_ids: Optional[List[str]] = None
    ) -> str:
        """
        Hybrid search for relevant context using content and metadata.

        Searches both vector similarity on content and filters by metadata.
        Supports filtering by file_ids to search only specific files.

        Args:
            query: The user's query.
            limit: Number of chunks to retrieve.
            file_ids: Optional list of file IDs to filter by. If empty/None, searches all files.

        Returns:
            Formatted context string.
        """
        try:
            query_filter = None
            if file_ids:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="file_id",
                            match=models.MatchAny(any=file_ids)
                        )
                    ]
                )
                logger.debug(f"Searching with file filter: {file_ids}")

            search_result = self.client.query(
                collection_name=self.collection_name,
                query_text=query,
                query_filter=query_filter,
                limit=limit
            )

            context_parts = []
            for hit in search_result:
                content = hit.document
                meta_context = hit.metadata.get('context', '')
                section = hit.metadata.get('section', '')
                keywords = hit.metadata.get('keywords', [])
                file_name = hit.metadata.get('file_name', '')
                page_numbers = hit.metadata.get('page_numbers', [])
                # Handle both old format (single int) and new format (list)
                if isinstance(page_numbers, int):
                    page_numbers = [page_numbers]
                pages_str = ', '.join(str(p) for p in page_numbers) if page_numbers else 'unknown'

                part = f"File: {file_name}\n"
                part += f"Pages: {pages_str}\n"
                part += f"Section: {section}\n"
                if keywords:
                    part += f"Keywords: {', '.join(keywords)}\n"
                if meta_context:
                    part += f"Context: {meta_context}\n"
                part += f"Content: {content}"

                context_parts.append(part)

            return "\n\n---\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")
            return ""

    def hybrid_search(
        self,
        query: str,
        limit: int = 3,
        file_ids: Optional[List[str]] = None,
        keyword_boost: float = 0.3
    ) -> str:
        """
        Enhanced hybrid search combining semantic search with keyword matching.

        Performs semantic vector search and boosts results that match
        query keywords in metadata.

        Args:
            query: The user's query.
            limit: Number of chunks to retrieve.
            file_ids: Optional list of file IDs to filter by.
            keyword_boost: Weight for keyword matches in scoring.

        Returns:
            Formatted context string.
        """
        try:
            query_filter = None
            if file_ids:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="file_id",
                            match=models.MatchAny(any=file_ids)
                        )
                    ]
                )
                logger.debug(f"Hybrid search with file filter: {file_ids}")

            # Extract query keywords for matching
            query_words = set(query.lower().split())

            # Fetch more results for re-ranking
            search_result = self.client.query(
                collection_name=self.collection_name,
                query_text=query,
                query_filter=query_filter,
                limit=limit * 2
            )

            # Re-rank based on keyword matches
            scored_results = []
            for hit in search_result:
                base_score = hit.score if hasattr(hit, 'score') else 1.0
                keywords = hit.metadata.get('keywords', [])
                context = hit.metadata.get('context', '')

                # Calculate keyword overlap
                hit_keywords = set(kw.lower() for kw in keywords)
                context_words = set(context.lower().split())

                keyword_overlap = len(query_words & hit_keywords)
                context_overlap = len(query_words & context_words)

                boost = (keyword_overlap + context_overlap * 0.5) * keyword_boost
                final_score = base_score + boost

                scored_results.append((final_score, hit))

            # Sort by score and take top results
            scored_results.sort(key=lambda x: x[0], reverse=True)
            top_results = scored_results[:limit]

            context_parts = []
            all_sources = []  # Track all sources for summary

            for score, hit in top_results:
                content = hit.document
                meta_context = hit.metadata.get('context', '')
                section = hit.metadata.get('section', '')
                keywords = hit.metadata.get('keywords', [])
                file_name = hit.metadata.get('file_name', '')
                page_numbers = hit.metadata.get('page_numbers', [])
                # Handle both old format (single int) and new format (list)
                if isinstance(page_numbers, int):
                    page_numbers = [page_numbers]
                pages_str = ', '.join(str(p) for p in page_numbers) if page_numbers else 'unknown'

                # Track source for summary
                all_sources.append({
                    'file': file_name,
                    'pages': page_numbers,
                    'score': score
                })

                part = f"File: {file_name}\n"
                part += f"Pages: {pages_str}\n"
                part += f"Section: {section}\n"
                if keywords:
                    part += f"Keywords: {', '.join(keywords)}\n"
                if meta_context:
                    part += f"Context: {meta_context}\n"
                part += f"Content: {content}"

                context_parts.append(part)

            # Add summary of all found sources at the beginning
            sources_summary = f"## Podsumowanie znalezionych źródeł (znaleziono {len(all_sources)} wyników):\n"
            if len(all_sources) > 1:
                sources_summary += "UWAGA: Znaleziono informacje w WIELU miejscach! Musisz poinformować użytkownika o wszystkich lokalizacjach.\n"
            sources_summary += "Lista znalezionych źródeł:\n"
            for idx, src in enumerate(all_sources, 1):
                pages = ', '.join(str(p) for p in src['pages']) if src['pages'] else 'nieznane'
                sources_summary += f"  {idx}. Plik: {src['file']} - strony: {pages}\n"
            sources_summary += "\nSzczegółowe konteksty poniżej:\n\n"
            return sources_summary + "\n\n---\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return ""

    def list_files(self) -> List[Dict[str, str]]:
        """
        List all unique files stored in Qdrant.

        Returns:
            List of dicts with file_id and file_name.
        """
        try:
            # Scroll through all points to collect unique file_ids
            files_map = {}
            offset = None

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                if not results:
                    break

                for point in results:
                    payload = point.payload or {}
                    file_id = payload.get('file_id')
                    file_name = payload.get('file_name', '')

                    if file_id and file_id not in files_map:
                        files_map[file_id] = {
                            'file_id': file_id,
                            'file_name': file_name
                        }

                if offset is None:
                    break

            return list(files_map.values())

        except Exception as e:
            logger.error(f"Error listing files from Qdrant: {e}")
            return []
