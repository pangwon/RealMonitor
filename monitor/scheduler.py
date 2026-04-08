"""모니터링 스케줄러.

APScheduler의 AsyncIOScheduler를 사용하여
config.yaml에 정의된 주기로 각 단지의 매물을 모니터링한다.
"""

from __future__ import annotations

from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from db.store import ArticleStore
from monitor.detector import run_detection
from monitor.filters import filter_articles
from monitor.naver_api import NaverLandClient
from monitor.parser import Article, parse_articles
from notifier.base import AbstractNotifier, format_article


async def _send_notifications(
    notifiers: list[AbstractNotifier],
    message: str,
    articles: list[Article],
) -> None:
    """모든 활성 Notifier로 알림을 전송한다. 실패 시 로깅만 한다."""
    for notifier in notifiers:
        try:
            await notifier.send(message, articles)
        except Exception as exc:
            logger.error("알림 전송 실패 ({}): {}", type(notifier).__name__, exc)


async def check_target(
    target: dict[str, Any],
    client: NaverLandClient,
    store: ArticleStore,
    notifiers: list[AbstractNotifier],
) -> None:
    """단일 모니터링 대상(단지)을 체크한다.

    API 조회 → 파싱 → 필터링 → 감지 → 알림 → DB 갱신.

    Args:
        target: config.yaml의 targets 항목.
        client: 네이버 부동산 API 클라이언트.
        store: 매물 이력 저장소.
        notifiers: 활성 알림 발송기 리스트.
    """
    name = target.get("name", "알 수 없음")
    complex_id = target["complex_id"]
    trade_type = target.get("trade_type", "전세")
    filter_config = target.get("filters")

    logger.info("체크 시작: {} (complex_id={})", name, complex_id)

    try:
        # 1. API 조회
        raw_articles = await client.fetch_all_articles(complex_id, trade_type)

        # 2. 파싱
        articles = parse_articles(raw_articles, complex_id, name)

        # 3. 필터링
        filtered = filter_articles(articles, filter_config)

        # 4. 감지 (내부에서 DB 갱신도 수행)
        result = await run_detection(filtered, complex_id, store)

        # 5. 알림
        if result.has_updates:
            if result.new:
                await _send_notifications(
                    notifiers,
                    f"🏠 {name} — 새 매물 {len(result.new)}건",
                    result.new,
                )
            if result.price_changed:
                price_articles = [pc.article for pc in result.price_changed]
                await _send_notifications(
                    notifiers,
                    f"💰 {name} — 가격 변동 {len(result.price_changed)}건",
                    price_articles,
                )

        logger.info("체크 완료: {} — {}", name, result.summary)

    except Exception as exc:
        logger.error("체크 실패: {} — {}", name, exc)


async def run_once(
    config: dict[str, Any],
    client: NaverLandClient,
    store: ArticleStore,
    notifiers: list[AbstractNotifier],
) -> None:
    """모든 대상을 1회 순차 체크한다.

    Args:
        config: 전체 config.yaml 딕셔너리.
        client: 네이버 부동산 API 클라이언트.
        store: 매물 이력 저장소.
        notifiers: 활성 알림 발송기 리스트.
    """
    targets = config.get("targets", [])
    if not targets:
        logger.warning("모니터링 대상이 없습니다 (config.yaml targets 확인)")
        return

    for target in targets:
        await check_target(target, client, store, notifiers)


def create_scheduler(
    config: dict[str, Any],
    client: NaverLandClient,
    store: ArticleStore,
    notifiers: list[AbstractNotifier],
) -> AsyncIOScheduler:
    """APScheduler를 생성하고 주기적 모니터링 작업을 등록한다.

    Args:
        config: 전체 config.yaml 딕셔너리.
        client: 네이버 부동산 API 클라이언트.
        store: 매물 이력 저장소.
        notifiers: 활성 알림 발송기 리스트.

    Returns:
        설정된 AsyncIOScheduler (아직 start되지 않은 상태).
    """
    interval_minutes = config.get("schedule", {}).get("interval_minutes", 10)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_once,
        "interval",
        minutes=interval_minutes,
        args=[config, client, store, notifiers],
        id="monitor_job",
        name=f"매물 모니터링 (매 {interval_minutes}분)",
        max_instances=1,
    )

    logger.info("스케줄러 등록: 매 {}분 간격", interval_minutes)
    return scheduler
