"""Tests for check implementations."""

from unittest.mock import patch, MagicMock
from gen_loop.checks import run_check


class TestShell:
    def test_success(self):
        r = run_check("shell", "echo hello", "")
        assert r.success and r.output == "hello"

    def test_failure(self):
        assert not run_check("shell", "false", "").success

    def test_criteria_match(self):
        assert run_check("shell", "echo 'status: OK'", "ok").success

    def test_criteria_miss(self):
        assert not run_check("shell", "echo 'status: ERROR'", "ok").success

    def test_timeout(self):
        r = run_check("shell", "sleep 60", "")
        assert not r.success and "timed out" in r.error.lower()


class TestFileExists:
    def test_exists(self, tmp_path):
        f = tmp_path / "yes.txt"
        f.write_text("hi")
        assert run_check("file_exists", str(f), "").success

    def test_missing(self, tmp_path):
        assert not run_check("file_exists", str(tmp_path / "no.txt"), "").success


class TestHttp:
    def test_success(self):
        import urllib.request
        mock = MagicMock()
        mock.status = 200
        mock.read.return_value = b'{"ok": true}'
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        with patch.object(urllib.request, "urlopen", return_value=mock):
            assert run_check("http", "http://localhost/health", "").success

    def test_error(self):
        import urllib.request
        import urllib.error
        with patch.object(urllib.request, "urlopen",
                          side_effect=urllib.error.HTTPError("", 503, "Down", {}, None)):
            r = run_check("http", "http://localhost/health", "")
            assert not r.success and "503" in r.output


class TestGrep:
    def test_found(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("Build completed OK")
        assert run_check("grep", f"completed::{f}", "").success

    def test_not_found(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("Still building")
        assert not run_check("grep", f"completed::{f}", "").success

    def test_bad_format(self):
        assert not run_check("grep", "no-separator", "").success


class TestHttpReadLimit:
    def test_reads_up_to_16384_bytes(self):
        """HTTP check reads up to HTTP_READ_LIMIT bytes."""
        from gen_loop.checks import HTTP_READ_LIMIT
        import urllib.request
        large_body = b"x" * 20000
        mock = MagicMock()
        mock.status = 200
        mock.read.return_value = large_body[:HTTP_READ_LIMIT]
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        with patch.object(urllib.request, "urlopen", return_value=mock):
            r = run_check("http", "http://localhost/large", "")
        assert r.success
        mock.read.assert_called_once_with(HTTP_READ_LIMIT)


class TestUnknown:
    def test_unknown_type(self):
        r = run_check("ftp", "x", "")
        assert not r.success and "Unknown" in r.error
