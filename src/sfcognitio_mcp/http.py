"""Polite async HTTP client: per-host delay, bounded concurrency, retries."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from urllib.parse import urlsplit

import httpx

from .config import CrawlerConfig

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class BlockedError(RuntimeError):
    """The site keeps refusing us (403/429). Stop and resume later."""


class PoliteClient:
    def __init__(self, cfg: CrawlerConfig, transport: httpx.AsyncBaseTransport | None = None):
        self.cfg = cfg
        self._sem = asyncio.Semaphore(max(1, cfg.concurrency))
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._host_last: dict[str, float] = {}
        self._consecutive_blocks = 0
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": cfg.user_agent,
                "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=cfg.timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    async def _wait_turn(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            last = self._host_last.get(host, 0.0)
            delay = self.cfg.per_host_delay_seconds - (time.monotonic() - last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._host_last[host] = time.monotonic()

    async def get(self, url: str, headers: dict | None = None) -> httpx.Response:
        """GET with politeness and retries. Returns the final response (any status)."""
        host = urlsplit(url).netloc
        attempt = 0
        while True:
            async with self._sem:
                await self._wait_turn(host)
                try:
                    resp = await self.client.get(url, headers=headers)
                except httpx.TransportError as e:
                    resp = None
                    err: Exception | None = e
                else:
                    err = None

            if resp is not None and resp.status_code not in RETRY_STATUSES and resp.status_code != 403:
                self._consecutive_blocks = 0
                return resp

            if resp is not None and resp.status_code in (403, 429):
                self._consecutive_blocks += 1
                if self._consecutive_blocks >= 5:
                    raise BlockedError(
                        f"{resp.status_code} from {host} five times in a row; stopping. "
                        "Re-run later to resume."
                    )

            attempt += 1
            if attempt > self.cfg.max_retries:
                if resp is not None:
                    return resp
                raise err  # type: ignore[misc]

            wait = min(self.cfg.max_backoff_seconds, (2 ** attempt) + random.uniform(0, 1))
            if resp is not None:
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = min(self.cfg.max_backoff_seconds, float(ra))
            log.warning("Retry %d for %s in %.1fs (%s)", attempt, url, wait,
                        resp.status_code if resp is not None else err)
            await asyncio.sleep(wait)
