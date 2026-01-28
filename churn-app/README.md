# Churn App - FastAPI Demo

Run front end 
uv run chainlit run app.py --port 4000 

A demonstration FastAPI application showcasing best practices for building production-ready APIs with proper project structure, Docker containerization, and clean architecture.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Running Locally](#running-locally)
- [Docker Commands](#docker-commands)
- [API Endpoints](#api-endpoints)
- [How It Works](#how-it-works)

---

## 🏗️ Architecture Overview

This application follows a **layered architecture** pattern with clear separation of concerns:

```
┌─────────────────────────────────────┐
│         FastAPI Application         │
│            (app/main.py)            │
└─────────────┬───────────────────────┘
              │
              │ registers
              ▼
┌─────────────────────────────────────┐
│           API Routers               │
│        (app/routers/*.py)           │
│   - Define HTTP endpoints           │
│   - Handle request/response         │
└─────────────┬───────────────────────┘
              │
              │ uses
              ▼
┌─────────────────────────────────────┐
│          Services Layer             │
│       (app/services/*.py)           │
│   - Business logic                  │
│   - Data processing                 │
└─────────────┬───────────────────────┘
              │
              │ imports
              ▼
┌─────────────────────────────────────┐
│         Shared Library              │
│         (churn-lib)                 │
│   - Reusable utilities              │
│   - Data preprocessing              │
└─────────────────────────────────────┘
```

---

## 📁 Project Structure

```
churn-app/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI application entry point
│   ├── dependencies.py          # Dependency injection (reserved for DI)
│   ├── routers/
│   │   ├── __init__.py          # Router registry
│   │   └── hello.py             # Hello endpoint router
│   └── services/
│       ├── __init__.py          # Services registry
│       └── greeter.py           # Greeter business logic
├── pyproject.toml               # Project dependencies & config
├── uv.lock                      # Locked dependency versions
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── .dockerignore                # Docker build exclusions
└── README.md                    # This file
```

---

## 🚀 Running Locally

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Step 1: Install Dependencies

```bash
cd churn-app
uv sync
```

This will:
- Create a virtual environment in `.venv/`
- Install all dependencies from `pyproject.toml`
- Install the local `churn-lib` in editable mode

### Step 2: Run the Development Server

```bash
uv run uvicorn app.main:app --reload
```

Or with host/port configuration:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Access the API

- **API Base**: http://localhost:8000/
- **Hello Endpoint**: http://localhost:8000/api/hello
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🐳 Docker Commands

### Building the Docker Image

Build from the **parent directory** (to include `churn-lib`):

```bash
cd /path/to/uv-app-template
docker build -f churn-app/Dockerfile -t churn-app:latest .
```

Build with no cache (clean build):

```bash
docker build --no-cache -f churn-app/Dockerfile -t churn-app:latest .
```

### Running with Docker

Run the container:

```bash
docker run -p 8000:8000 churn-app:latest
```

Run in detached mode with auto-restart:

```bash
docker run -d \
  --name churn-app-container \
  -p 8000:8000 \
  --restart unless-stopped \
  churn-app:latest
```

### Using Docker Compose (Recommended)

Start the application:

```bash
cd churn-app
docker-compose up
```

Start in detached mode:

```bash
docker-compose up -d
```

Build and start:

```bash
docker-compose up --build
```

Stop the application:

```bash
docker-compose down
```

Stop and remove volumes:

```bash
docker-compose down -v
```

### Docker Management Commands

#### Container Management

```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# Stop a container
docker stop churn-app-container

# Start a stopped container
docker start churn-app-container

# Restart a container
docker restart churn-app-container

# Remove a container
docker rm churn-app-container

# Remove a running container (force)
docker rm -f churn-app-container

# View container logs
docker logs churn-app-container

# Follow container logs (real-time)
docker logs -f churn-app-container

# View last 100 lines of logs
docker logs --tail 100 churn-app-container

# Execute command in running container
docker exec -it churn-app-container bash

# Inspect container details
docker inspect churn-app-container

# View container resource usage
docker stats churn-app-container
```

#### Image Management

```bash
# List images
docker images

# List images with filter
docker images | grep churn-app

# Remove an image
docker rmi churn-app:latest

# Remove dangling images
docker image prune

# Remove all unused images
docker image prune -a

# View image history
docker history churn-app:latest

# Check image size
docker images churn-app:latest --format "{{.Size}}"
```

#### System Cleanup

```bash
# Remove all stopped containers
docker container prune

# Remove all unused networks
docker network prune

# Remove all unused volumes
docker volume prune

# Clean up everything (containers, networks, images, build cache)
docker system prune -a

# Show disk usage
docker system df
```

### Example Docker Workflow

Here's a complete workflow from build to deployment:

```bash
# 1. Navigate to project root
cd /path/to/uv-app-template

# 2. Build the image
docker build -f churn-app/Dockerfile -t churn-app:v1.0.0 .

# 3. Test the image locally
docker run -d --name churn-test -p 8000:8000 churn-app:v1.0.0

# 4. Check if it's running
docker ps

# 5. View logs
docker logs -f churn-test

# 6. Test the API
curl http://localhost:8000/api/hello

# 7. Access the container shell (if needed)
docker exec -it churn-test bash

# 8. Stop and remove test container
docker stop churn-test
docker rm churn-test

# 9. Deploy with Docker Compose
cd churn-app
docker-compose up -d

# 10. Monitor the application
docker-compose logs -f

# 11. Check health status
docker-compose ps

# 12. Update the application (rebuild)
docker-compose down
docker-compose up --build -d

# 13. Cleanup old images
docker image prune -f
```

---

## 📍 API Endpoints

| Method | Endpoint       | Description                           |
|--------|----------------|---------------------------------------|
| GET    | `/`            | Root endpoint with welcome message    |
| GET    | `/api/hello`   | Returns hello message with DataFrame  |
| GET    | `/docs`        | Interactive API documentation (Swagger UI) |
| GET    | `/redoc`       | Alternative API documentation (ReDoc) |

### Example Response from `/api/hello`

```json
{
  "message": "Hello from churn-app!",
  "dataframe": {
    "shape": [2, 2],
    "columns": ["A", "B"],
    "data": [
      {"A": 1, "B": 3},
      {"A": 2, "B": 4}
    ]
  }
}
```

---

## 🧩 How It Works

### Component Breakdown

#### 1. **Main Application** (`app/main.py`)

The entry point of the FastAPI application. It:
- Creates the FastAPI instance with metadata (title, description, version)
- Registers routers with prefixes and tags
- Defines global endpoints (like the root `/` endpoint)

```python
app = FastAPI(
    title="Churn App API",
    description="Demo FastAPI application",
    version="0.1.0",
)
app.include_router(hello.router, prefix="/api", tags=["greetings"])
```

**Key Concepts:**
- `FastAPI()`: Creates the ASGI application
- `include_router()`: Registers route collections from router modules
- `prefix="/api"`: All routes in this router are prefixed with `/api`
- `tags=["greetings"]`: Groups endpoints in API docs

---

#### 2. **Routers** (`app/routers/hello.py`)

Routers define HTTP endpoints and handle request/response logic. They:
- Define API routes using decorators (`@router.get()`, `@router.post()`, etc.)
- Handle HTTP methods (GET, POST, PUT, DELETE)
- Validate request data
- Call services to perform business logic
- Return responses to clients

```python
from fastapi import APIRouter
from app.services.greeter import say_hello

router = APIRouter()

@router.get("/hello")
async def hello_endpoint():
    return say_hello()
```

**Key Concepts:**
- `APIRouter()`: Creates a modular router (like a sub-application)
- `@router.get("/hello")`: Decorator that registers a GET endpoint at `/hello`
- `async def`: Asynchronous endpoint (can use `await` for async operations)
- The router imports and calls the service layer

**Why separate routers?**
- **Modularity**: Each router handles a specific domain (users, products, etc.)
- **Reusability**: Routers can be included in multiple applications
- **Organization**: Keeps endpoints organized by feature
- **Testing**: Easier to test individual router modules

---

#### 3. **Services** (`app/services/greeter.py`)

Services contain the business logic and data processing. They:
- Implement core application functionality
- Process data
- Interact with databases, external APIs, or libraries
- Return structured data to routers
- Are independent of HTTP concerns

```python
from churn_lib.preprocessing import preprocess

def say_hello() -> dict:
    df = preprocess()

    return {
        "message": "Hello from churn-app!",
        "dataframe": {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records")
        }
    }
```

**Key Concepts:**
- Pure Python functions (no FastAPI dependencies)
- Business logic separated from HTTP layer
- Returns Python dictionaries (converted to JSON by FastAPI)
- Imports from shared library (`churn-lib`)

**Why separate services?**
- **Testability**: Can be tested without HTTP requests
- **Reusability**: Same logic can be used by CLI, background tasks, etc.
- **Maintainability**: Business logic changes don't affect API structure
- **Single Responsibility**: Each service has one clear purpose

---

#### 4. **Dependencies** (`app/dependencies.py`)

Currently empty but reserved for **Dependency Injection** (DI). In larger applications, this file would contain:
- Database connection providers
- Authentication/authorization dependencies
- Configuration providers
- Shared resources (caching, logging, etc.)

**Example of what could go here:**

```python
from fastapi import Depends
from typing import Annotated

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DatabaseDep = Annotated[Session, Depends(get_db)]
```

**Why use dependencies?**
- **Resource Management**: Automatic cleanup of connections
- **Code Reuse**: Share common logic across endpoints
- **Testing**: Easy to mock dependencies
- **Inversion of Control**: Dependencies are injected, not created

---

#### 5. **Shared Library** (`churn-lib`)

A separate Python package containing reusable utilities:
- Data preprocessing functions
- ML models
- Common utilities
- Domain-specific logic

Located at `../churn-lib/src/churn_lib/preprocessing.py`:

```python
import pandas as pd

def preprocess():
    print("Preprocessing data...")
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    return df
```

**Why a separate library?**
- **Reusability**: Can be used by multiple apps (churn-app, training scripts, etc.)
- **Versioning**: Library can be versioned independently
- **Distribution**: Can be published to PyPI
- **Development**: Editable install allows live updates during development

---

### Communication Flow

Here's how a request flows through the application:

```
1. HTTP Request: GET /api/hello
         ↓
2. FastAPI Router (hello.py)
   - Matches route: @router.get("/hello")
   - Calls: hello_endpoint()
         ↓
3. Router calls Service (greeter.py)
   - Executes: say_hello()
         ↓
4. Service calls Library (churn-lib)
   - Executes: preprocess()
   - Gets DataFrame: pd.DataFrame({"A": [1, 2], "B": [3, 4]})
         ↓
5. Service processes data
   - Converts DataFrame to dict
   - Builds response dictionary
         ↓
6. Router returns response
   - FastAPI serializes dict to JSON
         ↓
7. HTTP Response: JSON payload
```

**Detailed Example:**

```
Client Request:
  GET http://localhost:8000/api/hello

↓ [FastAPI receives request]

↓ [main.py] Router prefix "/api" + route "/hello"

↓ [hello.py] Matches @router.get("/hello")

↓ [hello.py] Calls say_hello() service

↓ [greeter.py] Calls preprocess() from churn-lib

↓ [preprocessing.py] Creates DataFrame

↓ [greeter.py] Converts DataFrame to dict structure

↓ [hello.py] Returns dict to FastAPI

↓ [FastAPI] Converts dict to JSON, adds headers

↓ Client Response:
  {
    "message": "Hello from churn-app!",
    "dataframe": {...}
  }
```

---

### Design Patterns Used

#### 1. **Layered Architecture**
- Presentation Layer (Routers) → Business Logic Layer (Services) → Data Layer (Library)
- Each layer has a specific responsibility
- Changes in one layer don't affect others

#### 2. **Separation of Concerns**
- HTTP handling (routers)
- Business logic (services)
- Data utilities (library)
- Each component has one job

#### 3. **Dependency Inversion**
- High-level modules (routers) depend on abstractions (services)
- Low-level modules (library) provide implementations
- Makes testing and refactoring easier

#### 4. **Modular Design**
- Routers are independent modules
- Services are independent functions
- Library is a separate package
- Easy to add/remove features

---

## 🔧 Development Tips

### Adding a New Endpoint

1. Create or update a router in `app/routers/`
2. Define the endpoint with `@router.get()`, `@router.post()`, etc.
3. Create service function in `app/services/`
4. Register router in `app/main.py`

Example:

```python
# app/routers/users.py
from fastapi import APIRouter
from app.services.user_service import get_all_users

router = APIRouter()

@router.get("/users")
async def list_users():
    return get_all_users()

# app/main.py
from app.routers import users
app.include_router(users.router, prefix="/api", tags=["users"])
```

### Using Dependencies

```python
# app/dependencies.py
def get_current_user():
    # Authentication logic
    return {"user_id": 123}

# app/routers/hello.py
from fastapi import Depends
from app.dependencies import get_current_user

@router.get("/hello")
async def hello_endpoint(user: dict = Depends(get_current_user)):
    return {"message": f"Hello user {user['user_id']}"}
```

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [uv Package Manager](https://github.com/astral-sh/uv)
- [Docker Documentation](https://docs.docker.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

## 📝 License

This is a demo project for educational purposes.
