import logging
import asyncio
from pathlib import Path
from docling.document_converter import DocumentConverter
from app.const import STAGING_DIR
from docling_core.types.doc import DocItemLabel
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from docling.chunking import HybridChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_milvus import Milvus
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from tempfile import mkdtemp
from langchain_core.documents import Document
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.vectorstores import InMemoryVectorStore
from app.services.qdrant import vector_store
# vector_store = InMemoryVectorStore(embeddings)

logger = logging.getLogger(__name__)

EXPORT_TYPE = ExportType.DOC_CHUNKS
EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3

def _sanitize_metadata(doc: Document) -> Document:
    """
    Convert Path objects in metadata to strings for Milvus compatibility.
    
    Args:
        doc: LangChain Document with potentially unsanitized metadata
        
    Returns:
        Document with sanitized metadata (Path objects converted to strings)
    """
    if not doc.metadata:
        return doc
    
    sanitized_metadata = {}
    for key, value in doc.metadata.items():
        if isinstance(value, Path):
            sanitized_metadata[key] = str(value)
        else:
            sanitized_metadata[key] = value
    
    doc.metadata = sanitized_metadata
    return doc


def _process_file_sync(file_id: str, filename: str | None = None) -> None:
    """
    Synchronous function that processes a file using docling.
    This runs in a thread pool to avoid blocking the event loop.
    
    Args:
        file_id: The UUID file identifier
        filename: Optional original filename for logging purposes
    """

    file_path = STAGING_DIR / file_id
    
    if not file_path.exists():
        logger.warning(f"File not found for file_id: {file_id} at path: {file_path}")
        return
    
    logger.info(f"Starting background processing for file_id: {file_id}, filename: {filename}")
    
    try:
        converter = DocumentConverter()

        loader = DoclingLoader(
            file_path=file_path,
            export_type=EXPORT_TYPE,
            chunker=HybridChunker(tokenizer=EMBED_MODEL_ID),
        )

        docs = loader.load()

        if EXPORT_TYPE == ExportType.DOC_CHUNKS:
            splits = docs
        elif EXPORT_TYPE == ExportType.MARKDOWN:

            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header_1"),
                    ("##", "Header_2"),
                    ("###", "Header_3"),
                ],
            )
            splits = [split for doc in docs for split in splitter.split_text(doc.page_content)]
        else:
            raise ValueError(f"Unexpected export type: {EXPORT_TYPE}")

        splits = [_sanitize_metadata(doc) for doc in splits]

        print('===========', splits)

        embedding = HuggingFaceEmbeddings(model_name=EMBED_MODEL_ID)

        vector_store

        # milvus_uri = str(Path(mkdtemp()) / "docling.db") 
        # vectorstore = Milvus.from_documents(
        #     documents=splits,
        #     embedding=embedding,
        #     collection_name="docling_demo",
        #     connection_args={"uri": milvus_uri},
        #     index_params={"index_type": "FLAT"},
        #     drop_old=True,
        # )

        # retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})

        # question_answer_chain = []

        # rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        # print(rag_chain)
        # rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        # llm = HuggingFaceEndpoint(
        #     repo_id=GEN_MODEL_ID,
        #     huggingfacehub_api_token=HF_TOKEN,
        # )


        # def clip_text(text, threshold=100):
        #     return f"{text[:threshold]}..." if len(text) > threshold else text
        
        
    except Exception as e:
        logger.error(f"Error processing file {file_id} in background: {str(e)}", exc_info=True)


async def process_file_background(file_id: str, filename: str | None = None) -> None:
    """
    Background job that loads and processes a file after it has been saved.
    This function runs after the response is sent to the user.
    Uses docling library to load and process the document.
    
    The blocking docling operations are run in a thread pool to avoid
    blocking the async event loop.
    
    Args:
        file_id: The UUID file identifier
        filename: Optional original filename for logging purposes
    """
    await asyncio.to_thread(_process_file_sync, file_id, filename)

