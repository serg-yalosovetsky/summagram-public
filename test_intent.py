import asyncio
import os
import sys
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv(".env")
from backend.session_agent import _stage1_intent
import backend.sglang_client
# Use the orchestrator port exposed on localhost (if running)
backend.sglang_client.Config.LLM_SERVER_URL = "http://localhost:8004"

async def test():
    intent = await _stage1_intent("задала алиса", [{"role": "user", "content": "что мне задала алиса"}])
    print(intent)

asyncio.run(test())
