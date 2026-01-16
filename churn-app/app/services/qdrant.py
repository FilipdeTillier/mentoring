from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
import getpass
import os
from langchain_openai import OpenAIEmbeddings


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")


embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

QDRANT_COLLECTION_NAME = 'test'
PORT = 6333

client = QdrantClient(host='localhost', port=PORT)

vector_size = len(embeddings.embed_query("sample text"))

if not client.collection_exists(QDRANT_COLLECTION_NAME):
    client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )
vector_store = QdrantVectorStore(
    client=client,
    collection_name=QDRANT_COLLECTION_NAME,
    embedding=embeddings,
)