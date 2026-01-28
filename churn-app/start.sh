#!/bin/bash

# Start the FastAPI backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Start Chainlit frontend
chainlit run front/app.py --host 0.0.0.0 --port 4001 &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
