#!/bin/bash
# Run Flask web application

cd /home/danladuke/Projects/DefiTracker
source venv/bin/activate
export PYTHONPATH=/home/danladuke/Projects/DefiTracker:$PYTHONPATH
python src/api/app.py

