#!/usr/bin/env python
"""
Celery Worker Entry Point
Starts the Celery worker for background task processing
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.workers.celery_app import celery_app, celery_worker

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Celery Worker for Document Intelligence Platform")
    print("=" * 60)
    
    # Run the worker
    celery_worker()