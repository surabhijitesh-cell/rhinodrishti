"""
test_security_hardening_v43.py — login guess limit, token versioning,
upload content checks, and the server-side URL fetch guard.

Pure-function tests — no Mongo connection, network or LLM calls.

Run:  cd backend && python -m pytest tests/test_security_hardening_v43.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.auth import LoginLimiter, token_version_ok
from routers.documents import file_content_matches, is_public_http_url


def _resolver(ip):
    return lambda host, port: [(2, 1, 6, "", (ip, port))]


# ── login limiter ────────────────────────────────────────────────────────────

def test_limiter_locks_after_five_failures():
    lim = LoginLimiter()
    for i in range(4):
        lim.record_failure("a|1.1.1.1", 100 + i)
    assert lim.retry_after("a|1.1.1.1", 105) == 0
    lim.record_failure("a|1.1.1.1", 105)
    assert lim.retry_after("a|1.1.1.1", 106) > 0
    assert lim.retry_after("b|1.1.1.1", 106) == 0  # other key unaffected


def test_limiter_clears_on_success():
    lim = LoginLimiter()
    for i in range(5):
        lim.record_failure("a|x", i)
    lim.clear("a|x")
    assert lim.retry_after("a|x", 10) == 0


def test_limiter_expires_after_window():
    lim = LoginLimiter(window_s=900)
    for i in range(5):
        lim.record_failure("a|x", i)
    assert lim.retry_after("a|x", 500) > 0
    assert lim.retry_after("a|x", 905) == 0


def test_limiter_size_is_bounded():
    lim = LoginLimiter(max_keys=10)
    for i in range(50):
        lim.record_failure(f"u{i}|x", i)
    assert len(lim._fails) == 10
    assert "u49|x" in lim._fails and "u0|x" not in lim._fails


# ── token version ────────────────────────────────────────────────────────────

def test_token_version_matching_and_defaults():
    assert token_version_ok({}, {})                       # old token, old user
    assert token_version_ok({"tv": 2}, {"token_version": 2})
    assert not token_version_ok({"tv": 0}, {"token_version": 1})   # after logout
    assert not token_version_ok({}, {"token_version": 1})


# ── URL guard ────────────────────────────────────────────────────────────────

def test_url_guard_rejects_private_targets():
    for ip in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "0.0.0.0"):
        assert not is_public_http_url("http://example.com/x", _resolver(ip))


def test_url_guard_rejects_bad_schemes_and_mixed_results():
    assert not is_public_http_url("file:///etc/passwd", _resolver("8.8.8.8"))
    assert not is_public_http_url("ftp://example.com", _resolver("8.8.8.8"))
    mixed = lambda h, p: [(2, 1, 6, "", ("8.8.8.8", p)), (2, 1, 6, "", ("10.0.0.1", p))]
    assert not is_public_http_url("http://example.com", mixed)


def test_url_guard_accepts_public_ip():
    assert is_public_http_url("https://example.com/a", _resolver("93.184.216.34"))


# ── file content check ───────────────────────────────────────────────────────

def test_file_content_check():
    assert file_content_matches("pdf", b"%PDF-1.7 rest")
    assert not file_content_matches("pdf", b"<html>not a pdf</html>")
    assert file_content_matches("docx", b"PK\x03\x04rest")
    assert not file_content_matches("docx", b"%PDF-1.7")
    assert file_content_matches("txt", "héllo".encode("utf-8"))
    assert not file_content_matches("txt", b"\xff\xfe\x00bad")
