from datetime import datetime, timezone


def utc_now() -> datetime:
    """UTC without tzinfo, matching the existing timestamp-without-time-zone schema.

    API consumers must interpret these persisted timestamps as UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
