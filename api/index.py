"""Vercel Python Function entrypoint for RUMI Manager.

All /api/* requests are rewritten here by vercel.json. The original API path is
passed in the internal __rumi_path query parameter and reconstructed by app.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402,F401
