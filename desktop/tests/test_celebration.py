"""Al terminar una sesión, el aviso de trofeos (pieza y logros) queda en el estado para mostrarse junto al confeti."""
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import services  # noqa: E402


class Fake:
    """Solo lo que usa Background._announce / _toast."""
    def __init__(self):
        self.lock, self.state, self.notified = threading.Lock(), {}, []
        self.notify = lambda title, text: self.notified.append(text)

    _toast = services.Background._toast
    _announce = services.Background._announce


class CelebrationTests(unittest.TestCase):
    def test_piece_and_achievement_are_queued(self):
        f = Fake()
        piece = {"icon": "🚆", "color": "#5B5BD6"}
        f._announce({"language": "es"}, [piece], [{"family": "streak", "goal": 3}])
        self.assertEqual(len(f.state["won"]), 1)
        w = f.state["won"][0]
        self.assertEqual(w["piece"], piece)
        self.assertEqual(w["count"], 1)
        self.assertEqual(len(w["ach_caption"]), 1)
        self.assertEqual(f.state["rewards_version"], 1)
        self.assertEqual(len(f.state["toasts"]), 2)        # los avisos pequeños se mantienen

    def test_nothing_won_queues_nothing(self):
        f = Fake()
        f._announce({"language": "es"}, [], [])
        self.assertNotIn("won", f.state)


if __name__ == "__main__":
    unittest.main()
