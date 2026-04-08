"""monitor/parser.py 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from monitor.parser import Article, parse_article, parse_articles

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_response() -> dict:
    """샘플 API 응답 JSON을 로드한다."""
    with open(FIXTURES_DIR / "sample_articles_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def raw_articles(sample_response: dict) -> list[dict]:
    return sample_response["articleList"]


class TestParseArticle:
    """parse_article 단위 테스트."""

    def test_basic_fields(self, raw_articles: list[dict]) -> None:
        """기본 필드가 올바르게 파싱된다."""
        article = parse_article(raw_articles[0], "12345", "래미안 원베일리")

        assert article.article_id == "2468001234"
        assert article.complex_id == "12345"
        assert article.complex_name == "래미안 원베일리"
        assert article.trade_type == "전세"
        assert article.price == "45000"

    def test_area_fields(self, raw_articles: list[dict]) -> None:
        """면적 필드가 float로 파싱된다."""
        article = parse_article(raw_articles[0], "12345")

        assert article.area_exclusive == pytest.approx(84.99)
        assert article.area_supply == pytest.approx(112.03)

    def test_floor_parsed_from_floor_info(self, raw_articles: list[dict]) -> None:
        """floorInfo '12/25'에서 층수 12를 추출한다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.floor == 12

    def test_direction(self, raw_articles: list[dict]) -> None:
        """방향이 올바르게 파싱된다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.direction == "남향"

    def test_description(self, raw_articles: list[dict]) -> None:
        """설명이 올바르게 파싱된다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.description == "깨끗하게 사용한 집입니다"

    def test_dong_ho(self, raw_articles: list[dict]) -> None:
        """동/호 정보가 파싱된다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.dong == "101동"
        assert article.ho == "1201"

    def test_tags(self, raw_articles: list[dict]) -> None:
        """태그 리스트가 파싱된다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.tags == ["역세권", "학군우수"]

    def test_article_url(self, raw_articles: list[dict]) -> None:
        """매물 URL이 올바르게 생성된다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.article_url == (
            "https://new.land.naver.com/complexes/12345?articleNo=2468001234"
        )

    def test_monthly_rent_price_format(self, raw_articles: list[dict]) -> None:
        """월세 가격이 '보증금/월세' 형식으로 파싱된다."""
        article = parse_article(raw_articles[2], "12345")
        assert article.price == "10000/150"
        assert article.trade_type == "월세"

    def test_empty_description(self, raw_articles: list[dict]) -> None:
        """빈 설명은 빈 문자열로 처리된다."""
        article = parse_article(raw_articles[2], "12345")
        assert article.description == ""

    def test_empty_ho(self, raw_articles: list[dict]) -> None:
        """호 정보가 없으면 빈 문자열이다."""
        article = parse_article(raw_articles[2], "12345")
        assert article.ho == ""

    def test_complex_name_fallback(self, raw_articles: list[dict]) -> None:
        """complex_name 미전달 시 API 응답의 complexName을 사용한다."""
        article = parse_article(raw_articles[0], "12345")
        assert article.complex_name == "래미안 원베일리"

    def test_missing_fields_use_defaults(self) -> None:
        """필드가 누락된 경우 기본값을 사용한다."""
        raw: dict = {"articleNo": "999"}
        article = parse_article(raw, "12345")

        assert article.article_id == "999"
        assert article.price == ""
        assert article.area_exclusive == 0.0
        assert article.floor == 0
        assert article.direction == ""
        assert article.tags == []


class TestParseArticles:
    """parse_articles 테스트."""

    def test_parses_all_articles(self, raw_articles: list[dict]) -> None:
        """전체 매물 리스트가 파싱된다."""
        articles = parse_articles(raw_articles, "12345", "래미안 원베일리")

        assert len(articles) == 3
        assert all(isinstance(a, Article) for a in articles)

    def test_empty_list(self) -> None:
        """빈 리스트는 빈 결과를 반환한다."""
        assert parse_articles([], "12345") == []

    def test_article_ids_unique(self, raw_articles: list[dict]) -> None:
        """파싱 결과의 article_id가 모두 다르다."""
        articles = parse_articles(raw_articles, "12345")
        ids = [a.article_id for a in articles]
        assert len(ids) == len(set(ids))
