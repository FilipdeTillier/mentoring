from fastapi import APIRouter

from app.services.greeter import say_hello

router = APIRouter()


@router.get("/hello")
async def hello_endpoint():
    return say_hello()