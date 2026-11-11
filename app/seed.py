"""Seed a demo account and a few public gallery generations.

Run after the app has created its tables:  python -m app.seed
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.engine import analyse, get_style, render_grid
from app.models import Generation, Image, User
from app.security import hash_password

DEMO_EMAIL = "demo@tasveer.pk"
DEMO_PASSWORD = "tasveer123"

# Prompts chosen to show off different styles and aspect ratios.
DEMO_PROMPTS = [
    ("a lone lighthouse on a stormy coast at night, cinematic", "cinematic", "16:9"),
    ("neon city street in the rain, cyberpunk", "cyberpunk", "3:2"),
    ("soft watercolor mountains at sunrise, pastel", "watercolor", "4:5"),
    ("minimal white studio product shot of a ceramic vase", "minimal", "1:1"),
    ("oil painting of a desert caravan at golden hour", "oil", "2:3"),
    ("anime girl on a rooftop under a bright blue sky", "anime", "9:16"),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                display_name="Demo Studio",
                password_hash=hash_password(DEMO_PASSWORD),
                credits=250,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"created demo user  {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"demo user exists   {DEMO_EMAIL}")

        made = 0
        for prompt, style_key, aspect in DEMO_PROMPTS:
            exists = db.scalar(
                select(Generation).where(Generation.prompt == prompt, Generation.user_id == user.id)
            )
            if exists:
                continue

            preset = get_style(style_key)
            plan = analyse(prompt)
            base_seed = plan.digest % (2**31 - 1)
            folder = settings.storage_dir / f"demo_{base_seed}"
            folder.mkdir(parents=True, exist_ok=True)

            results = render_grid(
                prompt=prompt,
                plan=plan,
                preset=preset,
                base_seed=base_seed,
                aspect=aspect,
                out_dir=folder,
                count=4,
                max_pixels=settings.max_output_pixels,
            )

            gen = Generation(
                user_id=user.id,
                prompt=prompt,
                negative_prompt="",
                style=preset.key,
                aspect_ratio=aspect,
                seed=base_seed,
                credits_spent=1,
                is_public=True,
                provider=settings.image_provider,
                created_at=datetime.now(UTC),
            )
            db.add(gen)
            db.flush()

            for i, r in enumerate(results):
                db.add(
                    Image(
                        generation_id=gen.id,
                        filename=f"{folder.name}/{r.path.name}",
                        width=r.width,
                        height=r.height,
                        seed=r.seed,
                        index=i,
                    )
                )
            db.commit()
            made += 1
            print(f"  + {style_key:<10} {aspect:<5} {prompt[:48]}")

        print(f"\nseeded {made} public generations")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
