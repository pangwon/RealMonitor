"""알림 발송 추상 클래스.

모든 Notifier 구현체가 상속해야 하는 인터페이스를 정의한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from monitor.parser import Article


class AbstractNotifier(ABC):
    """알림 발송 추상 베이스 클래스."""

    @abstractmethod
    async def send(self, message: str, articles: list[Article]) -> None:
        """알림을 발송한다.

        Args:
            message: 알림 제목/헤더 메시지.
            articles: 알림에 포함할 매물 리스트.
        """


def format_article(article: Article) -> str:
    """매물 정보를 보기 좋은 텍스트로 포맷한다.

    Args:
        article: 포맷할 매물.

    Returns:
        이모지 포함 포맷 문자열.
    """
    location = article.complex_name
    if article.dong:
        location += f" {article.dong}"
    if article.ho:
        location += f"/{article.ho}"

    lines = [
        "🏠 새 매물 발견!",
        "━━━━━━━━━━━━━━",
        f"📍 {location}",
        f"💰 {article.trade_type} {article.price}",
        f"📐 전용 {article.area_exclusive}㎡ / 공급 {article.area_supply}㎡",
        f"🏢 {article.floor}층 / {article.direction}" if article.direction else f"🏢 {article.floor}층",
    ]
    if article.description:
        lines.append(f'📝 "{article.description}"')
    lines.append(f"🔗 {article.article_url}")
    lines.append("━━━━━━━━━━━━━━")

    return "\n".join(lines)
