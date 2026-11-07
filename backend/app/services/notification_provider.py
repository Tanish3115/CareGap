"""Channel adapter boundary. Local providers have no destinations or network IO."""

from dataclasses import dataclass
from typing import Literal, Protocol

Channel = Literal["in_app", "email", "sms", "whatsapp"]


@dataclass(frozen=True)
class DeliveryReceipt:
    provider: str
    mode: str
    status: str


class NotificationProvider(Protocol):
    def deliver(self, *, message: str, idempotency_key: str) -> DeliveryReceipt: ...


class LocalMockProvider:
    def __init__(self, channel: Channel):
        if channel not in ("in_app", "email", "sms", "whatsapp"):
            raise ValueError("Unsupported channel")
        self.channel = channel

    def deliver(self, *, message: str, idempotency_key: str):
        if not message or len(message) > 500 or not idempotency_key or len(idempotency_key) > 300:
            raise ValueError("Invalid local reminder envelope")
        return DeliveryReceipt(
            provider="local-" + self.channel + "-v1", mode="local_mock", status="mock_delivered"
        )


def provider_for(channel: Channel) -> NotificationProvider:
    return LocalMockProvider(channel)
