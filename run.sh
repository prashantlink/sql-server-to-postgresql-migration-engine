#!/bin/bash
cd "$(dirname "$0")"
echo "Installing dependencies..."
pip install -r backend/requirements.txt -q
echo "Starting Migration Engine on http://localhost:8000"
cd backend
python main.py
