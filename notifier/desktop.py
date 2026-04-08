"""Desktop 네이티브 알림 발송 모듈.

plyer를 사용하여 OS 네이티브 알림을 표시한다.
"""

from __future__ import annotations

from loguru import logger

from monitor.parser import Article
from notifier.base import AbstractNotifier


class DesktopNotifier(AbstractNotifier):
    """OS 네이티브 데스크톱 알림 발송."""

    def __init__(self, app_name: str = "네이버 부동산 모니터") -> None:
        self._app_name = app_name

    async def send(self, message: str, articles: list[Article]) -> None:
        """매물 알림을 데스크톱 알림으로 표시한다.

        각 매물에 대해 개별 알림을 표시한다.

        Args:
            message: 알림 제목.
            articles: 알림에 포함할 매물 리스트.
        """
        if not articles:
            return

        try:
            from plyer import notification
        except ImportError:
            logger.error("plyer가 설치되지 않아 데스크톱 알림을 보낼 수 없습니다")
            return

        for article in articles:
            body = (
                f"{article.complex_name} | "
                f"{article.trade_type} {article.price} | "
                f"전용 {article.area_exclusive}㎡ {article.floor}층"
            )
            try:
                notification.notify(
                    title=message,
                    message=body,
                    app_name=self._app_name,
                    timeout=10,
                )
            except Exception as exc:
                logger.error("데스크톱 알림 실패: {}", exc)
