# API reference

Base URL: `http://127.0.0.1:8000`

All request and response bodies are JSON. Authenticated endpoints take
`Authorization: Bearer <token>`.

Interactive docs: `/docs` (Swagger) and `/redoc`.

---

## Authentication

### POST /api/auth/register

Create an account. Returns a token immediately — no email verification step.

**Body**

| Field | Type | Rules |
|---|---|---|
| `email` | string | valid email, unique |
| `display_name` | string | 2–80 characters |
| `password` | string | 8–128 characters, must mix letters and digits |

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","display_name":"You","password":"secret123"}'
```

**201 Created**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "you@example.com",
    "display_name": "You",
    "credits": 60,
    "is_admin": false,
    "created_at": "2026-11-11T19:00:00Z"
  }
}
```

**Errors**

| Code | When |
|---|---|
| 409 | email already registered |
| 422 | password too short, or all letters / all digits |

---

### POST /api/auth/login

**Body:** `{ "email": "...", "password": "..." }`

**200 OK** — same shape as register.

**401 Unauthorized** — wrong password *or* unknown email. The message is
identical for both, deliberately: it stops anyone probing which addresses have
accounts.

---

### GET /api/auth/me

Requires auth. Returns the current `UserOut`.

**401** if the token is missing, malformed, expired, or points at a deleted user.

---

## Generations

### POST /api/generations

Render a grid. Costs 1 credit.

**Body**

| Field | Type | Default | Rules |
|---|---|---|---|
| `prompt` | string | — | 3–800 chars, not blank |
| `negative_prompt` | string | `""` | max 400 chars |
| `style` | string \| null | auto | one of the 8 style keys |
| `aspect_ratio` | string | `"1:1"` | `1:1`, `3:2`, `2:3`, `16:9`, `9:16`, `4:5` |
| `seed` | int \| null | random | 0 – 2147483646 |
| `count` | int | 4 | 1–4 |
| `is_public` | bool | `false` | share to gallery |

```bash
curl -X POST http://127.0.0.1:8000/api/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "a lone lighthouse on a stormy coast at night, cinematic",
    "style": "cinematic",
    "aspect_ratio": "16:9",
    "count": 4
  }'
```

**201 Created**

```json
{
  "id": 7,
  "prompt": "a lone lighthouse on a stormy coast at night, cinematic",
  "negative_prompt": "",
  "style": "cinematic",
  "aspect_ratio": "16:9",
  "seed": 2071878112,
  "credits_spent": 1,
  "is_public": false,
  "provider": "local",
  "created_at": "2026-11-11T19:07:23Z",
  "author": "Demo Studio",
  "images": [
    {
      "id": 25,
      "filename": "gen_1_2071878112/img_0.png",
      "width": 1280,
      "height": 720,
      "seed": 2071878112,
      "index": 0,
      "upscaled": false,
      "url": "/media/gen_1_2071878112/img_0.png"
    }
  ]
}
```

**Errors**

| Code | When |
|---|---|
| 401 | no or invalid token |
| 402 | out of credits |
| 422 | prompt too short/blank, unknown style, bad ratio, count > 4 |
| 429 | more than 20 generations in a minute from one IP |
| 500 | the renderer itself failed (rare; the message says why) |

---

### GET /api/generations

Your own history, newest first.

**Query:** `limit` (1–100, default 20), `offset` (≥0, default 0)

**200 OK** — array of `GenerationOut`.

---

### GET /api/generations/{id}

One generation. Yours, or any public one.

**404** if it does not exist *or* belongs to someone else and is private. Not
403 — a 403 would confirm the id exists.

---

### DELETE /api/generations/{id}

Delete your own generation. Removes the rows and the PNGs from disk.

**204 No Content** on success. **404** if it is not yours.

---

### GET /api/generations/stats/summary

```json
{ "generations": 7, "images": 28, "credits": 249 }
```

---

## Gallery

### GET /api/gallery

Public generations, newest first.

**Query:** `page` (≥1, default 1), `page_size` (1–48, default 12), `style`
(optional filter)

```json
{
  "items": [ /* GenerationOut */ ],
  "total": 6,
  "page": 1,
  "page_size": 12,
  "has_more": false
}
```

---

### GET /api/gallery/{id}

One public generation. **404** if it is not public.

---

## Meta

### GET /api/health

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "development",
  "provider": "local",
  "styles": 8,
  "aspect_ratios": ["1:1", "3:2", "2:3", "16:9", "9:16", "4:5"]
}
```

### GET /api/styles

Every preset with its palette.

```json
[
  { "key": "cinematic", "label": "Cinematic",
    "palette": ["#0b1020", "#1b2a4a", "#c9762f", "#f2c14e", "#e8e3d9"] }
]
```

### GET /api/aspect-ratios

```json
{ "ratios": [ { "key": "1:1", "width": 1024, "height": 1024 } ] }
```

---

## Media

### GET /media/{path}

Serves a generated PNG. Public — no auth. Filenames are server-generated and
namespaced by generation folder, so they cannot be guessed or traversed.

`Content-Type: image/png`.

---

## Error format

Every error is `{ "detail": "..." }`. Validation errors (422) use FastAPI's
standard shape:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "prompt"],
      "msg": "String should have at least 3 characters",
      "input": "a"
    }
  ]
}
```

---

## Rate limits

| Scope | Limit |
|---|---|
| `POST /api/generations` | 20 / minute per IP |
| everything else | 120 / minute per IP |

Exceeding either returns **429** with `Retry-After: 60`.

---

## Security headers

Every response carries:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=()
X-Process-Time-ms: 12.4
```

In production (`ENVIRONMENT=production`) also:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```
