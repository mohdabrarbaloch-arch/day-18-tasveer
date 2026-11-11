# Setup

## Requirements

- Python 3.11 or newer
- Nothing else. No GPU, no API key, no database server.

SQLite is the default. Postgres is optional and only needed if you want to run
more than one worker.

## Local install

```bash
git clone https://github.com/mohdabrarbaloch-arch/day-18-tasveer
cd day-18-tasveer

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

## Configure

The app runs with zero configuration. If you want to change anything:

```bash
cp .env.example .env
```

Then edit `.env`. Every variable is documented in that file.

**The one you must change before going to production** is `SECRET_KEY`. The
default is a known string; anyone who has read this repo can forge a token with
it.

## Seed demo data

```bash
python -m app.seed
```

This creates:

- a demo account — `demo@tasveer.pk` / `tasveer123`, with 250 credits
- six public gallery pieces, one per style, so the gallery isn't empty

It is idempotent. Running it twice does not duplicate anything.

## Run

```bash
uvicorn app.main:app --reload
```

| URL | What |
|---|---|
| <http://127.0.0.1:8000> | the app |
| <http://127.0.0.1:8000/docs> | Swagger UI |
| <http://127.0.0.1:8000/redoc> | ReDoc |
| <http://127.0.0.1:8000/api/health> | health check |

## Docker

```bash
docker compose up --build
```

Brings up the app on 8000 and Postgres 16 on 5432. The compose file sets
`DATABASE_URL` so the app uses Postgres instead of SQLite.

To stop and wipe the database volume:

```bash
docker compose down -v
```

## Tests

```bash
pytest                    # 59 tests, ~80 seconds
pytest -q tests/test_prompt.py     # just the analyser, fast
ruff check .              # lint
ruff format --check .     # formatting
```

The test suite uses a temporary SQLite database and a temporary storage
directory, set up in `tests/conftest.py` before the app is imported. Your
development database is never touched.

## Troubleshooting

**`ImportError: email-validator is not installed`**
`pip install email-validator`. It is in `pyproject.toml`; this only happens if
you installed dependencies by hand.

**`RuntimeError: Directory 'static' does not exist`**
You are running from outside the project root. `cd` into `day-18-tasveer` first.

**Images render but the gallery is empty**
Run `python -m app.seed`. The gallery only shows generations with
`is_public = true`, and a fresh database has none.

**`402 Payment Required` when generating**
You are out of credits. Register a new account (60 free) or bump the demo user's
credits directly:

```bash
python -c "
from app.database import SessionLocal
from app.models import User
db = SessionLocal()
u = db.query(User).filter_by(email='demo@tasveer.pk').first()
u.credits = 500
db.commit()
print('credits:', u.credits)
"
```

**Rendering is slow**
It should be under a second. If it is not, check `MAX_OUTPUT_PIXELS` — a very
large value on a small machine will thrash. The default 4 MP is deliberate.
