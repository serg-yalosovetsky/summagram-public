import unittest
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from etl.sources.telegram import parse_vision_analysis


class TestMediaProcessing(unittest.TestCase):
    def test_parse_vision_analysis_markdown(self):
        analysis = 'Assistant: Here is the analysis: ```json\n{\n  "description": "A cute cat",\n  "is_meme": true,\n  "is_portrait": false,\n  "tags": ["cat", "cute", "meme"]\n}\n```'
        parsed = parse_vision_analysis(analysis)
        self.assertEqual(parsed["description"], "A cute cat")
        self.assertTrue(parsed["is_meme"])
        self.assertFalse(parsed["is_portrait"])
        self.assertEqual(parsed["tags"], ["cat", "cute", "meme"])

    def test_parse_vision_analysis_raw_json(self):
        analysis = '{\n  "description": "A dog with a hat",\n  "is_meme": false,\n  "is_portrait": true,\n  "tags": ["dog", "hat"]\n}'
        parsed = parse_vision_analysis(analysis)
        self.assertEqual(parsed["description"], "A dog with a hat")
        self.assertFalse(parsed["is_meme"])
        self.assertTrue(parsed["is_portrait"])
        self.assertEqual(parsed["tags"], ["dog", "hat"])

    def test_parse_vision_analysis_partial_json(self):
        # Model might output text before JSON
        analysis = 'The image shows a sunset. {"description": "Sunset over mountains", "is_meme": false, "tags": ["sunset", "mountains"]}'
        parsed = parse_vision_analysis(analysis)
        self.assertEqual(parsed["description"], "Sunset over mountains")
        self.assertFalse(parsed["is_meme"])
        self.assertEqual(parsed["tags"], ["sunset", "mountains"])

    def test_parse_vision_analysis_fallback(self):
        analysis = "I see a green field with some flowers."
        parsed = parse_vision_analysis(analysis)
        self.assertEqual(parsed["description"], analysis)
        self.assertIsNone(parsed.get("is_meme"))


if __name__ == "__main__":
    unittest.main()
