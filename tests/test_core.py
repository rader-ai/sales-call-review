import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import run


class CallReviewTests(unittest.TestCase):
    def setUp(self):
        self.meta = {"internal": ["Maya"], "external": ["Jordan"]}
        self.text = ("**Maya** [00:00] What is the problem?\n"
                     "**Jordan** [00:10] We spend five hours each week.\n"
                     "**Unknown Person** [00:20] This is uncertain.\n")

    def test_unknown_speaker_excluded_from_talk_share(self):
        stats = run.metrics(self.meta, self.text)
        self.assertTrue(stats["unknown_speakers_excluded"])
        self.assertEqual(stats["question_marks"]["internal"], 1)
        self.assertEqual(stats["words"]["unclear"], 3)
        self.assertAlmostEqual(stats["internal_talk_share"], 4 / 10, places=3)

    def test_quote_must_occur_in_one_turn(self):
        analysis = {"claims": [{"quote": "We spend five hours each week."},
                               {"quote": "the problem We spend five hours"}]}
        checked = run.verify(analysis, self.text)
        self.assertEqual([item["ok"] for item in checked], [True, False])

    def test_example_analysis_has_verified_quotes(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "examples"
        analysis = json.loads((root / "sample-analysis.json").read_text())
        checked = run.verify(analysis, (root / "discovery.md").read_text())
        self.assertEqual(len(checked), 4)
        self.assertTrue(all(item["ok"] for item in checked))


if __name__ == "__main__":
    unittest.main()
