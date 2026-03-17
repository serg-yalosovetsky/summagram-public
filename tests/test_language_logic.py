from indexer import get_chat_engine
import unittest
from unittest.mock import patch, MagicMock


class TestLanguageLogic(unittest.TestCase):
    def test_prompt_construction(self):
        # Mock get_index to avoid loading Chroma
        with patch("indexer.get_index") as mock_get_index:
            mock_index = MagicMock()
            mock_get_index.return_value = mock_index

            # We don't need to call as_chat_engine, just check the prompt in get_chat_engine
            # But let's see how it's used.
            # Actually, I want to verify the system_prompt passed to as_chat_engine

            get_chat_engine(system_prompt_suffix="TEST_SUFFIX")

            args, kwargs = mock_index.as_chat_engine.call_args
            system_prompt = kwargs.get("system_prompt", "")

            print("\n--- CONSTRUCTED SYSTEM PROMPT ---")
            print(system_prompt)
            print("--- END ---")

            self.assertIn("ru, en, uk", system_prompt)
            self.assertIn("en", system_prompt)
            self.assertIn("ru", system_prompt)
            self.assertIn("TEST_SUFFIX", system_prompt)
            self.assertIn("--- LANGUAGE RULES ---", system_prompt)


if __name__ == "__main__":
    unittest.main()
