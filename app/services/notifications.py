from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserSettings


async def get_or_create_settings(session: AsyncSession, user_id: int) -> UserSettings:
    """Получить настройки или создать дефолтные."""
    settings = await session.scalar(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    if not settings:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def notify_user(
    bot: Bot,
    session: AsyncSession,
    user_id: int,
    text: str,
    notification_type: str = "general",
) -> bool:
    """Отправить уведомление с учётом настроек.

    notification_type: 'new_cert' | 'new_substitution' | 'general'
    Возвращает True, если отправлено.
    """
    user = await session.get(User, user_id)
    if not user or not user.telegram_id:
        return False

    settings = await get_or_create_settings(session, user_id)

    # Глобальный выключатель
    if not settings.notifications_enabled:
        return False

    # Конкретные типы
    if notification_type == "new_cert" and not settings.notify_new_certs:
        return False
    if (
        notification_type == "new_substitution"
        and not settings.notify_new_substitutions
    ):
        return False

    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
        return True
    except Exception:
        return False


async def notify_role(
    bot: Bot,
    session: AsyncSession,
    role: str,
    text: str,
    notification_type: str = "general",
) -> int:
    """Отправить всем пользователям с ролью. Возвращает количество отправленных."""
    result = await session.execute(select(User).where(User.role == role))
    users = result.scalars().all()

    sent = 0
    for user in users:
        ok = await notify_user(bot, session, user.id, text, notification_type)
        if ok:
            sent += 1
    return sent
