"""Background scheduler — runs the monitor agent on a fixed interval."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from .monitor import run_check

logger = logging.getLogger(__name__)

INTERVAL = int(os.environ.get("NIL_AGENT_INTERVAL", "3600"))

_task: asyncio.Task[None] | None = None
_status: dict[str, Any] = {"running": False, "last_run": None}


async def _loop(artifacts_dir: Path) -> None:
    _status["running"] = True
    logger.info("Agent scheduler started (interval=%ds)", INTERVAL)
    while True:
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, run_check, artifacts_dir)
            _status["last_run"] = result
            logger.info("Agent run completed: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Agent run failed")
        await asyncio.sleep(INTERVAL)


def start(artifacts_dir: Path) -> None:
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(artifacts_dir))


def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
        _status["running"] = False


def status() -> dict[str, Any]:
    return {
        "running": _status["running"],
        "interval_seconds": INTERVAL,
        "last_run": _status["last_run"],
    }
