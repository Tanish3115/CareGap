import pytest
from app.services.notification_provider import provider_for


@pytest.mark.parametrize("channel", ["in_app", "email", "sms", "whatsapp"])
def test_local_channel_adapters_never_claim_external_delivery(channel):
    receipt = provider_for(channel).deliver(
        message="CareGap: sign in to review your care item.", idempotency_key="synthetic-record:1:" + channel
    )
    assert receipt.mode == "local_mock" and receipt.status == "mock_delivered"
    assert receipt.provider == "local-" + channel + "-v1"


def test_channel_adapter_rejects_unsupported_channel_and_invalid_envelopes():
    with pytest.raises(ValueError):
        provider_for("external-unknown")
    with pytest.raises(ValueError):
        provider_for("email").deliver(message="", idempotency_key="test")
    with pytest.raises(ValueError):
        provider_for("sms").deliver(message="test", idempotency_key="")
