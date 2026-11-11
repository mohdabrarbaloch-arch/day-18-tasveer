"""Rate limiter shared across routers.

SlowAPI wraps the app; routers import this single instance so limits are
declared next to the route they protect.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri="memory://",
)
