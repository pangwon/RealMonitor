"""네이버 부동산 API 클라이언트.

네이버 부동산 내부 API를 사용하여 아파트/오피스텔 매물 목록을 조회한다.
Rate limit 준수 및 exponential backoff 재시도 로직을 포함한다.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from loguru import logger

# 거래유형 매핑: 한글 → API 코드
TRADE_TYPE_MAP: dict[str, str] = {
    "매매": "A1",
    "전세": "B1",
    "월세": "B2",
}

BASE_URL = "https://new.land.naver.com/api/articles/complex"

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://new.land.naver.com/",
    "Accept": "application/json",
}

# Rate limit: 요청 간 최소 2초
_MIN_REQUEST_INTERVAL: float = 2.0

# Retry 설정
_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 2.0


class NaverLandClient:
    """네이버 부동산 API 비동기 클라이언트.

    Rate limit(요청 간 2초)과 exponential backoff 재시도를 자동 처리한다.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=timeout)
        self._last_request_time: float = 0.0

    async def close(self) -> None:
        """HTTP 클라이언트 세션을 종료한다."""
        await self._client.aclose()

    async def __aenter__(self) -> NaverLandClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _wait_rate_limit(self) -> None:
        """이전 요청으로부터 최소 2초 간격을 유지한다."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            wait = _MIN_REQUEST_INTERVAL - elapsed
            logger.debug("Rate limit 대기: {:.2f}초", wait)
            await asyncio.sleep(wait)

    async def _request_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Exponential backoff으로 GET 요청을 수행한다.

        Args:
            url: 요청 URL.
            params: 쿼리 파라미터.

        Returns:
            JSON 응답 딕셔너리.

        Raises:
            httpx.HTTPStatusError: 최대 재시도 후에도 실패한 경우.
        """
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            await self._wait_rate_limit()
            try:
                self._last_request_time = time.monotonic()
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE ** attempt
                logger.warning(
                    "API 요청 실패 (시도 {}/{}): {} — {:.1f}초 후 재시도",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise last_exc  # type: ignore[misc]

    async def fetch_articles(
        self,
        complex_id: str,
        trade_type: str = "전세",
        page: int = 1,
    ) -> dict[str, Any]:
        """특정 단지의 매물 목록을 조회한다.

        Args:
            complex_id: 네이버 부동산 단지 ID.
            trade_type: 거래유형 (매매/전세/월세).
            page: 페이지 번호 (1부터 시작).

        Returns:
            API 응답 JSON 딕셔너리 (articleList 등 포함).
        """
        trade_code = TRADE_TYPE_MAP.get(trade_type)
        if trade_code is None:
            raise ValueError(
                f"지원하지 않는 거래유형: {trade_type!r} "
                f"(가능: {', '.join(TRADE_TYPE_MAP)})"
            )

        url = f"{BASE_URL}/{complex_id}"
        params: dict[str, Any] = {
            "tradeType": trade_code,
            "page": page,
            "sameAddressGroup": "false",
        }

        logger.info(
            "매물 조회: complex_id={}, trade_type={}({}), page={}",
            complex_id,
            trade_type,
            trade_code,
            page,
        )
        return await self._request_with_retry(url, params)

    async def fetch_all_articles(
        self,
        complex_id: str,
        trade_type: str = "전세",
    ) -> list[dict[str, Any]]:
        """모든 페이지의 매물 목록을 수집한다.

        Args:
            complex_id: 네이버 부동산 단지 ID.
            trade_type: 거래유형 (매매/전세/월세).

        Returns:
            전체 매물 딕셔너리 리스트.
        """
        all_articles: list[dict[str, Any]] = []
        page = 1

        while True:
            data = await self.fetch_articles(complex_id, trade_type, page)
            articles = data.get("articleList", [])
            if not articles:
                break
            all_articles.extend(articles)

            # 더 이상 페이지가 없으면 종료
            is_more = data.get("isMoreData", False)
            if not is_more:
                break
            page += 1

        logger.info(
            "총 {}건 수집: complex_id={}, trade_type={}",
            len(all_articles),
            complex_id,
            trade_type,
        )
        return all_articles
