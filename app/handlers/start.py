from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.db.session import async_session
from app.db.queries import get_user_by_telegram_id
from app.keyboards.menus import main_menu
from app.texts import messages as msg

router = Router()


@router.message(CommandStart(), ~F.from_user.id.in_([settings.admin_telegram_id]))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Команда /start для обычных пользователей."""
    await state.clear()

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)

    if user:
        # Подбираем меню по роли
        from app.keyboards.menus import (
            student_menu,
            teacher_menu,
            dekan_menu,
            rector_menu,
        )

        menus = {
            "student": student_menu,
            "teacher": teacher_menu,
            "dekan": dekan_menu,
            "rector": rector_menu,
        }

        menu_func = menus.get(user.role)
        kb = menu_func() if menu_func else None

        await message.answer(
            f"С возвращением, {user.full_name}!\n\n" f"Ваша роль: {user.role}",
            reply_markup=kb,
        )
        return

    await message.answer(
        msg.START,
        reply_markup=main_menu(),
    )
