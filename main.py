"""네이버 부동산 매물 모니터링 봇 엔트리포인트.

스케줄러 모드(주기적 모니터링) 또는 --once(1회 체크) 모드로 실행한다.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger

from db.store import ArticleStore
from monitor.naver_api import NaverLandClient
from monitor.parser import Article
from monitor.scheduler import create_scheduler, run_once
from notifier import create_notifiers
from notifier.base import AbstractNotifier


def load_config(config_path: str) -> dict[str, Any]:
    """config.yaml을 로드하고 검증한다.

    Args:
        config_path: 설정 파일 경로.

    Returns:
        설정 딕셔너리.

    Raises:
        FileNotFoundError: 설정 파일이 없을 때.
        ValueError: 필수 설정이 누락되었을 때.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")

    with open(path, encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    # 필수 섹션 검증
    if not config.get("targets"):
        raise ValueError("config.yaml에 targets가 정의되지 않았습니다")

    for i, target in enumerate(config["targets"]):
        if not target.get("complex_id"):
            raise ValueError(f"targets[{i}]에 complex_id가 없습니다")

    return config


def setup_logging() -> None:
    """loguru 로깅을 설정한다."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> — "
        "<level>{message}</level>",
    )
    logger.add(
        "logs/monitor_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description="네이버 부동산 매물 모니터링 봇",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="1회 체크 후 종료 (스케줄러 없이)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="설정 파일 경로 (기본: config.yaml)",
    )
    return parser.parse_args()


async def _send_startup_notification(
    notifiers: list[AbstractNotifier],
    config: dict[str, Any],
) -> None:
    """시작 알림을 전송한다."""
    targets = config.get("targets", [])
    target_names = ", ".join(t.get("name", t["complex_id"]) for t in targets)
    interval = config.get("schedule", {}).get("interval_minutes", 10)

    message = (
        f"🚀 모니터링 시작\n"
        f"━━━━━━━━━━━━━━\n"
        f"📋 대상: {target_names}\n"
        f"⏱️ 주기: {interval}분\n"
        f"━━━━━━━━━━━━━━"
    )

    for notifier in notifiers:
        try:
            # 빈 articles 리스트와 함께 시작 메시지 전송
            await notifier.send(message, [])
        except Exception as exc:
            logger.error("시작 알림 전송 실패 ({}): {}", type(notifier).__name__, exc)


async def async_main(args: argparse.Namespace) -> None:
    """비동기 메인 로직."""
    config = load_config(args.config)

    notifiers = create_notifiers(config.get("notification", {}))
    if not notifiers:
        logger.warning("활성화된 알림 채널이 없습니다")

    async with NaverLandClient() as client, ArticleStore() as store:
        if args.once:
            # 1회 체크 모드
            logger.info("1회 체크 모드로 실행")
            await run_once(config, client, store, notifiers)
            logger.info("1회 체크 완료")
            return

        # 스케줄러 모드
        await _send_startup_notification(notifiers, config)

        scheduler = create_scheduler(config, client, store, notifiers)

        # 시작 직후 1회 즉시 실행
        await run_once(config, client, store, notifiers)

        # Graceful shutdown 설정
        stop_event = asyncio.Event()

        def _handle_signal() -> None:
            logger.info("종료 시그널 수신 — 스케줄러 정지 중...")
            scheduler.shutdown(wait=False)
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal)

        scheduler.start()
        logger.info("스케줄러 시작 — Ctrl+C로 종료")

        await stop_event.wait()
        logger.info("모니터링 종료")


def main() -> None:
    """프로그램 엔트리포인트."""
    load_dotenv()
    setup_logging()
    args = parse_args()

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료")
    except Exception as exc:
        logger.exception("예상치 못한 에러: {}", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
