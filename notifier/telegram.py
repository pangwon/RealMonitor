"""Telegram 알림 발송 모듈.

python-telegram-bot 라이브러리를 사용하여
Telegram 채팅방에 매물 알림을 전송한다.
"""

from __future__ import annotations

from telegram import Bot
from loguru import logger

from monitor.parser import Article
from notifier.base import AbstractNotifier, format_article

# Telegram 메시지 최대 길이
_MAX_MESSAGE_LENGTH = 4096


class TelegramNotifier(AbstractNotifier):
    """Telegram 봇을 통한 알림 발송."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot = Bot(token=bot_token)
        self._chat_id = chat_id

    async def send(self, message: str, articles: list[Article]) -> None:
        """매물 알림을 Telegram으로 전송한다.

        메시지가 4096자를 초과하면 자동으로 분할 전송한다.

        Args:
            message: 알림 헤더 메시지.
            articles: 알림에 포함할 매물 리스트.
        """
        if not articles:
            return

        chunks = self._build_chunks(message, articles)
        for chunk in chunks:
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=chunk,
                )
            except Exception as exc:
                logger.error("Telegram 전송 실패: {}", exc)

    def _build_chunks(self, header: str, articles: list[Article]) -> list[str]:
        """메시지를 4096자 이하 청크로 분할한다.

        Args:
            header: 알림 헤더.
            articles: 매물 리스트.

        Returns:
            분할된 메시지 문자열 리스트.
        """
        chunks: list[str] = []
        current = header + "\n\n"

        for article in articles:
            formatted = format_article(article)
            entry = formatted + "\n\n"

            if len(current) + len(entry) > _MAX_MESSAGE_LENGTH:
                chunks.append(current.rstrip())
                current = entry
            else:
                current += entry

        if current.strip():
            chunks.append(current.rstrip())

        return chunks
