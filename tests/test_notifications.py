import json
import unittest
from unittest.mock import patch
import monitor

class Good(monitor.Notifier):
    def send(self, subject, body):
        pass

class Bad(monitor.Notifier):
    def send(self, subject, body):
        raise RuntimeError("test failure")

class NotificationTests(unittest.TestCase):
    def test_per_channel_results(self):
        results = monitor.notify_all([Good(), Bad()], "x", "y")
        self.assertEqual(results[0][1], True)
        self.assertEqual(results[1][1], False)
        self.assertIn("test failure", results[1][2])

    def test_telegram_notifier(self):
        notifier = monitor.TelegramNotifier({"bot_token": "123:abc", "chat_id": "-100123"})
        with patch("monitor.http_request") as request:
            notifier.send("ZKAS BLOCK FOUND", "Worker: KSOPRO")
        request.assert_called_once()
        url = request.call_args.args[0]
        payload = json.loads(request.call_args.kwargs["data"].decode("utf-8"))
        self.assertEqual(url, "https://api.telegram.org/bot123:abc/sendMessage")
        self.assertEqual(payload["chat_id"], "-100123")
        self.assertIn("ZKAS BLOCK FOUND", payload["text"])
        self.assertIn("KSOPRO", payload["text"])

    def test_build_notifiers_includes_telegram(self):
        cfg = {"notifications": {
            "console": {"enabled": False},
            "telegram": {"enabled": True, "bot_token": "123:abc", "chat_id": "456"},
        }}
        notifiers = monitor.build_notifiers(cfg)
        self.assertEqual(len(notifiers), 1)
        self.assertIsInstance(notifiers[0], monitor.TelegramNotifier)

if __name__ == "__main__":
    unittest.main()
