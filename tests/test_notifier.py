"""Tests for notification delivery."""

import json
import pytest
from unittest.mock import patch, MagicMock
from gen_loop.store import LoopStore
from gen_loop.notifier import Notifier, ROTATION_SIZE_BYTES
from gen_loop.checks import CheckResult


@pytest.fixture
def store(tmp_path):
    return LoopStore(tmp_path / "loop-store")


@pytest.fixture
def notifier(tmp_path):
    return Notifier(tmp_path / "loop-store", default_method="file")


class TestFileNotifier:
    def test_writes_jsonl(self, store, notifier):
        entry = store.create(task="Notify me")
        result = CheckResult(success=True, output="done")
        notifier.notify(entry, "completed", result)

        lines = notifier.notifications_file.read_text().strip().split("\n")
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["loop_id"] == "loop-001"
        assert payload["event"] == "completed"
        assert payload["task"] == "Notify me"

    def test_multiple_notifications(self, store, notifier):
        e1 = store.create(task="First")
        e2 = store.create(task="Second")
        notifier.notify(e1, "completed")
        notifier.notify(e2, "failed")

        lines = notifier.notifications_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_includes_output(self, store, notifier):
        entry = store.create(task="With output")
        result = CheckResult(success=False, output="Connection refused", error="refused")
        notifier.notify(entry, "failed", result)

        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert "Connection refused" in payload["output"]


class TestStderrNotifier:
    def test_logs_to_stderr(self, store, notifier, capsys):
        store.create(task="Log me")
        notifier._notify_stderr({
            "loop_id": "loop-001", "event": "completed", "task": "Log me",
        })
        captured = capsys.readouterr()
        assert "loop-001" in captured.err
        assert "completed" in captured.err


class TestWebhookRetry:
    def test_webhook_success_first_try(self, store, notifier):
        """Webhook succeeds on first attempt."""
        import urllib.request
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        with patch.object(urllib.request, "urlopen", return_value=mock):
            result = notifier._notify_webhook("http://example.com/hook", {"test": True})
        assert result is True

    def test_webhook_retry_then_succeed(self, store, notifier):
        """Webhook fails first attempt, succeeds on retry."""
        import urllib.request
        mock_ok = MagicMock()
        mock_ok.__enter__ = lambda s: s
        mock_ok.__exit__ = MagicMock(return_value=False)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("refused")
            return mock_ok

        with patch.object(urllib.request, "urlopen", side_effect=side_effect):
            with patch("gen_loop.notifier.time.sleep"):  # Skip actual sleep
                result = notifier._notify_webhook("http://example.com/hook", {"test": True})
        assert result is True
        assert call_count == 2

    def test_webhook_all_retries_fail(self, store, notifier):
        """Webhook fails all 3 attempts, returns False."""
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                result = notifier._notify_webhook("http://example.com/hook", {"test": True})
        assert result is False

    def test_webhook_fallback_to_file(self, store, notifier):
        """When webhook-only fails, notification falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Webhook fail")
        entry["notification"] = {"method": "webhook", "webhookUrl": "http://example.com/hook"}

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        # Should have fallen back to file
        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_webhook_fallback"] is True

    def test_all_method_sends_both(self, store, notifier):
        """Method 'all' sends to file and attempts webhook."""
        import urllib.request
        entry = store.create(task="All notify")
        entry["notification"] = {"method": "all", "webhookUrl": "http://example.com/hook"}

        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        with patch.object(urllib.request, "urlopen", return_value=mock):
            notifier.notify(entry, "completed")

        # File notification should exist
        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert "_webhook_fallback" not in payload


class TestSlackNotifier:
    def test_slack_success(self, store, notifier):
        """Slack notification sends Block Kit payload."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "slack",
            "slackWebhookUrl": "https://hooks.slack.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        body = captured_data["body"]
        assert "blocks" in body
        assert body["blocks"][0]["type"] == "header"
        assert "COMPLETED" in body["blocks"][0]["text"]["text"]

    def test_slack_contains_loop_info(self, store, notifier):
        """Slack blocks include loop ID, task, and attempt count."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "slack",
            "slackWebhookUrl": "https://hooks.slack.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        fields_text = json.dumps(captured_data["body"]["blocks"][1]["fields"])
        assert "loop-001" in fields_text
        assert "Build server" in fields_text

    def test_slack_retry_and_fallback(self, store, notifier):
        """Slack failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Slack fail")
        entry["notification"] = {
            "method": "slack",
            "slackWebhookUrl": "https://hooks.slack.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_slack_fallback"] is True

    def test_all_method_includes_slack(self, store, notifier):
        """Method 'all' sends to file + webhook + slack."""
        import urllib.request
        call_count = {"value": 0}

        def count_calls(req, **kwargs):
            call_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_calls):
            notifier.notify(entry, "completed")

        assert call_count["value"] == 2  # webhook + slack
        assert notifier.notifications_file.exists()

    def test_build_slack_blocks_structure(self, notifier):
        """Verify Block Kit payload structure."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_slack_blocks(payload)
        assert "blocks" in result
        assert len(result["blocks"]) >= 3  # header, section, context
        assert result["blocks"][0]["type"] == "header"
        assert result["blocks"][-1]["type"] == "context"

    def test_build_slack_blocks_with_output(self, notifier):
        """Block Kit includes output section when present."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_slack_blocks(payload)
        assert len(result["blocks"]) == 4  # header, section, output, context
        assert "build failed" in result["blocks"][2]["text"]["text"]


class TestTelegramNotifier:
    def test_telegram_success(self, store, notifier):
        """Telegram notification sends HTML message to Bot API."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "telegram",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "api.telegram.org/bot123:ABC/sendMessage" in captured_data["url"]
        body = captured_data["body"]
        assert body["chat_id"] == "-100999"
        assert body["parse_mode"] == "HTML"
        assert "COMPLETED" in body["text"]

    def test_telegram_contains_loop_info(self, store, notifier):
        """Telegram message includes loop ID, task, and attempt count."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "telegram",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        text = captured_data["body"]["text"]
        assert "loop-001" in text
        assert "Build server" in text

    def test_telegram_retry_and_fallback(self, store, notifier):
        """Telegram failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Telegram fail")
        entry["notification"] = {
            "method": "telegram",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_telegram_fallback"] is True

    def test_all_method_includes_telegram(self, store, notifier):
        """Method 'all' sends to file + webhook + slack + telegram."""
        import urllib.request
        call_count = {"value": 0}

        def count_calls(req, **kwargs):
            call_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_calls):
            notifier.notify(entry, "completed")

        assert call_count["value"] == 3  # webhook + slack + telegram
        assert notifier.notifications_file.exists()

    def test_build_telegram_message_structure(self, notifier):
        """Verify HTML message structure."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_telegram_message(payload)
        assert "<b>Loop COMPLETED</b>" in result
        assert "<code>loop-042</code>" in result
        assert "Check deployment" in result
        assert "gen-loop-mcp" in result

    def test_build_telegram_message_with_output(self, notifier):
        """HTML message includes output section when present."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_telegram_message(payload)
        assert "<pre>" in result
        assert "build failed" in result


class TestDiscordNotifier:
    def test_discord_success(self, store, notifier):
        """Discord notification sends embed payload."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "discord",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        body = captured_data["body"]
        assert "embeds" in body
        assert len(body["embeds"]) == 1
        assert "COMPLETED" in body["embeds"][0]["title"]

    def test_discord_contains_loop_info(self, store, notifier):
        """Discord embed fields include loop ID and task."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "discord",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        fields_text = json.dumps(captured_data["body"]["embeds"][0]["fields"])
        assert "loop-001" in fields_text
        assert "Build server" in fields_text

    def test_discord_retry_and_fallback(self, store, notifier):
        """Discord failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Discord fail")
        entry["notification"] = {
            "method": "discord",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_discord_fallback"] is True

    def test_all_method_includes_discord(self, store, notifier):
        """Method 'all' sends to file + webhook + slack + telegram + discord."""
        import urllib.request
        call_count = {"value": 0}

        def count_calls(req, **kwargs):
            call_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_calls):
            notifier.notify(entry, "completed")

        assert call_count["value"] == 4  # webhook + slack + telegram + discord
        assert notifier.notifications_file.exists()

    def test_build_discord_embed_structure(self, notifier):
        """Verify embed payload structure."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_discord_embed(payload)
        assert "embeds" in result
        embed = result["embeds"][0]
        assert "COMPLETED" in embed["title"]
        assert embed["color"] == 0x2ECC71  # green
        assert len(embed["fields"]) == 4
        assert "gen-loop-mcp" in embed["footer"]["text"]

    def test_build_discord_embed_with_output(self, notifier):
        """Embed includes description with output when present."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_discord_embed(payload)
        embed = result["embeds"][0]
        assert "description" in embed
        assert "build failed" in embed["description"]
        assert "```" in embed["description"]


class TestTeamsNotifier:
    def test_teams_success(self, store, notifier):
        """Teams notification sends Adaptive Card payload."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "teams",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        body = captured_data["body"]
        assert body["type"] == "message"
        assert "attachments" in body
        assert len(body["attachments"]) == 1
        assert body["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"

    def test_teams_contains_loop_info(self, store, notifier):
        """Teams Adaptive Card FactSet includes loop ID, task, and attempts."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "teams",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        card_body = captured_data["body"]["attachments"][0]["content"]["body"]
        facts_text = json.dumps(card_body)
        assert "loop-001" in facts_text
        assert "Build server" in facts_text

    def test_teams_retry_and_fallback(self, store, notifier):
        """Teams failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Teams fail")
        entry["notification"] = {
            "method": "teams",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_teams_fallback"] is True

    def test_all_method_includes_teams(self, store, notifier):
        """Method 'all' sends to file + webhook + slack + telegram + discord + teams."""
        import urllib.request
        call_count = {"value": 0}

        def count_calls(req, **kwargs):
            call_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_calls):
            notifier.notify(entry, "completed")

        assert call_count["value"] == 5  # webhook + slack + telegram + discord + teams
        assert notifier.notifications_file.exists()

    def test_build_teams_card_structure(self, notifier):
        """Verify Adaptive Card payload structure."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_teams_card(payload)
        assert result["type"] == "message"
        assert len(result["attachments"]) == 1
        attachment = result["attachments"][0]
        assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
        card = attachment["content"]
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.2"
        assert card["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
        # Body: Container (header) + FactSet + TextBlock (footer)
        assert len(card["body"]) >= 3
        assert card["body"][0]["type"] == "Container"
        assert card["body"][0]["style"] == "good"  # completed = good
        assert card["body"][1]["type"] == "FactSet"

    def test_build_teams_card_with_output(self, notifier):
        """Adaptive Card includes monospace output block when present."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_teams_card(payload)
        card_body = result["attachments"][0]["content"]["body"]
        # Should have 4 elements: Container, FactSet, output TextBlock, footer TextBlock
        assert len(card_body) == 4
        output_block = card_body[2]
        assert output_block["type"] == "TextBlock"
        assert output_block["fontType"] == "Monospace"
        assert "build failed" in output_block["text"]


class TestNtfyNotifier:
    def test_ntfy_success(self, store, notifier):
        """Ntfy notification sends JSON with topic and title."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "ntfy",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "ntfy.sh" in captured_data["url"]
        body = captured_data["body"]
        assert body["topic"] == "gen-loop-alerts"
        assert "COMPLETED" in body["title"]

    def test_ntfy_contains_loop_info(self, store, notifier):
        """Ntfy message includes loop ID, task, and attempts."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "ntfy",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        message = captured_data["body"]["message"]
        assert "loop-001" in message
        assert "Build server" in message

    def test_ntfy_retry_and_fallback(self, store, notifier):
        """Ntfy failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Ntfy fail")
        entry["notification"] = {
            "method": "ntfy",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_ntfy_fallback"] is True

    def test_all_method_includes_ntfy(self, store, notifier):
        """Method 'all' sends to file + webhook + slack + telegram + discord + teams + ntfy."""
        import urllib.request
        call_count = {"value": 0}

        def count_calls(req, **kwargs):
            call_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_calls):
            notifier.notify(entry, "completed")

        assert call_count["value"] == 6  # webhook + slack + telegram + discord + teams + ntfy
        assert notifier.notifications_file.exists()

    def test_build_ntfy_message_structure(self, notifier):
        """Verify ntfy JSON message structure."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_ntfy_message(payload)
        assert "COMPLETED" in result["title"]
        assert result["priority"] == 3  # default for completed
        assert "white_check_mark" in result["tags"]
        assert "loop" in result["tags"]
        assert "loop-042" in result["message"]
        assert "Check deployment" in result["message"]

    def test_build_ntfy_message_with_output(self, notifier):
        """Ntfy message includes output text when present."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_ntfy_message(payload)
        assert result["priority"] == 5  # urgent for failed
        assert "x" in result["tags"]
        assert "build failed" in result["message"]


class TestMatrixNotifier:
    def test_matrix_success(self, store, notifier):
        """Matrix notification sends PUT to homeserver with Bearer auth."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["method"] = req.get_method()
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            captured_data["auth"] = req.get_header("Authorization")
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "matrix",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_test_token_xyz",
            "matrixRoomId": "!abc123:matrix.example.com",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "matrix.example.com/_matrix/client/v3/rooms" in captured_data["url"]
        assert "!abc123:matrix.example.com" in captured_data["url"]
        assert captured_data["method"] == "PUT"
        assert captured_data["auth"] == "Bearer syt_test_token_xyz"
        body = captured_data["body"]
        assert body["msgtype"] == "m.text"
        assert "COMPLETED" in body["body"]

    def test_matrix_message_structure(self, notifier):
        """Verify Matrix message has plain text body and HTML formatted_body."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_matrix_message(payload)
        assert result["msgtype"] == "m.text"
        assert result["format"] == "org.matrix.custom.html"
        assert "COMPLETED" in result["body"]
        assert "loop-042" in result["body"]
        assert "<h4>" in result["formatted_body"]
        assert "<code>loop-042</code>" in result["formatted_body"]

    def test_matrix_message_with_output(self, notifier):
        """Matrix message includes output text when present."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_matrix_message(payload)
        assert "build failed" in result["body"]
        assert "<pre>" in result["formatted_body"]
        assert "build failed" in result["formatted_body"]

    def test_matrix_retry_and_fallback(self, store, notifier):
        """Matrix failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Matrix fail")
        entry["notification"] = {
            "method": "matrix",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_test_token",
            "matrixRoomId": "!room:matrix.example.com",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_matrix_fallback"] is True

    def test_matrix_uses_put_method(self, store, notifier):
        """Matrix API requires PUT, not POST."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["method"] = req.get_method()
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="PUT test")
        entry["notification"] = {
            "method": "matrix",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        assert captured_data["method"] == "PUT"

    def test_all_method_includes_matrix(self, store, notifier):
        """Method 'all' sends to file + 9 HTTP (webhook+slack+telegram+discord+teams+ntfy+pushover+gotify+matrix) + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestTwilioSmsNotifier:
    def test_twilio_sms_success(self, store, notifier):
        """Twilio SMS sends form-encoded POST to API with Basic auth."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = req.data.decode("utf-8")
            captured_data["auth"] = req.get_header("Authorization")
            captured_data["content_type"] = req.get_header("Content-type")
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "twilio_sms",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "api.twilio.com" in captured_data["url"]
        assert "ACtest123" in captured_data["url"]
        assert captured_data["auth"].startswith("Basic ")
        assert captured_data["content_type"] == "application/x-www-form-urlencoded"
        assert "To=%2B13105555555" in captured_data["body"]
        assert "From=%2B12125551234" in captured_data["body"]
        assert "Body=" in captured_data["body"]

    def test_twilio_sms_message_structure(self):
        """Static _build_twilio_sms_message returns concise plain-text string."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deploy",
            "status": "completed",
            "attempts": 2,
        }
        message = Notifier._build_twilio_sms_message(payload)
        assert isinstance(message, str)
        assert "Loop COMPLETED" in message
        assert "loop-042" in message
        assert "Check deploy" in message
        assert "Attempts: 2" in message

    def test_twilio_sms_message_with_output(self):
        """SMS message includes truncated output text."""
        payload = {
            "timestamp": "2026-01-31T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "failed",
            "task": "Check build",
            "status": "failed",
            "attempts": 3,
            "output": "Build failed: missing dependency libfoo",
        }
        message = Notifier._build_twilio_sms_message(payload)
        assert "Build failed" in message
        assert "Output:" in message

    def test_twilio_sms_retry_and_fallback(self, store, notifier):
        """Twilio SMS retries 3 times, then falls back to file."""
        import urllib.request

        call_count = {"value": 0}

        def fail_request(req, **kwargs):
            call_count["value"] += 1
            raise ConnectionError("Network error")

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "twilio_sms",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
        }

        with patch.object(urllib.request, "urlopen", side_effect=fail_request):
            notifier.notify(entry, "failed")

        assert call_count["value"] == 3
        assert notifier.notifications_file.exists()
        content = notifier.notifications_file.read_text()
        assert "_twilio_sms_fallback" in content

    def test_twilio_sms_basic_auth(self, store, notifier):
        """Verifies Authorization header is Basic base64(SID:Token)."""
        import base64
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["auth"] = req.get_header("Authorization")
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "twilio_sms",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        expected_creds = base64.b64encode(b"ACtest123:authtoken456").decode("utf-8")
        assert captured_data["auth"] == f"Basic {expected_creds}"

    def test_all_method_includes_twilio_sms(self, store, notifier):
        """Method 'all' sends to file + 10 HTTP (webhook+slack+telegram+discord+teams+ntfy+pushover+gotify+matrix+twilio_sms) + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestGoogleChatNotifier:
    def test_google_chat_success(self, store, notifier):
        """Google Chat notification sends Cards v2 payload to webhook."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "google_chat",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "chat.googleapis.com" in captured_data["url"]
        body = captured_data["body"]
        assert "cardsV2" in body
        assert len(body["cardsV2"]) == 1
        assert "COMPLETED" in body["cardsV2"][0]["card"]["header"]["title"]

    def test_google_chat_card_structure(self, notifier):
        """Verify Cards v2 payload structure."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_google_chat_card(payload)
        assert "cardsV2" in result
        card = result["cardsV2"][0]["card"]
        assert "COMPLETED" in card["header"]["title"]
        assert card["header"]["subtitle"] == "loop-042"
        assert len(card["sections"]) >= 2  # widgets + footer

    def test_google_chat_card_with_output(self, notifier):
        """Card includes collapsible output section when present."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_google_chat_card(payload)
        card = result["cardsV2"][0]["card"]
        assert len(card["sections"]) == 3  # widgets + output + footer
        output_section = card["sections"][1]
        assert output_section["header"] == "Output"
        assert output_section["collapsible"] is True
        assert "build failed" in output_section["widgets"][0]["textParagraph"]["text"]

    def test_google_chat_retry_and_fallback(self, store, notifier):
        """Google Chat failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Google Chat fail")
        entry["notification"] = {
            "method": "google_chat",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_google_chat_fallback"] is True

    def test_google_chat_contains_loop_info(self, store, notifier):
        """Card widgets contain loop_id, task, and attempts."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Build server")
        entry["notification"] = {
            "method": "google_chat",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "failed")

        card_text = json.dumps(captured_data["body"])
        assert "loop-001" in card_text
        assert "Build server" in card_text

    def test_all_method_includes_google_chat(self, store, notifier):
        """Method 'all' sends to file + 11 HTTP + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestGotifyNotifier:
    def test_gotify_success(self, store, notifier):
        """Gotify notification sends JSON with title, message, priority to server/message?token=xxx."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "gotify",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "gotify.example.com/message?token=Axxxxxxxxxx" in captured_data["url"]
        body = captured_data["body"]
        assert "COMPLETED" in body["title"]
        assert body["priority"] == 2  # low for completed

    def test_gotify_message_structure(self, notifier):
        """Verify Gotify JSON message structure."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_gotify_message(payload)
        assert "COMPLETED" in result["title"]
        assert result["priority"] == 2
        assert "loop-042" in result["message"]
        assert "Check deployment" in result["message"]

    def test_gotify_message_with_output(self, notifier):
        """Gotify message includes output text when present."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_gotify_message(payload)
        assert result["priority"] == 8  # high for failed
        assert "build failed" in result["message"]

    def test_gotify_retry_and_fallback(self, store, notifier):
        """Gotify failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Gotify fail")
        entry["notification"] = {
            "method": "gotify",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_gotify_fallback"] is True

    def test_gotify_priority_mapping(self, notifier):
        """Priority maps correctly: completed=2, failed=8, expired=5, retry=5, cancelled=2."""
        base = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "task": "Test",
            "status": "unknown",
            "attempts": 1,
        }
        for event, expected in [("completed", 2), ("failed", 8), ("expired", 5), ("retry", 5), ("cancelled", 2)]:
            p = {**base, "event": event}
            result = Notifier._build_gotify_message(p)
            assert result["priority"] == expected, f"{event} should map to priority {expected}"

    def test_all_method_includes_gotify(self, store, notifier):
        """Method 'all' sends to file + 9 HTTP (webhook+slack+telegram+discord+teams+ntfy+pushover+gotify+matrix) + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestPushoverNotifier:
    def test_pushover_success(self, store, notifier):
        """Pushover notification sends JSON with token, user, title, message, priority."""
        import urllib.request
        captured_data = {}

        def capture_request(req, **kwargs):
            captured_data["url"] = req.full_url
            captured_data["body"] = json.loads(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "pushover",
            "pushoverUserKey": "uQiRzpo4DXghDmr9QzzfQu27cmVRsG",
            "pushoverAppToken": "azGDORePK8gMaC0QOYAMyEEuzJnyUi",
        }

        with patch.object(urllib.request, "urlopen", side_effect=capture_request):
            notifier.notify(entry, "completed")

        assert "api.pushover.net" in captured_data["url"]
        body = captured_data["body"]
        assert body["token"] == "azGDORePK8gMaC0QOYAMyEEuzJnyUi"
        assert body["user"] == "uQiRzpo4DXghDmr9QzzfQu27cmVRsG"
        assert "COMPLETED" in body["title"]
        assert body["priority"] == -1  # low for completed

    def test_pushover_message_structure(self, notifier):
        """Verify Pushover JSON message structure."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_pushover_message(payload, "user123", "token456")
        assert result["token"] == "token456"
        assert result["user"] == "user123"
        assert "COMPLETED" in result["title"]
        assert result["priority"] == -1
        assert "loop-042" in result["message"]
        assert "Check deployment" in result["message"]

    def test_pushover_message_with_output(self, notifier):
        """Pushover message includes output text when present."""
        payload = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_pushover_message(payload, "user123", "token456")
        assert result["priority"] == 1  # high for failed
        assert "build failed" in result["message"]

    def test_pushover_retry_and_fallback(self, store, notifier):
        """Pushover failure falls back to file with marker."""
        import urllib.request
        entry = store.create(task="Pushover fail")
        entry["notification"] = {
            "method": "pushover",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
        }

        with patch.object(urllib.request, "urlopen", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_pushover_fallback"] is True

    def test_pushover_priority_mapping(self, notifier):
        """Priority maps correctly: completed=-1, failed=1, expired=0, retry=0, cancelled=-1."""
        base = {
            "timestamp": "2026-02-02T12:00:00+00:00",
            "loop_id": "loop-001",
            "task": "Test",
            "status": "unknown",
            "attempts": 1,
        }
        for event, expected in [("completed", -1), ("failed", 1), ("expired", 0), ("retry", 0), ("cancelled", -1)]:
            p = {**base, "event": event}
            result = Notifier._build_pushover_message(p, "u", "t")
            assert result["priority"] == expected, f"{event} should map to priority {expected}"

    def test_all_method_includes_pushover(self, store, notifier):
        """Method 'all' sends to file + 9 HTTP (webhook+slack+telegram+discord+teams+ntfy+pushover+gotify+matrix) + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestEmailNotifier:
    def test_email_success(self, store, notifier):
        """Email notification connects via SMTP, sends with starttls and login."""
        entry = store.create(task="Deploy check")
        entry["notification"] = {
            "method": "email",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("gen_loop.notifier.smtplib.SMTP", return_value=mock_smtp):
            notifier.notify(entry, "completed")

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user@example.com", "secret")
        mock_smtp.sendmail.assert_called_once()
        args = mock_smtp.sendmail.call_args
        assert args[0][0] == "sender@example.com"
        assert args[0][1] == ["recipient@example.com"]

    def test_email_message_structure(self, notifier):
        """Static _build_email_message returns MIME string with Subject, From, To, body."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-042",
            "event": "completed",
            "task": "Check deployment",
            "status": "completed",
            "attempts": 2,
        }
        result = Notifier._build_email_message(payload, "from@test.com", "to@test.com")
        assert "Subject:" in result
        assert "COMPLETED" in result
        assert "loop-042" in result
        assert "Check deployment" in result
        assert "from@test.com" in result
        assert "to@test.com" in result
        assert "gen-loop-mcp" in result

    def test_email_message_with_output(self, notifier):
        """Email body includes output text when present."""
        payload = {
            "timestamp": "2026-02-01T12:00:00+00:00",
            "loop_id": "loop-001",
            "event": "failed",
            "task": "Build check",
            "status": "failed",
            "attempts": 3,
            "output": "Error: build failed at step 4",
        }
        result = Notifier._build_email_message(payload, "from@test.com", "to@test.com")
        assert "build failed" in result
        assert "FAILED" in result

    def test_email_retry_and_fallback(self, store, notifier):
        """Email failure falls back to file with marker after 3 attempts."""
        entry = store.create(task="Email fail")
        entry["notification"] = {
            "method": "email",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch("gen_loop.notifier.smtplib.SMTP", side_effect=ConnectionError("refused")):
            with patch("gen_loop.notifier.time.sleep"):
                notifier.notify(entry, "completed")

        assert notifier.notifications_file.exists()
        payload = json.loads(notifier.notifications_file.read_text().strip())
        assert payload["_email_fallback"] is True

    def test_email_multiple_recipients(self, store, notifier):
        """Comma-separated to_addr is split correctly for sendmail."""
        entry = store.create(task="Multi recipient")
        entry["notification"] = {
            "method": "email",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "alice@test.com, bob@test.com, charlie@test.com",
            "smtpUseTls": True,
        }

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("gen_loop.notifier.smtplib.SMTP", return_value=mock_smtp):
            notifier.notify(entry, "completed")

        args = mock_smtp.sendmail.call_args
        assert args[0][1] == ["alice@test.com", "bob@test.com", "charlie@test.com"]

    def test_all_method_includes_email(self, store, notifier):
        """Method 'all' sends to file + 8 HTTP (webhook+slack+telegram+discord+teams+ntfy+pushover+gotify) + 1 SMTP."""
        import urllib.request
        http_count = {"value": 0}
        smtp_count = {"value": 0}

        def count_http_calls(req, **kwargs):
            http_count["value"] += 1
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        def count_smtp_calls(*args, **kwargs):
            smtp_count["value"] += 1
            return mock_smtp

        entry = store.create(task="All methods")
        entry["notification"] = {
            "method": "all",
            "webhookUrl": "http://example.com/hook",
            "slackWebhookUrl": "https://hooks.slack.com/test",
            "telegramBotToken": "123:ABC",
            "telegramChatId": "-100999",
            "discordWebhookUrl": "https://discord.com/api/webhooks/test",
            "teamsWebhookUrl": "https://prod.workflow.microsoft.com/test",
            "ntfyServer": "https://ntfy.sh",
            "ntfyTopic": "gen-loop-alerts",
            "pushoverUserKey": "user123",
            "pushoverAppToken": "token456",
            "gotifyServerUrl": "https://gotify.example.com",
            "gotifyAppToken": "Axxxxxxxxxx",
            "matrixHomeserver": "https://matrix.example.com",
            "matrixAccessToken": "syt_token",
            "matrixRoomId": "!room:matrix.example.com",
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "authtoken456",
            "twilioFromNumber": "+12125551234",
            "twilioToNumber": "+13105555555",
            "googleChatWebhookUrl": "https://chat.googleapis.com/v1/spaces/SPACE/messages?key=KEY&token=TOKEN",
            "smtpServer": "smtp.example.com",
            "smtpPort": 587,
            "smtpUsername": "user@example.com",
            "smtpPassword": "secret",
            "smtpFrom": "sender@example.com",
            "smtpTo": "recipient@example.com",
            "smtpUseTls": True,
        }

        with patch.object(urllib.request, "urlopen", side_effect=count_http_calls):
            with patch("gen_loop.notifier.smtplib.SMTP", side_effect=count_smtp_calls):
                notifier.notify(entry, "completed")

        assert http_count["value"] == 11  # webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat
        assert smtp_count["value"] == 1  # email
        assert notifier.notifications_file.exists()


class TestFileRotation:
    def test_rotates_at_size_limit(self, store, notifier):
        """Notifications file rotates when exceeding 1MB."""
        # Create a file just over the limit
        notifier.notifications_file.parent.mkdir(parents=True, exist_ok=True)
        notifier.notifications_file.write_text("x" * (ROTATION_SIZE_BYTES + 100))

        entry = store.create(task="After rotation")
        notifier.notify(entry, "completed")

        # Original should be small (just the new entry)
        assert notifier.notifications_file.exists()
        assert notifier.notifications_file.stat().st_size < ROTATION_SIZE_BYTES

        # Rotated file should exist
        rotated = notifier.notifications_file.with_suffix(".jsonl.1")
        assert rotated.exists()
        assert rotated.stat().st_size > ROTATION_SIZE_BYTES
