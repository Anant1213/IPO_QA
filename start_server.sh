#!/bin/bash
# Start script for Hybrid RAG system
# Uses clean virtual environment to avoid mutex issues

cd "$(dirname "$0")"

# Activate the fresh virtual environment
source fresh_venv/bin/activate

echo "🚀 Starting Hybrid RAG Server..."
echo "Using Python: $(which python3)"
echo "Torch version: $(python3 -c 'import torch; print(torch.__version__)')"

# Run the Flask application
python3 src/app.py
