"""Bounded source selection. Providers cannot introduce clinical statements."""

from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel, ConfigDict, Field
from app.config import settings


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_keys: list[str] = Field(max_length=50)


class ProviderUnavailable(Exception):
    pass


def provider_status():
    return dict(
        mode=settings.SUMMARY_PROVIDER,
        reference=settings.SUMMARY_PROVIDER_REFERENCE,
        available=settings.SUMMARY_PROVIDER == "extractive" or settings.SUMMARY_PROVIDER_APPROVED,
        sends_source_data=settings.SUMMARY_PROVIDER == "http",
    )


def select_sources(facts):
    if settings.SUMMARY_PROVIDER == "extractive":
        return list(facts)
    if not settings.SUMMARY_PROVIDER_APPROVED:
        raise ProviderUnavailable()
    parts = urlsplit(settings.SUMMARY_PROVIDER_URL)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ProviderUnavailable()
    sources = {f"source-{index}": fact for index, fact in enumerate(facts)}
    payload = dict(
        schema_version="caregap-source-selection-v1",
        task="select_authorized_sources",
        sources=[
            dict(
                key=key,
                category=fact["category"],
                title=fact["title"],
                date=fact["date"],
                provenance=fact["provenance"],
                details=fact["details"],
            )
            for key, fact in sources.items()
        ],
    )
    headers = {"Content-Type": "application/json"}
    if settings.SUMMARY_PROVIDER_TOKEN.get_secret_value():
        headers["Authorization"] = "Bearer " + settings.SUMMARY_PROVIDER_TOKEN.get_secret_value()
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            with client.stream(
                "POST", settings.SUMMARY_PROVIDER_URL, json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ProviderUnavailable()
        result = Selection.model_validate_json(bytes(body))
        if len(set(result.source_keys)) != len(result.source_keys) or any(
            key not in sources for key in result.source_keys
        ):
            raise ProviderUnavailable()
        return [sources[key] for key in result.source_keys]
    except (httpx.HTTPError, ValueError, TypeError):
        raise ProviderUnavailable() from None
