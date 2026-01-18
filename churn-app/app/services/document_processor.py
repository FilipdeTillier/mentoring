from pathlib import Path
from typing import List, Dict, Any
import logging
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of document content with metadata."""

    def __init__(
        self,
        content: str,
        section_title: str = "",
        chunk_index: int = 0,
        metadata: Dict[str, Any] = None
    ):
        self.content = content
        self.section_title = section_title
        self.chunk_index = chunk_index
        self.metadata = metadata or {}

    def __repr__(self):
        return f"DocumentChunk(section='{self.section_title}', index={self.chunk_index}, length={len(self.content)})"


class DocumentProcessor:
    """Process documents using Docling and split into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize document processor.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.converter = DocumentConverter()

    async def process_document(self, file_path: Path) -> List[DocumentChunk]:
        """
        Process document: parse with Docling, split by sections, and create overlapping chunks.

        Args:
            file_path: Path to the document file

        Returns:
            List of document chunks with overlapping content
        """
        try:
            logger.info(f"Processing document: {file_path}")

            # Convert document using Docling
            result = self.converter.convert(str(file_path))
            doc = result.document

            # Export as markdown to see what we got
            markdown_content = doc.export_to_markdown()

            # Extract sections
            sections = self._extract_sections(doc)
            logger.info(f"Extracted {len(sections)} sections from document")

            # Create overlapping chunks
            chunks = []
            for section in sections:
                section_chunks = self._create_overlapping_chunks(
                    section['content'],
                    section['title']
                )
                chunks.extend(section_chunks)

            logger.info(f"Created {len(chunks)} chunks from document")
            return chunks

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise

    def _extract_sections(self, doc: Any) -> List[Dict[str, str]]:
        """
        Extract sections from Docling document.

        Args:
            doc: Docling document object

        Returns:
            List of sections with title and content
        """
        sections = []

        # Export document as markdown for easier processing
        markdown_content = doc.export_to_markdown()

        # Split by headers (assuming markdown format with # headers)
        current_section = {'title': 'Introduction', 'content': ''}
        lines = markdown_content.split('\n')

        for line in lines:
            # Check if line is a header
            if line.startswith('#'):
                # Save previous section if it has content
                if current_section['content'].strip():
                    sections.append(current_section)

                # Start new section
                title = line.lstrip('#').strip()
                current_section = {'title': title, 'content': ''}
            else:
                current_section['content'] += line + '\n'

        # Add last section
        if current_section['content'].strip():
            sections.append(current_section)

        # If no sections found, treat entire document as one section
        if not sections:
            sections.append({
                'title': 'Document Content',
                'content': markdown_content
            })

        return sections

    def _create_overlapping_chunks(
        self,
        text: str,
        section_title: str
    ) -> List[DocumentChunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to split
            section_title: Title of the section

        Returns:
            List of document chunks with overlap
        """
        chunks = []
        text = text.strip()

        if not text:
            return chunks

        # Calculate step size (chunk_size - overlap)
        step_size = self.chunk_size - self.chunk_overlap

        # Ensure step size is positive
        if step_size <= 0:
            step_size = self.chunk_size

        # Create chunks with overlap
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            # Try to break at sentence boundary if possible
            if end < len(text):
                # Look for sentence endings near the end of chunk
                for delimiter in ['. ', '.\n', '! ', '?\n', '? ']:
                    last_delimiter = chunk_text.rfind(delimiter)
                    if last_delimiter > self.chunk_size * 0.7:  # At least 70% of chunk size
                        chunk_text = chunk_text[:last_delimiter + 1]
                        break

            chunks.append(DocumentChunk(
                content=chunk_text.strip(),
                section_title=section_title,
                chunk_index=chunk_index,
                metadata={
                    'start_pos': start,
                    'end_pos': start + len(chunk_text),
                    'has_overlap': chunk_index > 0
                }
            ))

            chunk_index += 1
            start += step_size

            # Prevent infinite loop
            if start >= len(text):
                break

        return chunks


# Example usage in processing
async def process_file_with_docling(
    file_path: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[DocumentChunk]:
    """
    Convenience function to process a file with Docling.

    Args:
        file_path: Path to file
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks

    Returns:
        List of document chunks
    """
    processor = DocumentProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return await processor.process_document(file_path)
