"""
Docker helper utilities — LEGACY / MANUAL-OPS ONLY.

This module is NO LONGER called from the hot request path.
The orchestrator now controls vLLM processes via HTTP sleep/wake endpoints
(see services.py). These helpers remain available for manual debugging and
ad-hoc container administration only.

Docker client is lazily instantiated to avoid import-time crashes in
environments where the Docker socket is absent (e.g. CI test runners).
"""

import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger("orchestrator")

# Lazy import: docker SDK is only needed if someone actually calls these helpers.
_docker_client: Any = None


def _get_docker_client() -> Any:
    """Return (or lazily create) the Docker client."""
    global _docker_client
    if _docker_client is None:
        import docker  # local import: optional dependency in vLLM deployment

        _docker_client = docker.from_env()
    return _docker_client


# ---------------------------------------------------------------------------
# Network detection (manual-ops helper, not used by the hot path)
# ---------------------------------------------------------------------------


def _get_own_network() -> str:
    """Detect the Docker Compose network this container is on."""
    import docker  # local import: optional dependency

    client = _get_docker_client()
    hostname = os.environ.get("HOSTNAME", "")
    if not hostname:
        raise RuntimeError(
            "HOSTNAME env-var is empty — cannot detect Docker network."
        )
    try:
        container = client.containers.get(hostname)
        networks = container.attrs["NetworkSettings"]["Networks"]
        for name in networks:
            if name != "bridge":
                return name
        return next(iter(networks))
    except docker.errors.NotFound as exc:
        raise RuntimeError(
            f"Cannot find own container by HOSTNAME={hostname!r}."
        ) from exc


def get_network_name() -> str:
    """Return the Docker Compose network name (manual-ops helper)."""
    name = _get_own_network()
    logger.info("Detected Docker network: %s", name)
    return name


# ---------------------------------------------------------------------------
# Container helpers (manual-ops only)
# ---------------------------------------------------------------------------


def get_container(container_name: str) -> Any:
    """Find a container by exact name."""
    import docker  # local import: optional dependency

    client = _get_docker_client()
    containers = client.containers.list(all=True, filters={"name": container_name})
    for c in containers:
        if c.name == container_name:
            return c
    raise docker.errors.NotFound(f"Container {container_name} not found")


def ensure_container_running(target_name: str, stop_names: List[str]) -> None:
    """[LEGACY] Ensure a named container is running, others stopped.

    This was the old hot-path switch mechanism.  It is NOT called by the
    orchestrator any more.  Kept here for manual debugging only.
    """
    import docker  # local import: optional dependency

    client = _get_docker_client()
    for name in stop_names:
        try:
            c = get_container(name)
            c.reload()
            if c.status == "running":
                logger.info("Stopping %s...", name)
                c.stop()
                c.wait()
        except docker.errors.NotFound:
            pass

    try:
        container = get_container(target_name)
    except docker.errors.NotFound:
        raise RuntimeError(
            f"Container {target_name} not found — "
            "vLLM containers must be pre-started via docker-compose."
        )

    container.reload()
    if container.status != "running":
        logger.info("Starting %s...", target_name)
        try:
            container.start()
        except docker.errors.APIError as exc:
            raise RuntimeError(
                f"Docker API error starting {target_name}: {exc}"
            ) from exc


def cleanup_containers() -> None:
    """[LEGACY] Stop and remove all managed model containers."""
    import docker  # local import: optional dependency

    client = _get_docker_client()
    # Import here to avoid circular import; config may not define containers anymore.
    try:
        from config import MODE_URLS  # type: ignore[import]

        for mode, url in MODE_URLS.items():
            logger.info(
                "cleanup_containers is a no-op in vLLM mode "
                "(workers are managed by docker-compose). mode=%s url=%s",
                mode,
                url,
            )
    except Exception:
        logger.warning("cleanup_containers: could not import MODE_URLS; skipping.")
