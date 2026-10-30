from app.core.time import utc_now
from datetime import datetime, timedelta
from uuid import uuid4
from app.config import settings
from app.models.session import AuthSession
from app.core.security import create_access_token


def issue_session(db, user):
    session_id = str(uuid4())
    db.add(AuthSession(id=session_id, user_id=user.id,
                       expires_at=utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)))
    db.flush()
    return create_access_token({"sub": user.id, "jti": session_id})
