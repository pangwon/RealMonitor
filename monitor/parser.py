"""네이버 부동산 API 응답 파서.

API JSON 응답에서 매물 데이터를 추출하고,
정규화된 Article dataclass로 변환한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Article:
    """정규화된 매물 데이터."""

    article_id: str
    complex_id: str
    complex_name: str
    trade_type: str
    price: str
    area_exclusive: float
    area_supply: float
    floor: int
    direction: str
    description: str
    article_url: str
    dong: str = ""
    ho: str = ""
    tags: list[str] = field(default_factory=list)


def _safe_int(value: Any, default: int = 0) -> int:
    """값을 int로 안전하게 변환한다."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """값을 float로 안전하게 변환한다."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_article(raw: dict[str, Any], complex_id: str, complex_name: str = "") -> Article:
    """단일 매물 JSON을 Article로 변환한다.

    Args:
        raw: API 응답의 개별 매물 딕셔너리.
        complex_id: 단지 ID.
        complex_name: 단지명 (config에서 전달).

    Returns:
        정규화된 Article 인스턴스.
    """
    article_id = str(raw.get("articleNo", ""))

    # 가격 정보 조합
    deal_price = raw.get("dealOrWarrantPrc", "")
    rent_price = raw.get("rentPrc", "")
    if rent_price:
        price = f"{deal_price}/{rent_price}"
    else:
        price = str(deal_price)

    # 거래유형 한글 변환
    trade_type_name = raw.get("tradeTypeName", "")

    # 면적
    area_exclusive = _safe_float(raw.get("exclusiveArea"))
    area_supply = _safe_float(raw.get("supplyArea"))

    # 층수
    floor = _safe_int(raw.get("floorInfo", "").split("/")[0] if raw.get("floorInfo") else 0)

    # 방향
    direction = raw.get("direction", "") or ""

    # 설명
    description = raw.get("articleFeatureDesc", "") or ""

    # 동/호
    dong = raw.get("buildingName", "") or ""
    ho = raw.get("hoNo", "") or ""

    # 태그
    tags = raw.get("tagList", []) or []

    # 매물 URL
    article_url = f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}"

    return Article(
        article_id=article_id,
        complex_id=complex_id,
        complex_name=complex_name or raw.get("complexName", ""),
        trade_type=trade_type_name,
        price=price,
        area_exclusive=area_exclusive,
        area_supply=area_supply,
        floor=floor,
        direction=direction,
        description=description,
        article_url=article_url,
        dong=dong,
        ho=ho,
        tags=tags,
    )


def parse_articles(
    raw_list: list[dict[str, Any]],
    complex_id: str,
    complex_name: str = "",
) -> list[Article]:
    """매물 목록 JSON을 Article 리스트로 변환한다.

    Args:
        raw_list: API 응답의 articleList.
        complex_id: 단지 ID.
        complex_name: 단지명.

    Returns:
        Article 리스트.
    """
    return [parse_article(raw, complex_id, complex_name) for raw in raw_list]
