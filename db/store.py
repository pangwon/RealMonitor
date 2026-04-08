"""SQLite 기반 매물 이력 저장소.

aiosqlite를 사용하여 매물 데이터의 CRUD 및
가격 변동 이력을 관리한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from loguru import logger

from monitor.parser import Article

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    complex_id TEXT NOT NULL,
    trade_type TEXT,
    price TEXT,
    area_exclusive REAL,
    floor INTEGER,
    direction TEXT,
    description TEXT,
    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    price_history TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_articles_complex_id ON articles(complex_id);
"""


class ArticleStore:
    """매물 이력 SQLite 저장소.

    테이블 자동 생성, 신규 매물 삽입, 기존 매물 갱신,
    가격 변동 감지 및 비활성 매물 마킹을 처리한다.
    """

    def __init__(self, db_path: str = "articles.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """DB 연결을 열고 테이블을 초기화한다."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.execute(_CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info("DB 연결 완료: {}", self._db_path)

    async def close(self) -> None:
        """DB 연결을 종료한다."""
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> ArticleStore:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _now_iso(self) -> str:
        """현재 UTC 시각을 ISO 형식 문자열로 반환한다."""
        return datetime.now(timezone.utc).isoformat()

    async def get_article(self, article_id: str) -> dict[str, Any] | None:
        """article_id로 매물 레코드를 조회한다.

        Args:
            article_id: 매물 고유 ID.

        Returns:
            매물 딕셔너리 또는 None.
        """
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM articles WHERE article_id = ?",
            (article_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_active_article_ids(self, complex_id: str) -> set[str]:
        """특정 단지의 활성 매물 ID 목록을 조회한다.

        Args:
            complex_id: 단지 ID.

        Returns:
            활성 매물 article_id 집합.
        """
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT article_id FROM articles WHERE complex_id = ? AND is_active = 1",
            (complex_id,),
        )
        rows = await cursor.fetchall()
        return {row["article_id"] for row in rows}

    async def upsert_article(self, article: Article) -> tuple[bool, bool]:
        """매물을 삽입하거나 갱신한다.

        - DB에 없으면 새로 삽입.
        - 이미 있으면 last_seen_at 갱신 및 is_active=1로 복원.
        - 가격이 변경되었으면 price_history에 기록.

        Args:
            article: 정규화된 Article.

        Returns:
            (is_new, price_changed) 튜플.
        """
        assert self._db is not None
        now = self._now_iso()
        existing = await self.get_article(article.article_id)

        if existing is None:
            # 신규 매물 삽입
            await self._db.execute(
                """
                INSERT INTO articles
                    (article_id, complex_id, trade_type, price,
                     area_exclusive, floor, direction, description,
                     first_seen_at, last_seen_at, price_history, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', 1)
                """,
                (
                    article.article_id,
                    article.complex_id,
                    article.trade_type,
                    article.price,
                    article.area_exclusive,
                    article.floor,
                    article.direction,
                    article.description,
                    now,
                    now,
                ),
            )
            await self._db.commit()
            logger.debug("신규 매물 삽입: {}", article.article_id)
            return (True, False)

        # 기존 매물 갱신
        price_changed = existing["price"] != article.price

        if price_changed:
            # 가격 변동 이력 추가
            history: list[dict[str, str]] = json.loads(existing["price_history"] or "[]")
            history.append({"price": existing["price"], "date": now})
            history_json = json.dumps(history, ensure_ascii=False)

            await self._db.execute(
                """
                UPDATE articles
                SET price = ?, price_history = ?, last_seen_at = ?, is_active = 1
                WHERE article_id = ?
                """,
                (article.price, history_json, now, article.article_id),
            )
            logger.info(
                "가격 변동 감지: {} ({} → {})",
                article.article_id,
                existing["price"],
                article.price,
            )
        else:
            await self._db.execute(
                """
                UPDATE articles
                SET last_seen_at = ?, is_active = 1
                WHERE article_id = ?
                """,
                (now, article.article_id),
            )

        await self._db.commit()
        return (False, price_changed)

    async def mark_inactive(self, complex_id: str, active_article_ids: set[str]) -> list[str]:
        """API에서 사라진 매물을 비활성으로 마킹한다.

        Args:
            complex_id: 단지 ID.
            active_article_ids: 현재 API에서 확인된 매물 ID 집합.

        Returns:
            비활성 처리된 article_id 리스트.
        """
        assert self._db is not None
        db_active_ids = await self.get_active_article_ids(complex_id)
        removed_ids = db_active_ids - active_article_ids

        if not removed_ids:
            return []

        now = self._now_iso()
        placeholders = ",".join("?" for _ in removed_ids)
        await self._db.execute(
            f"UPDATE articles SET is_active = 0, last_seen_at = ? "
            f"WHERE article_id IN ({placeholders})",
            (now, *removed_ids),
        )
        await self._db.commit()
        logger.info("비활성 처리: {}건 (complex_id={})", len(removed_ids), complex_id)
        return list(removed_ids)
