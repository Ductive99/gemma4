#!/bin/bash
set -e
echo "Preparing Red Pen..."

if ! pgrep -x "ollama" > /dev/null
then
    echo "Ollama is not running. Starting it in the background..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
else
    echo "Ollama is already running."
fi

if [ -z "$SERPAPI_API_KEY" ]; then
    echo "Warning: SERPAPI_API_KEY is not set - claims will be checked with no evidence (UNVERIFIED)."
fi

if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting web app on http://localhost:8000"
uvicorn redpen.server:app --host 0.0.0.0 --port 8000
