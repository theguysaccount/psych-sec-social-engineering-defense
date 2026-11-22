"""The self-test's retries (scripts/check_live.py), with the network and the pauses replaced."""
import importlib.util
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_live", ROOT / "scripts" / "check_live.py")
check_live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_live)


def http_error(code):
    return urllib.error.HTTPError("https://example.test/", code, "test", {}, None)


class Retries(unittest.TestCase):
    def setUp(self):
        check_live.retries_used = 0
        for target, name in ((check_live.time, "sleep"), (check_live, "print")):
            patcher = mock.patch.object(target, name, create=True)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def fetch(self, *answers):
        """get() a URL whose single attempts answer `answers` in turn; returns (result or error, tries)."""
        answers = iter(answers)

        def once(url):
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return answer

        with mock.patch.object(check_live, "get_once", side_effect=once) as attempt:
            try:
                return check_live.get("https://example.test/"), attempt.call_count
            except Exception as e:
                return e, attempt.call_count

    def test_a_single_503_is_retried(self):
        self.assertEqual(self.fetch(http_error(503), (200, "ok")), ((200, "ok"), 2))
        self.sleep.assert_called_once_with(10)

    def test_timeouts_and_dropped_connections_are_retried(self):
        result, tries = self.fetch(urllib.error.URLError("timed out"), TimeoutError(), ConnectionResetError(), (200, "ok"))
        self.assertEqual((result, tries), ((200, "ok"), 4))
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [10, 20, 30])

    def test_answers_a_retry_wont_change_fail_at_once(self):
        for code in (403, 404, 410):
            result, tries = self.fetch(http_error(code), (200, "ok"))
            self.assertEqual((result.code, tries), (code, 1))
        self.sleep.assert_not_called()

    def test_gives_up_after_four_tries(self):
        result, tries = self.fetch(*[http_error(503)] * 5)
        self.assertEqual((result.code, tries), (503, 4))

    def test_a_run_has_a_retry_budget(self):
        check_live.retries_used = check_live.RETRY_BUDGET
        result, tries = self.fetch(http_error(503), (200, "ok"))
        self.assertEqual((result.code, tries), (503, 1))


if __name__ == "__main__":
    unittest.main()
