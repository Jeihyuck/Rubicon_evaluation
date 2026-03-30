#!/usr/bin/env python3
"""CLI entry point.

Usage::

    python run.py

All configuration is read from environment variables (or ``.env``).
"""
from __future__ import annotations

import sys

from app.main import run

if __name__ == "__main__":
    sys.exit(run())
