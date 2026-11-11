"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level `app` (or `handler`) in this
file. Everything else is the same FastAPI app the local server runs.

One caveat worth knowing: Vercel's filesystem is read-only except for /tmp, and
/tmp does not persist between invocations. Generated images therefore vanish.
For a real deployment, point STORAGE_DIR at a mounted volume or swap the storage
layer for S3/R2 — see the README's deployment section.
"""

import os
import sys
from pathlib import Path

# Make the project root importable from inside the api/ directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Vercel gives us a writable /tmp and nothing else.
os.environ.setdefault("STORAGE_DIR", "/tmp/tasveer-generated")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tasveer.db")
os.environ.setdefault("ENVIRONMENT", "production")

from app.main import app  # noqa: E402

# Vercel's Python runtime accepts either name.
handler = app
