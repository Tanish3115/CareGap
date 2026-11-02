from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI.get_secret_value(),
)
