import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Document processing service using Docling for document conversion
    and chunking with OpenAI-generated section context summaries.
    """

    def __init__(self):
        self._openai_client: Optional[OpenAI] = None

    @property
    def openai_client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def generate_section_summary(self, section_text: str) -> str:
        """
        Generate a brief summary of a section using OpenAI GPT-3.5.

        Args:
            section_text: The full text content of the section

        Returns:
            A brief summary with the most important information
        """
        if not section_text.strip():
            return ""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates very brief summaries. "
                        "Summarize the given text in a few words, capturing only the most important information. "
                        "Keep the summary under 50 words.",
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this section briefly:\n\n{section_text[:4000]}",
                    },
                ],
                max_tokens=100,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Failed to generate section summary: {e}")
            return ""

    def process_document_with_docling(
        self,
        file_path: str,
        job_id: str,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process a document using Docling with section-level context summaries.

        For each section in the document:
        1. Extract all chunks belonging to that section
        2. Generate a summary of the entire section using GPT-3.5
        3. Add the summary as 'context' in the metadata of each chunk

        Returns: Processing result with chunks containing context metadata
        """
        from docling.chunking import HybridChunker
        from docling.document_converter import DocumentConverter

        options = options or {}
        path = Path(file_path)

        logger.info(f"Processing document with Docling for job {job_id}: {path.name}")

        # Convert document using Docling
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document

        # Create chunker
        chunker = HybridChunker()
        chunks = list(chunker.chunk(doc))

        # Group chunks by section (using headings path)
        sections: dict[str, list] = defaultdict(list)
        for chunk in chunks:
            # Get section identifier from chunk metadata
            section_key = self._get_section_key(chunk)
            sections[section_key].append(chunk)

        # Generate summaries for each section and add context to chunks
        processed_chunks = []
        section_summaries: dict[str, str] = {}

        for section_key, section_chunks in sections.items():
            # Combine all chunk texts in the section
            section_text = " ".join(chunk.text for chunk in section_chunks)

            # Generate summary only once per section (to avoid repeated API calls)
            if section_key not in section_summaries:
                logger.info(f"Generating summary for section: {section_key}")
                section_summaries[section_key] = self.generate_section_summary(
                    section_text
                )

            context_summary = section_summaries[section_key]

            # Add context to each chunk's metadata
            for chunk in section_chunks:
                chunk_data = {
                    "text": chunk.text,
                    "meta": {
                        "context": context_summary,
                        "section": section_key,
                        "headings": self._get_headings(chunk),
                        "page": getattr(chunk.meta, "page", None)
                        if hasattr(chunk, "meta")
                        else None,
                    },
                }
                processed_chunks.append(chunk_data)

        return {
            "job_id": job_id,
            "filename": path.name,
            "file_size_bytes": path.stat().st_size,
            "extension": path.suffix.lower(),
            "type": "docling",
            "chunk_count": len(processed_chunks),
            "section_count": len(sections),
            "chunks": processed_chunks,
        }

    def _get_section_key(self, chunk) -> str:
        """Extract section identifier from chunk metadata."""
        if hasattr(chunk, "meta") and hasattr(chunk.meta, "headings"):
            headings = chunk.meta.headings
            if headings:
                return " > ".join(headings)
        return "root"

    def _get_headings(self, chunk) -> list[str]:
        """Extract headings list from chunk metadata."""
        if hasattr(chunk, "meta") and hasattr(chunk.meta, "headings"):
            return list(chunk.meta.headings) if chunk.meta.headings else []
        return []

    def process_document(
        self,
        file_path: str,
        job_id: str,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process a document file.

        For PDF and DOCX files, uses Docling with context summaries.
        For other files, falls back to basic processing.

        Returns: Processing result dictionary
        Raises: Exception if processing fails
        """
        options = options or {}
        path = Path(file_path)

        logger.info(f"Processing document for job {job_id}: {path.name}")

        ext = path.suffix.lower()

        # Use Docling for supported document types
        if ext in [".pdf", ".docx", ".pptx", ".xlsx", ".html", ".md"]:
            return self.process_document_with_docling(file_path, job_id, options)

        # Fallback for other file types
        result = {
            "job_id": job_id,
            "filename": path.name,
            "file_size_bytes": path.stat().st_size,
            "extension": ext,
        }

        if ext == ".txt":
            result.update(self._process_text_file(path))
        elif ext == ".csv":
            result.update(self._process_csv_file(path))
        else:
            result["warning"] = f"No specific processor for {ext}, basic metadata only"

        return result

    def _process_text_file(self, path: Path) -> dict[str, Any]:
        """Process plain text file."""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return {
            "type": "text",
            "char_count": len(content),
            "line_count": content.count("\n") + 1,
            "word_count": len(content.split()),
        }

    def _process_csv_file(self, path: Path) -> dict[str, Any]:
        """Process CSV file."""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        return {
            "type": "csv",
            "row_count": len(lines),
            "header": lines[0].strip() if lines else None,
        }


# Default instance
document_processor = DocumentProcessor()
