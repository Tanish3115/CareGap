"""Exercise only the isolated local TLS rehearsal; do not change OS trust or app users."""

import http.cookiejar
import http.client
import json
import secrets
import ssl
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
compose = [
    "docker",
    "compose",
    "-f",
    "docker-compose.yml",
    "-f",
    "infra/staging/compose.yml",
    "--env-file",
    ".tools/staging.env",
]
ca = subprocess.run(
    [*compose, "exec", "-T", "caddy", "cat", "/data/caddy/pki/authorities/local/root.crt"],
    cwd=root,
    capture_output=True,
    check=True,
).stdout
ca_path = root / ".tools/staging-root-ca.pem"
ca_path.write_bytes(ca)
context = ssl.create_default_context(cafile=str(ca_path))


class LoopbackConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def connect_loopback(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
            if address != ("localhost", 3443):
                raise ValueError("The smoke client permits only this local rehearsal address")
            return socket.create_connection(("127.0.0.1", 3443), timeout, source_address)

        # Preserve HTTPSConnection's TLS hostname/SNI verification; avoid only the
        # measured Windows IPv6-to-IPv4 localhost TCP fallback delay.
        self._create_connection = connect_loopback


class LoopbackHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(LoopbackConnection, request, context=self._context)


jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    LoopbackHTTPSHandler(context=context),
    urllib.request.HTTPCookieProcessor(jar),
)


def call(method, path, body=None, expected=200, client=opener):
    encoded = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        "https://localhost:3443" + path,
        data=encoded,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "https://localhost:3443"},
    )
    try:
        response = client.open(request, timeout=15)
        status = response.status
        content = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        content = error.read()
    assert status == expected, f"{method} {path.split('?')[0]} returned {status}, expected {expected}"
    return json.loads(content) if content else None


latencies = []
for _ in range(10):
    start = time.perf_counter()
    call("GET", "/api/v1/health")
    latencies.append(time.perf_counter() - start)
password = secrets.token_urlsafe(24) + "A1!"
email = f"synthetic-tls-{uuid4().hex}@example.com"
call(
    "POST",
    "/api/v1/auth/register",
    dict(email=email, password=password, full_name="Synthetic TLS smoke patient", role="patient"),
    201,
)
call("POST", "/api/v1/auth/login", dict(email=email, password=password))
identity = call("GET", "/api/v1/auth/me")
assert any(
    cookie.name == "caregap_session" and cookie.secure and "HttpOnly" in cookie._rest for cookie in jar
)
patient_id = identity["patient"]["id"]
record = call(
    "POST",
    "/api/v1/clinical/records",
    dict(
        patient_id=patient_id,
        title="Synthetic TLS care record",
        occurred_on=datetime.now(timezone.utc).date().isoformat(),
        data=dict(kind="diagnosis", condition="SYNTHETIC TLS fixture"),
        reason="Isolated TLS smoke source check",
        source_checked=True,
    ),
    201,
)
assert call("GET", f"/api/v1/clinical/records?patient_id={patient_id}")[0]["id"] == record["id"]
other = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    LoopbackHTTPSHandler(context=context),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
)
other_email = f"synthetic-other-tls-{uuid4().hex}@example.com"
call(
    "POST",
    "/api/v1/auth/register",
    dict(email=other_email, password=password, full_name="Synthetic other TLS patient", role="patient"),
    201,
    other,
)
call("POST", "/api/v1/auth/login", dict(email=other_email, password=password), client=other)
call("GET", f"/api/v1/clinical/records?patient_id={patient_id}", expected=403, client=other)
call("POST", "/api/v1/auth/logout", expected=204)
call("GET", "/api/v1/auth/me", expected=401)
redis_code = "import redis,uuid; key='synthetic-smoke-'+uuid.uuid4().hex; a=redis.Redis(host='redis'); b=redis.Redis(host='redis'); assert a.incr(key)==1; a.expire(key,60); assert b.incr(key)==2; a.delete(key); print('Independent clients shared the Redis counter.')"
result = subprocess.run(
    [*compose, "exec", "-T", "backend", "python", "-c", redis_code], cwd=root, capture_output=True, check=True
)
assert "shared the Redis counter" in result.stdout.decode()
print(
    json.dumps(
        dict(
            mode="isolated_local_tls_rehearsal",
            transport="IPv4 loopback with verified localhost TLS/SNI",
            certificate_verified=True,
            secure_httponly_session=True,
            source_write_read=True,
            cross_patient_denied=True,
            logout_revoked=True,
            redis_shared_counter=True,
            health_requests=len(latencies),
            health_latency_median_ms=round(statistics.median(latencies) * 1000, 1),
            health_latency_max_ms=round(max(latencies) * 1000, 1),
            clinical_or_production_validation=False,
        ),
        indent=2,
    )
)
