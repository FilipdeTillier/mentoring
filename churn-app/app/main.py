from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.routers import hello, chat

app = FastAPI(
    title="Churn App API",
    description="Demo FastAPI application showcasing best practices",
    version="0.1.0",
)

app.include_router(hello.router, prefix="/api", tags=["greetings"])
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "Welcome to Churn App API", "docs": "/docs"}
