from app.core.audit import purge_expired_logs, redact


def test_redact_sensitive_values():
    value = redact({"password": "secret", "Authorization": "Bearer abc", "query": "hello"})
    assert value == {"password": "[REDACTED]", "Authorization": "[REDACTED]", "query": "hello"}
