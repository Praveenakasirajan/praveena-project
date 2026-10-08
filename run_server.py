#!/usr/bin/env python
"""Simple script to run the FastAPI server."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    project_dir = Path(__file__).resolve().parent
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(project_dir),
    )
