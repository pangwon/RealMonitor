"""pytest 공통 설정."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_response() -> dict:
    """샘플 API 응답 JSON을 로드한다."""
    with open(FIXTURES_DIR / "sample_articles_response.json", encoding="utf-8") as f:
        return json.load(f)
