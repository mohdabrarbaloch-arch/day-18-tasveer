# Architecture

## What this is

Tasveer is an image generation service. You send a prompt, it sends back a grid
of four pictures. Around that core sits the boring-but-necessary scaffolding any
real product needs: accounts, credits, history, a public gallery, rate limits.

The interesting design decision is the renderer. It is **procedural, not
neural** — and that choice is deliberate, not a shortcut.

## System diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser                                                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  static/index.html + styles.css + app.js                       │  │
│  │  · Studio view (prompt, style chips, ratio chips, advanced)    │  │
│  │  · Gallery view (paginated public feed)                        │  │
│  │  · History strip, lightbox, auth modal                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  fetch()  ·  JSON  ·  Bearer JWT
┌───────────────────────────────▼──────────────────────────────────────┐
│  FastAPI                                                             │
│                                                                      │
│  middleware:  CORS  →  security headers  →  SlowAPI rate limit       │
│                                                                      │
│  routers/                                                            │
│    auth.py         POST /register  POST /login  GET /me              │
│    generations.py  POST /  GET /  GET /{id}  DELETE /{id}  /stats    │
│    gallery.py      GET /  GET /{id}                                  │
│                                                                      │
│  deps.py           bearer token → User (401 / 404 semantics)         │
│  schemas.py        bounded Pydantic models (the input contract)      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │                                               │
┌───────▼─────────────────┐                 ┌───────────▼──────────────┐
│  engine/                │                 │  SQLAlchemy 2.0          │
│                         │                 │                          │
│  prompt.py              │                 │  User                    │
│    tokenize → mood      │                 │    id, email, hash,      │
│    → composition        │                 │    credits, is_admin     │
│    → density            │                 │                          │
│    → digest (seed)      │                 │  Generation              │
│                         │                 │    prompt, style,        │
│  styles.py              │                 │    aspect, seed,         │
│    8 presets, each a    │                 │    is_public, provider   │
│    palette + render     │                 │                          │
│    params               │                 │  Image                   │
│                         │                 │    filename, w, h, seed  │
│  renderer.py            │                 │                          │
│    fBm noise            │                 │  SQLite (dev)            │
│    → domain warp        │                 │  Postgres (prod)         │
│    → palette map        │                 └──────────────────────────┘
│    → key light          │
│    → bloom              │                 ┌──────────────────────────┐
│    → vignette + grain   │                 │  storage/generated/      │
│    → PNG                │                 │    gen_{uid}_{seed}/     │
└─────────────────────────┘                 │      img_0..3.png        │
                                            │  served at /media/*      │
                                            └──────────────────────────┘
```

## The render pipeline, step by step

A generation request walks through five stages.

**1. Validate.** Pydantic rejects anything outside the contract: prompt under 3
or over 800 characters, unknown style, aspect ratio not in the whitelist, count
above 4, seed outside 32-bit range. A request that cannot be expressed cannot be
abused.

**2. Analyse the prompt.** `engine/prompt.py` turns free text into a
`PromptPlan`:

- **tokens** — lowercased words, stopwords and generic words ("photo", "render")
  stripped
- **mood** — 19 mood words each carry a `(hue, saturation, brightness)` nudge.
  "warm golden sunset" pushes hue positive; "cold icy winter" pushes it negative.
  They accumulate, then clamp to ±1.
- **composition** — "portrait"/"face"/"product" → `centered`;
  "landscape"/"mountain"/"city" → `horizon`; otherwise `scatter`
- **density** — grows with token count, capped at 0.95. A negative prompt
  containing "minimal" or "clean" pulls it back down.
- **digest** — SHA-256 of the normalised prompt, first 4 bytes as an int. This
  is the default seed, which is why the same prompt gives the same picture.

**3. Render.** `engine/renderer.py` builds the image in numpy:

```
gradient field (linear / radial / diagonal)
        ↓
fBm noise, 5-6 octaves, base cell count from density
        ↓
domain warp: sample the noise field at coordinates displaced by two
             other noise fields — this is what makes forms organic
        ↓
blend in ridged detail (1 - |2n-1|^1.6) for brush-stroke character
        ↓
map the 0-1 field through the style's palette (multi-stop gradient)
        ↓
blend 42% gradient / 58% texture
        ↓
directional key light (random angle per seed)
        ↓
bloom: blur the bright regions and add them back
        ↓
vignette (radial falloff) + film grain
        ↓
smoothstep contrast curve
        ↓
PNG
```

**4. Persist.** One `Generation` row, four `Image` rows, files on disk under
`storage/generated/gen_{user_id}_{seed}/`. The user's credit count drops by one
in the same transaction.

**5. Serve.** `/media/*` is a `StaticFiles` mount over the storage directory.
Filenames are namespaced by generation folder, so two users can never collide.

## Why procedural instead of diffusion

Three reasons, in order of importance:

**Honesty.** A diffusion model behind a fake API would mean either shipping a
broken demo or lying about what it does. This renderer produces a real image
from a real prompt, and the README says exactly what it is. No one is misled.

**Determinism.** Same prompt + same seed = byte-identical PNG. That is a
property diffusion models do not have (without extra work), and it makes the
"reuse seed" button meaningful and the test suite possible.

**Cost and latency.** Under a second on one CPU core, no GPU, no API key, no
per-image bill. A portfolio project that costs nothing to run is a project that
stays online.

The trade-off is real and worth stating: this does not understand "a red fox in
snow" the way a diffusion model does. It reads the *mood* of the words, not
their meaning. For abstract editorial art that is fine. For a photorealistic
fox it is not.

**The escape hatch.** `IMAGE_PROVIDER` in the config switches the backend. Set
it to `openai` or `replicate`, supply the key, and the same API surface delegates
to a hosted model. The schema, the credits, the gallery, the history — all
unchanged. That is the point of keeping the renderer behind a narrow interface.

## Data flow: one generation

```
POST /api/generations
  { prompt, style, aspect_ratio, seed?, count, is_public }
        │
        ├─ deps.get_current_user      → 401 if no/invalid token
        ├─ Pydantic validation        → 422 if out of contract
        ├─ credits check              → 402 if zero
        │
        ├─ style = payload.style or detect_style_from_prompt(prompt)
        ├─ plan  = analyse(prompt, negative_prompt)
        ├─ seed  = payload.seed or secrets.randbelow(2**31-1)
        │
        ├─ render_grid(count=4)       → 4 PNGs on disk
        │
        ├─ INSERT generation, 4 images
        ├─ UPDATE user.credits -= 1
        └─ COMMIT
        │
        └─ 201 { id, prompt, style, seed, images: [{url, w, h, seed}] }
```

## Security model

| Concern | How it is handled |
|---|---|
| Password storage | bcrypt, 12 rounds, via passlib |
| Session | JWT HS256, 24h expiry, `sub` = user id |
| Token in transit | `Authorization: Bearer`, never a cookie (no CSRF surface) |
| Account probing | login returns the same 401 for unknown email and wrong password |
| Resource enumeration | another user's private generation returns **404**, not 403 |
| Input bounds | every field has `min_length`/`max_length`/`ge`/`le` |
| Rate limiting | 20/min on generate, 120/min default, per IP |
| Headers | `nosniff`, `DENY` framing, referrer policy, permissions policy, HSTS in prod |
| Secrets | env only; `.env.example` documents every key, no defaults that work in prod |
| SQL injection | SQLAlchemy parameterised queries throughout |
| Path traversal | filenames are generated server-side, never taken from input |
| Memory exhaustion | `max_output_pixels` caps every render at 4 MP |

## Scaling notes

**Where it breaks first.** Rendering is CPU-bound and synchronous. One uvicorn
worker handles roughly 1-2 generations per second. Past that, requests queue.

**Fix 1 — more workers.** `uvicorn --workers 4` on a 4-core box. Trivial, gets
you 4-8/sec.

**Fix 2 — move rendering off the request path.** Push the job to a queue
(Celery + Redis, or RQ), return `202 Accepted` with a job id, and let the client
poll or subscribe over a WebSocket. The API stays responsive under load and the
renderer scales independently. This is the change I would make first in
production.

**Fix 3 — object storage.** Local disk does not survive a container restart and
does not share across replicas. Swap `StaticFiles` for S3/R2 with signed URLs.
The `Image.filename` column already stores a relative path, so the change is
contained to the URL builder.

**Database.** SQLite is fine for one process. The moment you run two workers,
move to Postgres — `docker-compose.yml` already has it. Add Alembic before the
first schema change in production; `create_all()` does not migrate.

**Caching.** The gallery is the hot read path and it changes slowly. A 30-second
cache on `GET /api/gallery` would cut database load substantially. Generation
results are already immutable, so they can be cached forever by id.

**Cost.** At 4 MP per image and 4 images per generation, storage grows at roughly
4-5 MB per generation. A 10 GB volume holds about 2,000 generations. Add a
retention policy or move to object storage before that matters.

## What I would build next

1. **Upscale endpoint** — the `Image.upscaled` column exists and is unused.
2. **Image-to-image** — accept a reference image, extract its palette, use it as
   the style. The renderer already takes a palette; this is a small change.
3. **WebSocket progress** — for the queue-based renderer, so the UI can show
   real progress instead of a spinner.
4. **Prompt library** — save and share prompts, not just results.
5. **Alembic** — before the first production schema change, not after.
