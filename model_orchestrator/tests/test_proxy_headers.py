import sys
from pathlib import Path
from types import SimpleNamespace


_orch_dir = str(Path(__file__).resolve().parent.parent)
if _orch_dir not in sys.path:
    sys.path.insert(0, _orch_dir)

from config import VLLM_API_KEY  # noqa: E402
from middleware import ProxyMiddleware  # noqa: E402


def test_build_proxy_headers_overrides_authorization() -> None:
    request = SimpleNamespace(
        headers={
            "authorization": "Bearer sk-no-key-required",
            "content-type": "application/json",
        }
    )

    headers = ProxyMiddleware._build_proxy_headers(request)

    assert headers["authorization"] == f"Bearer {VLLM_API_KEY}"
    assert headers["content-type"] == "application/json"
