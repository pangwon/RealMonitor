"""Slack 알림 발송 모듈.

Incoming Webhook URL을 통해 Block Kit 형식으로
매물 알림을 전송한다.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from monitor.parser import Article
from notifier.base import AbstractNotifier, format_article


class SlackNotifier(AbstractNotifier):
    """Slack Webhook을 통한 알림 발송."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send(self, message: str, articles: list[Article]) -> None:
        """매물 알림을 Slack으로 전송한다.

        Block Kit 형식으로 매물별 섹션을 구성하여 전송한다.

        Args:
            message: 알림 헤더 메시지.
            articles: 알림에 포함할 매물 리스트.
        """
        if not articles:
            return

        blocks = self._build_blocks(message, articles)
        payload: dict[str, Any] = {"blocks": blocks}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack 전송 실패: {}", exc)

    def _build_blocks(self, header: str, articles: list[Article]) -> list[dict[str, Any]]:
        """Block Kit 블록 리스트를 생성한다.

        Args:
            header: 알림 헤더.
            articles: 매물 리스트.

        Returns:
            Slack Block Kit 블록 리스트.
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header, "emoji": True},
            },
            {"type": "divider"},
        ]

        for article in articles:
            text = format_article(article)
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            )
            blocks.append({"type": "divider"})

        return blocks
