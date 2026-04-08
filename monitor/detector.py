"""신규 매물 감지 모듈.

API 조회 결과와 DB를 비교하여 신규 매물, 가격 변동, 거래완료(삭제)를 감지한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from db.store import ArticleStore
from monitor.parser import Article


@dataclass
class PriceChange:
    """가격 변동 정보."""

    article: Article
    old_price: str
    new_price: str


@dataclass
class DetectionResult:
    """한 번의 감지 사이클 결과."""

    new: list[Article] = field(default_factory=list)
    price_changed: list[PriceChange] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def has_updates(self) -> bool:
        """알림이 필요한 변경사항이 있는지 반환한다."""
        return bool(self.new or self.price_changed or self.removed)

    @property
    def summary(self) -> str:
        """감지 결과 요약 문자열을 반환한다."""
        parts: list[str] = []
        if self.new:
            parts.append(f"신규 {len(self.new)}건")
        if self.price_changed:
            parts.append(f"가격변동 {len(self.price_changed)}건")
        if self.removed:
            parts.append(f"삭제 {len(self.removed)}건")
        return ", ".join(parts) if parts else "변동 없음"


async def detect_new_articles(
    articles: list[Article],
    store: ArticleStore,
) -> list[Article]:
    """API 조회 결과에서 DB에 없는 신규 매물을 찾는다.

    Args:
        articles: API에서 파싱된 매물 리스트.
        store: 매물 이력 저장소.

    Returns:
        신규 매물 리스트.
    """
    new_articles: list[Article] = []
    for article in articles:
        existing = await store.get_article(article.article_id)
        if existing is None:
            new_articles.append(article)
    if new_articles:
        logger.info("신규 매물 {}건 감지", len(new_articles))
    return new_articles


async def detect_price_changes(
    articles: list[Article],
    store: ArticleStore,
) -> list[PriceChange]:
    """기존 매물 중 가격이 변경된 것을 감지한다.

    Args:
        articles: API에서 파싱된 매물 리스트.
        store: 매물 이력 저장소.

    Returns:
        가격 변동 정보 리스트.
    """
    changes: list[PriceChange] = []
    for article in articles:
        existing = await store.get_article(article.article_id)
        if existing is not None and existing["price"] != article.price:
            changes.append(
                PriceChange(
                    article=article,
                    old_price=existing["price"],
                    new_price=article.price,
                )
            )
    if changes:
        logger.info("가격 변동 {}건 감지", len(changes))
    return changes


async def detect_removed(
    complex_id: str,
    current_article_ids: set[str],
    store: ArticleStore,
) -> list[str]:
    """DB에 있지만 API에서 사라진 매물(거래완료/삭제)을 감지한다.

    Args:
        complex_id: 단지 ID.
        current_article_ids: 현재 API에서 확인된 매물 ID 집합.
        store: 매물 이력 저장소.

    Returns:
        삭제된 매물 article_id 리스트.
    """
    db_active_ids = await store.get_active_article_ids(complex_id)
    removed = db_active_ids - current_article_ids
    if removed:
        logger.info("삭제/거래완료 {}건 감지 (complex_id={})", len(removed), complex_id)
    return list(removed)


async def run_detection(
    articles: list[Article],
    complex_id: str,
    store: ArticleStore,
) -> DetectionResult:
    """전체 감지 사이클을 실행한다.

    신규 매물 감지 → 가격 변동 감지 → 삭제 감지 → DB 반영을 순서대로 수행한다.

    Args:
        articles: API에서 파싱된 매물 리스트.
        complex_id: 단지 ID.
        store: 매물 이력 저장소.

    Returns:
        DetectionResult (new, price_changed, removed).
    """
    # 1. DB 반영 전에 신규/가격변동 감지
    new = await detect_new_articles(articles, store)
    price_changed = await detect_price_changes(articles, store)

    # 2. 삭제 감지
    current_ids = {a.article_id for a in articles}
    removed = await detect_removed(complex_id, current_ids, store)

    # 3. DB 반영: upsert + 비활성 마킹
    for article in articles:
        await store.upsert_article(article)
    await store.mark_inactive(complex_id, current_ids)

    result = DetectionResult(new=new, price_changed=price_changed, removed=removed)
    logger.info("감지 완료 (complex_id={}): {}", complex_id, result.summary)
    return result
