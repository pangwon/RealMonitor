"""알림 패키지.

config.yaml의 notification 섹션을 기반으로
활성화된 Notifier 인스턴스를 생성한다.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from notifier.base import AbstractNotifier


def create_notifiers(config: dict[str, Any]) -> list[AbstractNotifier]:
    """설정에서 enabled: true인 알림 채널의 Notifier를 생성한다.

    Args:
        config: config.yaml의 notification 섹션 딕셔너리.

    Returns:
        활성화된 Notifier 인스턴스 리스트.
    """
    notifiers: list[AbstractNotifier] = []

    # Telegram
    tg_cfg = config.get("telegram", {})
    if tg_cfg.get("enabled"):
        from notifier.telegram import TelegramNotifier

        bot_token = tg_cfg.get("bot_token", "")
        chat_id = tg_cfg.get("chat_id", "")
        if bot_token and chat_id:
            notifiers.append(TelegramNotifier(bot_token, chat_id))
            logger.info("Telegram 알림 활성화")
        else:
            logger.warning("Telegram 설정 누락 (bot_token 또는 chat_id)")

    # Slack
    slack_cfg = config.get("slack", {})
    if slack_cfg.get("enabled"):
        from notifier.slack import SlackNotifier

        webhook_url = slack_cfg.get("webhook_url", "")
        if webhook_url:
            notifiers.append(SlackNotifier(webhook_url))
            logger.info("Slack 알림 활성화")
        else:
            logger.warning("Slack 설정 누락 (webhook_url)")

    # Desktop
    desktop_cfg = config.get("desktop", {})
    if desktop_cfg.get("enabled"):
        from notifier.desktop import DesktopNotifier

        notifiers.append(DesktopNotifier())
        logger.info("Desktop 알림 활성화")

    return notifiers
