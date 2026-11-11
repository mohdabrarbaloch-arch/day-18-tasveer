"""Public gallery: browse generations other people chose to share."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Generation
from app.routers.generations import _to_out
from app.schemas import GalleryPage, GenerationOut

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("", response_model=GalleryPage)
def gallery(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    style: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
) -> GalleryPage:
    """Paginated feed of public generations."""
    base = select(Generation).where(Generation.is_public.is_(True))
    count_stmt = select(func.count(Generation.id)).where(Generation.is_public.is_(True))

    if style:
        base = base.where(Generation.style == style.strip().lower())
        count_stmt = count_stmt.where(Generation.style == style.strip().lower())

    total = db.scalar(count_stmt) or 0

    stmt = (
        base.options(selectinload(Generation.images), selectinload(Generation.user))
        .order_by(Generation.created_at.desc(), Generation.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    items = [_to_out(g) for g in db.scalars(stmt).all()]

    return GalleryPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/{generation_id}", response_model=GenerationOut)
def gallery_item(generation_id: int, db: Session = Depends(get_db)) -> GenerationOut:
    gen = db.scalar(
        select(Generation)
        .where(Generation.id == generation_id, Generation.is_public.is_(True))
        .options(selectinload(Generation.images), selectinload(Generation.user))
    )
    if gen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not in the public gallery"
        )
    return _to_out(gen)
