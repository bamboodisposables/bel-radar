from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from urllib import robotparser
from urllib.parse import urlparse

from app.config import settings


_LAST_REQUEST: dict[str, float] = {}
_REQUEST_LOCK = asyncio.Lock()
_RATE_MS_BY_SCOPE: dict[str, int] = {
    "kvk_api": 1400,
    "kvk_public": 1300,
    "directory_nl": 1000,
    "directory_sites": 1000,
    "duckduckgo_search": 950,
    "social_hints": 1300,
    "serpapi": 900,
    "twilio_lookup": 500,
    "numlookup_api": 700,
    "clearbit_lookup": 700,
    "hunter_lookup": 700,
}

_TIMEOUT_SECONDS_BY_SCOPE: dict[str, float] = {
    "kvk_api": 18.0,
    "kvk_public": 16.0,
    "directory_nl": 15.0,
    "directory_sites": 15.0,
    "duckduckgo_search": 14.0,
    "social_hints": 14.0,
    "serpapi": 14.0,
    "twilio_lookup": 12.0,
    "numlookup_api": 12.0,
    "clearbit_lookup": 12.0,
    "hunter_lookup": 12.0,
}

_ROBOTS: dict[str, robotparser.RobotFileParser] = {}


async def _apply_rate_limit(scope: str, *, min_interval_ms: int) -> None:
    if min_interval_ms <= 0:
        return
    interval = min_interval_ms / 1000

    async with _REQUEST_LOCK:
        now = time.monotonic()
        last = _LAST_REQUEST.get(scope, 0.0)
        wait = (last + interval) - now
        if wait > 0:
            await asyncio.sleep(wait)
        _LAST_REQUEST[scope] = time.monotonic()


def _retry_wait(step: int, base_delay: float, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(base_delay * (step + 1), float(retry_after))
            except (TypeError, ValueError):
                pass
    return base_delay * (step + 1)


async def _is_allowed_by_robots(url: str, user_agent: str = "*", *, scope: str | None = None) -> bool:
    if not settings.RESPECT_ROBOTS:
        return True

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return True

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    robot_parser = _ROBOTS.get(base_url)
    if robot_parser is None:
        robots_url = f"{base_url}/robots.txt"
        parser = robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.allow_all = True
        except Exception:
            parser.allow_all = True
        _ROBOTS[base_url] = parser
        robot_parser = parser

    if getattr(robot_parser, "allow_all", False):
        return True

    if scope and scope.startswith("social_"):
        # strikter voor social hints: alleen indexpagina's, geen crawl-paden
        return not parsed.path.startswith("/in/")

    return robot_parser.can_fetch(user_agent, url)


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    scope: str,
    timeout: httpx.Timeout | None = None,
    min_interval_ms: int | None = None,
    read_timeout: float | None = None,
    attempts: int | None = None,
    delay_seconds: float | None = None,
    retry_statuses: set[int] = frozenset({403, 429, 500, 502, 503, 504}),
    allow_robots: bool = True,
    **kwargs,
) -> httpx.Response | None:
    if allow_robots and not await _is_allowed_by_robots(url, scope=scope):
        return None

    attempts = attempts if attempts is not None else settings.SEARCH_RETRY_ATTEMPTS
    delay = delay_seconds if delay_seconds is not None else settings.SEARCH_RETRY_DELAY_SECONDS
    timeout = timeout or httpx.Timeout(
        read_timeout
        or _TIMEOUT_SECONDS_BY_SCOPE.get(scope, settings.SEARCH_REQUEST_TIMEOUT_SECONDS),
        connect=read_timeout or _TIMEOUT_SECONDS_BY_SCOPE.get(scope, settings.SEARCH_REQUEST_TIMEOUT_SECONDS),
    )
    min_interval_ms = settings.SEARCH_RATE_LIMIT_MS if min_interval_ms is None else min_interval_ms
    min_interval_ms = max(min_interval_ms, 0)
    scoped_ms = _RATE_MS_BY_SCOPE.get(scope, min_interval_ms)

    last_exception: Exception | None = None

    for step in range(max(1, attempts)):
        await _apply_rate_limit(scope, min_interval_ms=scoped_ms)
        try:
            response = await client.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in retry_statuses and step < attempts - 1:
                await asyncio.sleep(_retry_wait(step, delay, response=response))
                continue
            return response
        except httpx.HTTPError as exc:
            last_exception = exc
            if step >= attempts - 1:
                break
            await asyncio.sleep(_retry_wait(step, delay))

    if last_exception:
        raise last_exception
    return None
