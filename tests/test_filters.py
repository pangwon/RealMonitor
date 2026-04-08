"""monitor/filters.py 테스트."""

from __future__ import annotations

import pytest

from monitor.filters import ArticleFilter, filter_articles, _parse_price
from monitor.parser import Article


def _make_article(
    price: str = "50000",
    area_exclusive: float = 84.0,
    floor: int = 10,
    direction: str = "남향",
) -> Article:
    """테스트용 Article을 생성한다."""
    return Article(
        article_id="1",
        complex_id="12345",
        complex_name="테스트",
        trade_type="전세",
        price=price,
        area_exclusive=area_exclusive,
        area_supply=112.0,
        floor=floor,
        direction=direction,
        description="",
        article_url="https://example.com",
    )


class TestParsePrice:
    """_parse_price 테스트."""

    def test_simple_number(self) -> None:
        assert _parse_price("45000") == 45000

    def test_monthly_rent(self) -> None:
        """월세 '보증금/월세'에서 보증금만 추출한다."""
        assert _parse_price("10000/150") == 10000

    def test_with_comma(self) -> None:
        assert _parse_price("45,000") == 45000

    def test_invalid_string(self) -> None:
        assert _parse_price("협의") is None

    def test_empty_string(self) -> None:
        assert _parse_price("") is None


class TestArticleFilterFromConfig:
    """ArticleFilter.from_config 테스트."""

    def test_full_config(self) -> None:
        config = {
            "price_min": 40000,
            "price_max": 80000,
            "area_min": 80,
            "area_max": 120,
            "floor_min": 5,
            "floor_max": 20,
            "direction": "남",
        }
        f = ArticleFilter.from_config(config)
        assert f.price_min == 40000
        assert f.price_max == 80000
        assert f.area_min == 80
        assert f.area_max == 120
        assert f.floor_min == 5
        assert f.floor_max == 20
        assert f.direction == "남"

    def test_none_config(self) -> None:
        """None이면 모든 필드가 None인 빈 필터를 반환한다."""
        f = ArticleFilter.from_config(None)
        assert f.price_min is None
        assert f.direction is None

    def test_empty_config(self) -> None:
        f = ArticleFilter.from_config({})
        assert f.price_min is None

    def test_partial_config(self) -> None:
        f = ArticleFilter.from_config({"price_min": 40000})
        assert f.price_min == 40000
        assert f.price_max is None


class TestArticleFilterMatches:
    """ArticleFilter.matches 테스트."""

    def test_no_filters_passes_all(self) -> None:
        """필터 조건이 없으면 모든 매물을 통과시킨다."""
        f = ArticleFilter()
        assert f.matches(_make_article()) is True

    def test_price_min_pass(self) -> None:
        f = ArticleFilter(price_min=40000)
        assert f.matches(_make_article(price="50000")) is True

    def test_price_min_fail(self) -> None:
        f = ArticleFilter(price_min=60000)
        assert f.matches(_make_article(price="50000")) is False

    def test_price_max_pass(self) -> None:
        f = ArticleFilter(price_max=60000)
        assert f.matches(_make_article(price="50000")) is True

    def test_price_max_fail(self) -> None:
        f = ArticleFilter(price_max=40000)
        assert f.matches(_make_article(price="50000")) is False

    def test_price_range(self) -> None:
        f = ArticleFilter(price_min=40000, price_max=60000)
        assert f.matches(_make_article(price="50000")) is True
        assert f.matches(_make_article(price="30000")) is False
        assert f.matches(_make_article(price="70000")) is False

    def test_area_min_pass(self) -> None:
        f = ArticleFilter(area_min=80.0)
        assert f.matches(_make_article(area_exclusive=84.0)) is True

    def test_area_min_fail(self) -> None:
        f = ArticleFilter(area_min=100.0)
        assert f.matches(_make_article(area_exclusive=84.0)) is False

    def test_area_max_pass(self) -> None:
        f = ArticleFilter(area_max=120.0)
        assert f.matches(_make_article(area_exclusive=84.0)) is True

    def test_area_max_fail(self) -> None:
        f = ArticleFilter(area_max=60.0)
        assert f.matches(_make_article(area_exclusive=84.0)) is False

    def test_floor_min_pass(self) -> None:
        f = ArticleFilter(floor_min=5)
        assert f.matches(_make_article(floor=10)) is True

    def test_floor_min_fail(self) -> None:
        f = ArticleFilter(floor_min=15)
        assert f.matches(_make_article(floor=10)) is False

    def test_floor_max_pass(self) -> None:
        f = ArticleFilter(floor_max=20)
        assert f.matches(_make_article(floor=10)) is True

    def test_floor_max_fail(self) -> None:
        f = ArticleFilter(floor_max=5)
        assert f.matches(_make_article(floor=10)) is False

    def test_direction_partial_match(self) -> None:
        """방향은 부분 일치로 검사한다 ('남' in '남향')."""
        f = ArticleFilter(direction="남")
        assert f.matches(_make_article(direction="남향")) is True
        assert f.matches(_make_article(direction="남서향")) is True
        assert f.matches(_make_article(direction="동향")) is False

    def test_combined_filters(self) -> None:
        """여러 조건을 동시에 적용한다."""
        f = ArticleFilter(price_min=40000, area_min=80, floor_min=5, direction="남")
        assert f.matches(_make_article(price="50000", area_exclusive=84.0, floor=10, direction="남향")) is True
        # 가격 미달
        assert f.matches(_make_article(price="30000", area_exclusive=84.0, floor=10, direction="남향")) is False
        # 면적 미달
        assert f.matches(_make_article(price="50000", area_exclusive=59.0, floor=10, direction="남향")) is False

    def test_unparseable_price_passes_filter(self) -> None:
        """가격 파싱 불가 시 가격 필터를 통과시킨다."""
        f = ArticleFilter(price_min=40000)
        assert f.matches(_make_article(price="협의")) is True


class TestFilterArticles:
    """filter_articles 통합 테스트."""

    def test_no_filter_returns_all(self) -> None:
        """필터 없이 호출하면 모든 매물을 반환한다."""
        articles = [_make_article(price="30000"), _make_article(price="50000")]
        result = filter_articles(articles)
        assert len(result) == 2

    def test_filter_narrows_results(self) -> None:
        articles = [
            _make_article(price="30000"),
            _make_article(price="50000"),
            _make_article(price="70000"),
        ]
        result = filter_articles(articles, {"price_min": 40000, "price_max": 60000})
        assert len(result) == 1
        assert result[0].price == "50000"

    def test_empty_articles(self) -> None:
        result = filter_articles([], {"price_min": 40000})
        assert result == []
