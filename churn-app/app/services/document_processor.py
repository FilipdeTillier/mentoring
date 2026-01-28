from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import asyncio
import json
from collections import defaultdict
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel

from app.services.llm_service import generate_section_context

logger = logging.getLogger(__name__)

# Directory to save debug output
DEBUG_OUTPUT_DIR = Path(__file__).parent / "docling_debug"


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


class PageContent:
    """Represents content of a single page."""

    def __init__(self, page_number: int):
        self.page_number = page_number
        self.sections: List[Dict[str, Any]] = []  # List of sections on this page

    def add_item(self, item_data: Dict[str, Any]):
        """Add an item to the page."""
        self.sections.append(item_data)


class DocumentProcessor:
    """Process documents using Docling and split into page-based, section-based chunks."""

    def __init__(self, local_llm: Optional[str] = None):
        """
        Initialize document processor.

        Args:
            local_llm: Optional Ollama model name. If provided, uses local Ollama
                      instead of OpenAI for context generation.
        """
        self.converter = DocumentConverter()
        self._local_llm = local_llm

    async def process_document(self, file_path: Path) -> List[DocumentChunk]:
        """
        Process document: parse with Docling and create page-based, section-based chunks.

        Structure:
        1. First split all content by pages
        2. Within each page, split by sections
        3. Each section is a chunk
        4. Sub-chapters are separate chunks with parent chapter context

        Args:
            file_path: Path to the document file

        Returns:
            List of document chunks
        """
        try:
            logger.info(f"Processing document: {file_path}")

            result = await asyncio.to_thread(self.converter.convert, str(file_path))
            doc = result.document

            # Save Docling debug output
            self._save_docling_debug_output(doc, file_path.name)

            # Step 1: Extract all items grouped by page
            pages_data = self._extract_items_by_page(doc)
            logger.info(f"Extracted content from {len(pages_data)} pages")

            # Step 2: Create chunks from pages and sections
            chunks = self._create_chunks_from_pages(pages_data, file_path.name)
            logger.info(f"Created {len(chunks)} chunks from document")

            return chunks

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise

    def _extract_items_by_page(self, doc: Any) -> Dict[int, List[Dict[str, Any]]]:
        """
        Extract all items from Docling document grouped by page number.

        Args:
            doc: Docling document object

        Returns:
            Dict mapping page_number -> list of items on that page
        """
        pages: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        # Extended content labels - include all possible text content types
        content_labels = {
            DocItemLabel.PARAGRAPH,
            DocItemLabel.TEXT,
            DocItemLabel.LIST_ITEM,
            DocItemLabel.CAPTION,
            DocItemLabel.FOOTNOTE,
        }

        # Track current section hierarchy
        current_hierarchy: Dict[int, str] = {}  # level -> title

        total_items = 0
        added_items = 0
        skipped_items = []

        for item, level in doc.iterate_items():
            total_items += 1
            page_number = self._extract_page_number(item)
            if page_number is None:
                page_number = 1  # Default to page 1 if not found

            item_data = {
                "type": None,
                "text": "",
                "level": level,
                "section_hierarchy": dict(current_hierarchy),  # Copy current hierarchy
                "page_number": page_number,
                "label": str(item.label) if hasattr(item, 'label') else None
            }

            if item.label == DocItemLabel.TITLE:
                item_data["type"] = "title"
                item_data["text"] = getattr(item, 'text', '')
                if item_data["text"]:
                    current_hierarchy = {0: item_data["text"]}
                    item_data["section_hierarchy"] = dict(current_hierarchy)

            elif item.label == DocItemLabel.SECTION_HEADER:
                item_data["type"] = "section_header"
                item_data["text"] = getattr(item, 'text', '')
                header_level = getattr(item, 'level', 1)
                item_data["header_level"] = header_level

                if item_data["text"]:
                    # Update hierarchy - keep only levels < current level
                    current_hierarchy = {
                        k: v for k, v in current_hierarchy.items() if k < header_level
                    }
                    current_hierarchy[header_level] = item_data["text"]
                    item_data["section_hierarchy"] = dict(current_hierarchy)

            elif item.label in content_labels:
                item_data["type"] = "content"
                item_data["text"] = getattr(item, 'text', '')

            elif item.label == DocItemLabel.TABLE:
                item_data["type"] = "table"
                item_data["text"] = self._extract_table_text(item)

            else:
                # Handle any other label types as generic content
                text = getattr(item, 'text', '')
                if text:
                    item_data["type"] = "other_content"
                    item_data["text"] = text
                    logger.debug(f"Found item with unhandled label {item.label} on page {page_number}: {text[:100]}...")

            # Add ALL items with text content
            if item_data["text"]:
                pages[page_number].append(item_data)
                added_items += 1
            else:
                skipped_items.append({
                    "page": page_number,
                    "label": item_data["label"],
                    "type": item_data["type"]
                })

        # Log statistics
        logger.info(f"Extracted {added_items}/{total_items} items across {len(pages)} pages")
        if skipped_items:
            logger.debug(f"Skipped {len(skipped_items)} empty items")

        # Log per-page statistics
        for page_num in sorted(pages.keys()):
            logger.info(f"Page {page_num}: {len(pages[page_num])} items")

        return dict(pages)

    def _create_chunks_from_pages(
        self,
        pages_data: Dict[int, List[Dict[str, Any]]],
        filename: str
    ) -> List[DocumentChunk]:
        """
        Create chunks from page-grouped data.

        Each section on a page becomes a chunk. Content without explicit section
        headers is grouped under the current section context.

        Args:
            pages_data: Dict mapping page_number -> list of items
            filename: Name of the source file

        Returns:
            List of DocumentChunk objects
        """
        chunks = []
        chunk_index = 0

        # Process pages in order
        for page_number in sorted(pages_data.keys()):
            page_items = pages_data[page_number]

            # Group items by section on this page
            sections_on_page = self._group_items_by_section(page_items, page_number)

            for section_data in sections_on_page:
                if not section_data["content"].strip():
                    continue

                # Build section title from hierarchy
                section_title = self._build_section_title(section_data["hierarchy"])

                # Generate context (includes parent chapter info)
                parent_context = self._build_parent_context(section_data["hierarchy"])
                section_context = self._generate_section_context(section_data["content"])

                # Combine parent context with generated context
                full_context = ""
                if parent_context:
                    full_context = f"Rozdział nadrzędny: {parent_context}\n"
                if section_context:
                    full_context += f"Kontekst sekcji: {section_context}"

                chunk = DocumentChunk(
                    content=section_data["content"],
                    section_title=section_title,
                    chunk_index=chunk_index,
                    metadata={
                        'section_name': section_data.get("section_name", section_title),
                        'chapter_name': section_data.get("chapter_name", ""),
                        'parent_context': parent_context,
                        'section_level': section_data.get("level", 0),
                        'context': full_context,
                        'filename': filename,
                        'page_number': page_number,  # Single page number
                        'page_numbers': [page_number],  # For compatibility
                        'hierarchy': section_data["hierarchy"]
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

                logger.debug(
                    f"Created chunk {chunk_index} from page {page_number}, "
                    f"section '{section_title}', length: {len(section_data['content'])} chars"
                )

        return chunks

    def _group_items_by_section(
        self,
        page_items: List[Dict[str, Any]],
        page_number: int
    ) -> List[Dict[str, Any]]:
        """
        Group items on a page by their section.

        Args:
            page_items: List of items on the page
            page_number: The page number

        Returns:
            List of section data dicts with content and metadata
        """
        if not page_items:
            logger.warning(f"No items on page {page_number}")
            return []

        sections = []

        # Get initial hierarchy from first item if available
        first_item_hierarchy = page_items[0].get("section_hierarchy", {}) if page_items else {}

        current_section = {
            "hierarchy": first_item_hierarchy,
            "content_parts": [],
            "level": 0,
            "section_name": f"Strona {page_number}",
            "chapter_name": first_item_hierarchy.get(0, "") if first_item_hierarchy else ""
        }

        for item in page_items:
            item_type = item.get("type", "")

            if item_type in ("title", "section_header"):
                # Save current section if it has content
                if current_section["content_parts"]:
                    current_section["content"] = "\n\n".join(current_section["content_parts"])
                    sections.append(current_section)

                # Start new section
                hierarchy = item.get("section_hierarchy", {})
                section_name = item.get("text", f"Sekcja na stronie {page_number}")
                chapter_name = ""
                if hierarchy:
                    min_level = min(hierarchy.keys())
                    chapter_name = hierarchy.get(0, hierarchy.get(min_level, ""))

                # Include the header text as the first content of the new section
                # This ensures sections with only headers are not lost
                header_text = item.get("text", "")
                initial_content = [header_text] if header_text else []

                current_section = {
                    "hierarchy": hierarchy,
                    "content_parts": initial_content,
                    "level": item.get("header_level", 0),
                    "section_name": section_name,
                    "chapter_name": chapter_name
                }

            elif item_type in ("content", "table", "other_content"):
                # Add content to current section
                text = item.get("text", "")
                if text:
                    current_section["content_parts"].append(text)
                    # Update hierarchy if not set
                    if not current_section["hierarchy"]:
                        current_section["hierarchy"] = item.get("section_hierarchy", {})
                    # Update chapter name if not set
                    if not current_section["chapter_name"] and current_section["hierarchy"]:
                        hierarchy = current_section["hierarchy"]
                        if hierarchy:
                            min_level = min(hierarchy.keys())
                            current_section["chapter_name"] = hierarchy.get(0, hierarchy.get(min_level, ""))

        # Don't forget the last section
        if current_section["content_parts"]:
            current_section["content"] = "\n\n".join(current_section["content_parts"])
            sections.append(current_section)

        # Log what we found
        logger.debug(f"Page {page_number}: grouped into {len(sections)} sections")
        for i, sec in enumerate(sections):
            content_len = len(sec.get("content", ""))
            logger.debug(f"  Section {i+1}: '{sec.get('section_name', 'unnamed')}' - {content_len} chars")

        return sections

    @staticmethod
    def _build_section_title(hierarchy: Dict[int, str]) -> str:
        """Build section title from hierarchy."""
        if not hierarchy:
            return "Dokument"
        sorted_levels = sorted(hierarchy.keys())
        return " > ".join(hierarchy[level] for level in sorted_levels)

    @staticmethod
    def _build_parent_context(hierarchy: Dict[int, str]) -> str:
        """Build parent context string from hierarchy (excluding the deepest level)."""
        if not hierarchy or len(hierarchy) <= 1:
            return ""
        sorted_levels = sorted(hierarchy.keys())
        # Exclude the last (deepest) level to get parent context
        parent_levels = sorted_levels[:-1]
        return " > ".join(hierarchy[level] for level in parent_levels)

    def _save_docling_debug_output(self, doc: Any, filename: str):
        """
        Save Docling document structure to a JSON file for debugging.

        Args:
            doc: Docling document object
            filename: Original filename for naming the debug file
        """
        try:
            DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            debug_data = {
                "filename": filename,
                "pages": defaultdict(list)
            }

            # Extract all items grouped by page
            for item, level in doc.iterate_items():
                page_number = self._extract_page_number(item)

                item_data = {
                    "level": level,
                    "label": str(item.label) if hasattr(item, 'label') else None,
                    "text": getattr(item, 'text', '')[:500] if hasattr(item, 'text') else None,
                    "page_no": page_number,
                    "prov": []
                }

                # Extract provenance data
                if hasattr(item, 'prov') and item.prov:
                    for prov in item.prov:
                        prov_data = {
                            "page_no": getattr(prov, 'page_no', None),
                            "bbox": None
                        }
                        if hasattr(prov, 'bbox'):
                            bbox = prov.bbox
                            if bbox:
                                prov_data["bbox"] = {
                                    "l": getattr(bbox, 'l', None),
                                    "t": getattr(bbox, 't', None),
                                    "r": getattr(bbox, 'r', None),
                                    "b": getattr(bbox, 'b', None),
                                }
                        item_data["prov"].append(prov_data)

                page_key = str(page_number if page_number else 0)
                debug_data["pages"][page_key].append(item_data)

            # Convert to regular dict for JSON serialization
            debug_data["pages"] = dict(debug_data["pages"])

            # Save to JSON file
            output_file = DEBUG_OUTPUT_DIR / f"{Path(filename).stem}_docling_debug.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved Docling debug output to: {output_file}")
            print(f"[DEBUG] Docling output saved to: {output_file}", flush=True)

        except Exception as e:
            logger.warning(f"Failed to save Docling debug output: {e}")
            print(f"[DEBUG] Failed to save Docling debug output: {e}", flush=True)

    @staticmethod
    def _extract_table_text(table_item: Any) -> str:
        """Extract text representation from a table item."""
        try:
            if hasattr(table_item, 'export_to_markdown'):
                return table_item.export_to_markdown()
            elif hasattr(table_item, 'text'):
                return table_item.text
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_page_number(item: Any) -> Optional[int]:
        """
        Extract the page number from Docling item's provenance data.

        Args:
            item: Docling item

        Returns:
            Page number (1-indexed), or None if not found.
        """
        try:
            if hasattr(item, 'prov') and item.prov:
                first_prov = item.prov[0]
                if hasattr(first_prov, 'page_no') and first_prov.page_no is not None:
                    return first_prov.page_no
        except Exception:
            pass
        return None

    def _generate_section_context(self, content: str) -> str:
        """
        Generate a short context with key information for retrieval.

        Args:
            content: The content of the section.

        Returns:
            A short context string with key information.
        """
        return generate_section_context(content, self._local_llm)


async def process_file_with_docling(
    file_path: Path,
    local_llm: Optional[str] = None
) -> List[DocumentChunk]:
    """
    Convenience function to process a file with Docling.

    Uses page-based, section-based chunking where:
    - Content is first split by pages
    - Each section on a page becomes a chunk
    - Sub-chapters are separate chunks with parent chapter context

    Args:
        file_path: Path to file
        local_llm: Optional Ollama model name for context generation

    Returns:
        List of document chunks
    """
    processor = DocumentProcessor(local_llm=local_llm)
    return await processor.process_document(file_path)
