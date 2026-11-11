"""Generation routes: create a grid, list your history, fetch one, delete."""

import contextlib
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.engine import analyse, detect_style_from_prompt, get_style, render_grid
from app.models import Generation, Image, User
from app.schemas import GenerateRequest, GenerationOut, ImageOut
from app.services.limiter import limiter

router = APIRouter(prefix="/api/generations", tags=["generations"])


def _image_url(filename: str) -> str:
    return f"/media/{filename}"


def _to_out(gen: Generation) -> GenerationOut:
    out = GenerationOut.model_validate(gen)
    out.images = [
        ImageOut(
            id=img.id,
            filename=img.filename,
            width=img.width,
            height=img.height,
            seed=img.seed,
            index=img.index,
            upscaled=img.upscaled,
            url=_image_url(img.filename),
        )
        for img in sorted(gen.images, key=lambda i: i.index)
    ]
    out.author = gen.user.display_name if gen.user else ""
    return out


@router.post("", response_model=GenerationOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_generate)
def create_generation(
    request: Request,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> GenerationOut:
    """Render a grid of images for a prompt and charge the user one credit."""
    if current.credits < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Out of credits. Top up to keep generating.",
        )

    style_key = payload.style or detect_style_from_prompt(payload.prompt)
    preset = get_style(style_key)
    plan = analyse(payload.prompt, payload.negative_prompt)

    base_seed = payload.seed if payload.seed is not None else secrets.randbelow(2**31 - 1)

    # Each generation gets its own folder so filenames never collide.
    folder = settings.storage_dir / f"gen_{current.id}_{base_seed}"
    folder.mkdir(parents=True, exist_ok=True)

    try:
        results = render_grid(
            prompt=payload.prompt,
            plan=plan,
            preset=preset,
            base_seed=base_seed,
            aspect=payload.aspect_ratio,
            out_dir=folder,
            count=payload.count,
            max_pixels=settings.max_output_pixels,
        )
    except Exception as exc:  # noqa: BLE001 — surface a clean 500, not a stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rendering failed: {exc}",
        ) from exc

    gen = Generation(
        user_id=current.id,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        style=preset.key,
        aspect_ratio=payload.aspect_ratio,
        seed=base_seed,
        credits_spent=1,
        is_public=payload.is_public,
        provider=settings.image_provider,
    )
    db.add(gen)
    db.flush()  # assign gen.id before creating images

    for i, result in enumerate(results):
        db.add(
            Image(
                generation_id=gen.id,
                filename=f"{folder.name}/{result.path.name}",
                width=result.width,
                height=result.height,
                seed=result.seed,
                index=i,
            )
        )

    current.credits -= 1
    db.commit()
    db.refresh(gen)

    return _to_out(gen)


@router.get("", response_model=list[GenerationOut])
def my_generations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[GenerationOut]:
    """Your own generation history, newest first."""
    stmt = (
        select(Generation)
        .where(Generation.user_id == current.id)
        .options(selectinload(Generation.images), selectinload(Generation.user))
        .order_by(Generation.created_at.desc(), Generation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_out(g) for g in db.scalars(stmt).all()]


@router.get("/{generation_id}", response_model=GenerationOut)
def get_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> GenerationOut:
    gen = db.scalar(
        select(Generation)
        .where(Generation.id == generation_id)
        .options(selectinload(Generation.images), selectinload(Generation.user))
    )
    # 404 rather than 403 for someone else's private generation — don't confirm
    # that the id exists at all.
    if gen is None or (gen.user_id != current.id and not gen.is_public):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
    return _to_out(gen)


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    gen = db.scalar(
        select(Generation)
        .where(Generation.id == generation_id)
        .options(selectinload(Generation.images))
    )
    if gen is None or gen.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")

    # Remove the files from disk too, so storage doesn't grow forever.
    for img in gen.images:
        path = settings.storage_dir / img.filename
        # A missing file must never block the delete.
        with contextlib.suppress(OSError):
            Path(path).unlink(missing_ok=True)

    db.delete(gen)
    db.commit()


@router.get("/stats/summary")
def stats(db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Small dashboard summary for the signed-in user."""
    total = db.scalar(select(func.count(Generation.id)).where(Generation.user_id == current.id))
    images = db.scalar(
        select(func.count(Image.id))
        .join(Generation, Image.generation_id == Generation.id)
        .where(Generation.user_id == current.id)
    )
    return {
        "generations": total or 0,
        "images": images or 0,
        "credits": current.credits,
    }
