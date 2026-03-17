import os
import sys

# simulate conftest.py
root = os.getcwd()
etl_dir = os.path.join(root, "etl")
if etl_dir not in sys.path:
    sys.path.insert(0, etl_dir)

from unittest.mock import MagicMock
local_modules = ["models", "schemas", "config", "database", "main", "sources", "processing", "manager", "llm_config", "telemetry"]
for m in local_modules:
    if m in sys.modules: del sys.modules[m]
sys.modules["llm_config"] = MagicMock()
sys.modules["telemetry"] = MagicMock()

try:
    from etl.db.chats import build_multilingual_prefix_patterns
    print("build_multilingual_prefix_patterns is:", type(build_multilingual_prefix_patterns))
except Exception as e:
    print("Exception importing:", e)
