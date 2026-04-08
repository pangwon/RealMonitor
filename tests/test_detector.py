"""monitor/detector.py 테스트.

인메모리 SQLite를 사용하여 신규/가격변동/삭제 감지를 테스트한다.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from db.store import ArticleStore
from monitor.detector import (
    DetectionResult,
    detect_new_articles,
    detect_price_changes,
    detect_removed,
    run_detection,
)
from monitor.parser import Article


def _make_article(
    article_id: str = "100",
    price: str = "45000",
    complex_id: str = "12345",
    **kwargs: object,
) -> Article:
    """테스트용 Article을 생성한다."""
    defaults = {
        "complex_name": "테스트 단지",
        "trade_type": "전세",
        "area_exclusive": 84.0,
        "area_supply": 112.0,
        "floor": 10,
        "direction": "남향",
        "description": "테스트",
        "article_url": f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    }
    defaults.update(kwargs)
    return Article(article_id=article_id, price=price, complex_id=complex_id, **defaults)  # type: ignore[arg-type]


@pytest_asyncio.fixture()
async def store() -> ArticleStore:
    """인메모리 SQLite 저장소를 생성한다."""
    s = ArticleStore(db_path=":memory:")
    await s.connect()
    yield s  # type: ignore[misc]
    await s.close()


class TestDetectNewArticles:
    """detect_new_articles 테스트."""

    @pytest.mark.asyncio()
    async def test_all_new(self, store: ArticleStore) -> None:
        """DB가 비어있으면 모든 매물이 신규이다."""
        articles = [_make_article("1"), _make_article("2")]
        new = await detect_new_articles(articles, store)
        assert len(new) == 2

    @pytest.mark.asyncio()
    async def test_some_existing(self, store: ArticleStore) -> None:
        """DB에 이미 있는 매물은 신규가 아니다."""
        existing = _make_article("1")
        await store.upsert_article(existing)

        articles = [_make_article("1"), _make_article("2")]
        new = await detect_new_articles(articles, store)

        assert len(new) == 1
        assert new[0].article_id == "2"

    @pytest.mark.asyncio()
    async def test_no_new(self, store: ArticleStore) -> None:
        """모든 매물이 이미 DB에 있으면 빈 리스트를 반환한다."""
        await store.upsert_article(_make_article("1"))
        await store.upsert_article(_make_article("2"))

        articles = [_make_article("1"), _make_article("2")]
        new = await detect_new_articles(articles, store)
        assert new == []


class TestDetectPriceChanges:
    """detect_price_changes 테스트."""

    @pytest.mark.asyncio()
    async def test_price_changed(self, store: ArticleStore) -> None:
        """가격이 변경된 매물을 감지한다."""
        await store.upsert_article(_make_article("1", price="40000"))

        articles = [_make_article("1", price="45000")]
        changes = await detect_price_changes(articles, store)

        assert len(changes) == 1
        assert changes[0].old_price == "40000"
        assert changes[0].new_price == "45000"

    @pytest.mark.asyncio()
    async def test_price_unchanged(self, store: ArticleStore) -> None:
        """가격이 동일하면 빈 리스트를 반환한다."""
        await store.upsert_article(_make_article("1", price="45000"))

        articles = [_make_article("1", price="45000")]
        changes = await detect_price_changes(articles, store)
        assert changes == []

    @pytest.mark.asyncio()
    async def test_new_article_not_detected_as_change(self, store: ArticleStore) -> None:
        """신규 매물은 가격 변동으로 감지되지 않는다."""
        articles = [_make_article("999", price="50000")]
        changes = await detect_price_changes(articles, store)
        assert changes == []


class TestDetectRemoved:
    """detect_removed 테스트."""

    @pytest.mark.asyncio()
    async def test_removed_articles(self, store: ArticleStore) -> None:
        """API에서 사라진 매물을 감지한다."""
        await store.upsert_article(_make_article("1"))
        await store.upsert_article(_make_article("2"))
        await store.upsert_article(_make_article("3"))

        current_ids = {"1", "3"}
        removed = await detect_removed("12345", current_ids, store)

        assert set(removed) == {"2"}

    @pytest.mark.asyncio()
    async def test_no_removed(self, store: ArticleStore) -> None:
        """모든 매물이 API에 남아있으면 빈 리스트를 반환한다."""
        await store.upsert_article(_make_article("1"))
        await store.upsert_article(_make_article("2"))

        current_ids = {"1", "2"}
        removed = await detect_removed("12345", current_ids, store)
        assert removed == []

    @pytest.mark.asyncio()
    async def test_empty_db(self, store: ArticleStore) -> None:
        """DB가 비어있으면 삭제 감지 없음."""
        removed = await detect_removed("12345", {"1"}, store)
        assert removed == []


class TestRunDetection:
    """run_detection 통합 테스트."""

    @pytest.mark.asyncio()
    async def test_full_cycle_new_articles(self, store: ArticleStore) -> None:
        """신규 매물 감지 후 DB에 저장된다."""
        articles = [_make_article("1"), _make_article("2")]
        result = await run_detection(articles, "12345", store)

        assert len(result.new) == 2
        assert result.price_changed == []
        assert result.removed == []
        assert result.has_updates is True

        # DB에 저장되었는지 확인
        assert await store.get_article("1") is not None
        assert await store.get_article("2") is not None

    @pytest.mark.asyncio()
    async def test_full_cycle_price_change(self, store: ArticleStore) -> None:
        """가격 변동 감지 및 DB 반영."""
        await store.upsert_article(_make_article("1", price="40000"))

        articles = [_make_article("1", price="50000")]
        result = await run_detection(articles, "12345", store)

        assert result.new == []
        assert len(result.price_changed) == 1
        # DB에 새 가격이 반영되었는지 확인
        row = await store.get_article("1")
        assert row is not None
        assert row["price"] == "50000"

    @pytest.mark.asyncio()
    async def test_full_cycle_removed(self, store: ArticleStore) -> None:
        """삭제 감지 및 비활성 마킹."""
        await store.upsert_article(_make_article("1"))
        await store.upsert_article(_make_article("2"))

        articles = [_make_article("1")]
        result = await run_detection(articles, "12345", store)

        assert set(result.removed) == {"2"}
        row = await store.get_article("2")
        assert row is not None
        assert row["is_active"] == 0

    @pytest.mark.asyncio()
    async def test_no_updates(self, store: ArticleStore) -> None:
        """변동이 없으면 has_updates가 False이다."""
        await store.upsert_article(_make_article("1", price="45000"))

        articles = [_make_article("1", price="45000")]
        result = await run_detection(articles, "12345", store)

        assert result.has_updates is False
        assert result.summary == "변동 없음"


class TestDetectionResult:
    """DetectionResult 테스트."""

    def test_summary_with_all_types(self) -> None:
        result = DetectionResult(
            new=[_make_article("1")],
            price_changed=[],  # simplified
            removed=["3"],
        )
        assert "신규 1건" in result.summary
        assert "삭제 1건" in result.summary

    def test_summary_empty(self) -> None:
        result = DetectionResult()
        assert result.summary == "변동 없음"
        assert result.has_updates is False
