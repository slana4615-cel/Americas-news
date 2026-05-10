#!/usr/bin/env python3
"""
Daily Americas News Brief - compatibility entry point.

The GitHub Actions workflow uses fetch_news.py directly. This wrapper is kept
for users who still call the legacy entry point.
"""

from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("fetch_news.py")), run_name="__main__")
