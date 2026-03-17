"""Unit tests for the vLLM sleep/wake orchestrator.

Covers:
- OrchestratorState fields
- classify_openai_payload routing
- ensure_mode singleflight with mocked HTTP
- Vision idle sleep scheduling
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure model_orchestrator modules are importable
_orch_dir = str(Path(__file__).resolve().parent.parent)
if _orch_dir not in sys.path:
    sys.path.insert(0, _orch_dir)

from models import OrchestratorState  # noqa: E402

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# OrchestratorState
# ---------------------------------------------------------------------------


class TestOrchestratorState:
    """OrchestratorState must expose all fields required by new sleep/wake logic."""

    def test_warm_task_exists(self) -> None:
        st = OrchestratorState()
        assert hasattr(st, "warm_task")

    def test_warm_task_starts_unset(self) -> None:
        st = OrchestratorState()
        assert st.warm_task is None

    def test_engine_states_starts_empty(self) -> None:
        st = OrchestratorState()
        assert isinstance(st.engine_states, dict)
        assert len(st.engine_states) == 0

    def test_last_used_at_starts_empty(self) -> None:
        st = OrchestratorState()
        assert isinstance(st.last_used_at, dict)
        assert len(st.last_used_at) == 0

    def test_vision_idle_task_starts_unset(self) -> None:
        st = OrchestratorState()
        assert st.vision_idle_task is None

    def test_audio_idle_task_starts_unset(self) -> None:
        st = OrchestratorState()
        assert st.audio_idle_task is None


# ---------------------------------------------------------------------------
# classify_openai_payload
# ---------------------------------------------------------------------------


class TestClassifyOpenaiPayload:
    """Deterministic router must correctly identify text vs vision payloads."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from services import classify_openai_payload  # noqa: PLC0415
        self.classify = classify_openai_payload

    def test_plain_text_returns_text(self) -> None:
        payload = {
            "messages": [{"role": "user", "content": "hello world"}]
        }
        assert self.classify(payload) == "text"

    def test_empty_messages_returns_text(self) -> None:
        assert self.classify({"messages": []}) == "text"

    def test_no_messages_key_returns_text(self) -> None:
        assert self.classify({}) == "text"

    def test_image_url_part_returns_vision(self) -> None:
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                        {"type": "text", "text": "describe this"},
                    ],
                }
            ]
        }
        assert self.classify(payload) == "vision"

    def test_input_image_type_returns_vision(self) -> None:
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "source": {"url": "https://example.com/img.png"}},
                    ],
                }
            ]
        }
        assert self.classify(payload) == "vision"

    def test_string_content_with_no_image_returns_text(self) -> None:
        payload = {
            "messages": [
                {"role": "system", "content": "you are helpful"},
                {"role": "user", "content": "tell me something"},
            ]
        }
        assert self.classify(payload) == "text"

    def test_multi_turn_with_image_in_second_message_returns_vision(self) -> None:
        payload = {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}},
                    ],
                },
            ]
        }
        assert self.classify(payload) == "vision"

    def test_input_audio_returns_audio(self) -> None:
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": "base64...", "format": "pcm16"}},
                    ],
                }
            ]
        }
        assert self.classify(payload) == "audio"

    def test_text_content_only_not_audio(self) -> None:
        payload = {
            "messages": [{"role": "user", "content": "transcribe this for me"}]
        }
        assert self.classify(payload) == "text"


# ---------------------------------------------------------------------------
# Singleflight (warm task) — no actual HTTP
# ---------------------------------------------------------------------------


class TestWarmSingleflight:
    """ensure_mode must deduplicate concurrent switch requests."""

    @pytest.mark.asyncio
    async def test_ensure_mode_already_current_returns_immediately(self) -> None:
        from models import state

        original_mode = state.current_mode
        state.current_mode = "text"
        try:
            from services import ensure_mode

            # Should return without calling any HTTP — just touches the mode
            with patch("services.detect_engine_state") as mock_detect:
                await ensure_mode("text")
                mock_detect.assert_not_called()
        finally:
            state.current_mode = original_mode

    @pytest.mark.asyncio
    async def test_ensure_mode_awaits_in_progress_task(self) -> None:
        """When a switch task is already running, callers should await it."""
        from models import state

        state.current_mode = None

        async def _dummy_switch() -> None:
            await asyncio.sleep(0.05)
            state.current_mode = "text"

        task = asyncio.create_task(_dummy_switch())
        state.warm_task = task

        try:
            # A second caller should await the task and see the updated mode.
            from services import ensure_mode

            with patch("services._do_switch_mode", new_callable=AsyncMock) as mock_switch:
                await ensure_mode("text")
                # _do_switch_mode should NOT be called because the in-progress
                # task already set the mode to "text".
                mock_switch.assert_not_called()
        finally:
            state.current_mode = None
            if not task.done():
                task.cancel()
            state.warm_task = None


class TestSleepCapabilityAwareness:
    """Non-vLLM backends (e.g. whisper) must not use sleep/wake dev endpoints."""

    @pytest.mark.asyncio
    async def test_sleep_engine_skips_audio_backend_without_http_calls(self) -> None:
        from services import sleep_engine

        with patch("services.get_http_client", new_callable=AsyncMock) as mock_client:
            await sleep_engine("audio", level=2)
            mock_client.assert_not_called()


# ---------------------------------------------------------------------------
# /warm endpoint integration (HTTP layer)
# ---------------------------------------------------------------------------


class TestWarmEndpoint:
    """Smoke-test the /warm route with mocked startup and logger."""

    @pytest.mark.asyncio
    async def test_warm_already_warm(self) -> None:
        """If current_mode matches, return 200 already_warm."""
        from models import state

        original_mode = state.current_mode
        state.current_mode = "text"
        try:
            with (
                patch("main.setup_logger"),
                patch("services.startup_orchestrator", new_callable=AsyncMock),
            ):
                from main import app
                from httpx import AsyncClient, ASGITransport

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as ac:
                    resp = await ac.post("/warm", params={"mode": "text"})
                assert resp.status_code == 200
                assert resp.json()["status"] == "already_warm"
        finally:
            state.current_mode = original_mode

    @pytest.mark.asyncio
    async def test_warm_unknown_mode_returns_400(self) -> None:
        with (
            patch("main.setup_logger"),
            patch("services.startup_orchestrator", new_callable=AsyncMock),
        ):
            from main import app
            from httpx import AsyncClient, ASGITransport

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post("/warm", params={"mode": "nonexistent"})
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_warm_audio_mode_is_valid(self) -> None:
        """audio is now a valid mode and should NOT return 400."""
        from models import state

        original_mode = state.current_mode
        state.current_mode = "audio"
        try:
            with (
                patch("main.setup_logger"),
                patch("services.startup_orchestrator", new_callable=AsyncMock),
            ):
                from main import app
                from httpx import AsyncClient, ASGITransport

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as ac:
                    resp = await ac.post("/warm", params={"mode": "audio"})
                assert resp.status_code == 200
                assert resp.json()["status"] == "already_warm"
        finally:
            state.current_mode = original_mode
