import unittest
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

if __name__ == "__main__":
    unittest.main()
