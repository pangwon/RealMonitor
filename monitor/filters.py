"""매물 필터링 모듈.

config.yaml의 filters 섹션을 기반으로 가격, 면적, 층수, 방향 등
조건에 맞는 매물만 필터링한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from monitor.parser import Article


def _parse_price(price_str: str) -> int | None:
    """가격 문자열에서 만원 단위 숫자를 추출한다.

    월세(보증금/월세)인 경우 보증금 기준으로 파싱한다.

    Args:
        price_str: 가격 문자열 (예: "45000", "30000/100").

    Returns:
        만원 단위 정수 또는 파싱 실패 시 None.
    """
    try:
        # 월세: "보증금/월세" → 보증금 기준
        base = price_str.split("/")[0].strip()
        # 쉼표, 공백, "만원" 등 제거
        cleaned = base.replace(",", "").replace("만원", "").replace("억", "").strip()
        return int(cleaned)
    except (ValueError, IndexError):
        return None


@dataclass
class ArticleFilter:
    """매물 필터 조건.

    None인 필드는 해당 조건을 적용하지 않는다.
    """

    price_min: int | None = None
    price_max: int | None = None
    area_min: float | None = None
    area_max: float | None = None
    floor_min: int | None = None
    floor_max: int | None = None
    direction: str | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> ArticleFilter:
        """config.yaml의 filters 딕셔너리에서 ArticleFilter를 생성한다.

        Args:
            config: filters 설정 딕셔너리. None이면 빈 필터 반환.

        Returns:
            ArticleFilter 인스턴스.
        """
        if not config:
            return cls()
        return cls(
            price_min=config.get("price_min"),
            price_max=config.get("price_max"),
            area_min=config.get("area_min"),
            area_max=config.get("area_max"),
            floor_min=config.get("floor_min"),
            floor_max=config.get("floor_max"),
            direction=config.get("direction"),
        )

    def matches(self, article: Article) -> bool:
        """매물이 필터 조건에 부합하는지 검사한다.

        Args:
            article: 검사할 매물.

        Returns:
            모든 조건을 만족하면 True.
        """
        # 가격 필터
        if self.price_min is not None or self.price_max is not None:
            price = _parse_price(article.price)
            if price is not None:
                if self.price_min is not None and price < self.price_min:
                    return False
                if self.price_max is not None and price > self.price_max:
                    return False

        # 면적 필터 (전용면적 기준)
        if self.area_min is not None and article.area_exclusive < self.area_min:
            return False
        if self.area_max is not None and article.area_exclusive > self.area_max:
            return False

        # 층수 필터
        if self.floor_min is not None and article.floor < self.floor_min:
            return False
        if self.floor_max is not None and article.floor > self.floor_max:
            return False

        # 방향 필터 (부분 일치)
        if self.direction is not None and self.direction not in article.direction:
            return False

        return True


def filter_articles(
    articles: list[Article],
    filter_config: dict[str, Any] | None = None,
) -> list[Article]:
    """필터 조건에 맞는 매물만 반환한다.

    필터 조건이 없으면(filter_config가 None이거나 빈 딕셔너리)
    모든 매물을 그대로 반환한다.

    Args:
        articles: 필터링할 매물 리스트.
        filter_config: config.yaml의 filters 딕셔너리.

    Returns:
        필터 조건을 만족하는 매물 리스트.
    """
    article_filter = ArticleFilter.from_config(filter_config)
    filtered = [a for a in articles if article_filter.matches(a)]
    logger.debug(
        "필터링 결과: {}건 → {}건 (조건: {})",
        len(articles),
        len(filtered),
        filter_config or "없음",
    )
    return filtered
