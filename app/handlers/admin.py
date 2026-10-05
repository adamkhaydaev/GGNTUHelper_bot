from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from sqlalchemy import select, func

from app.config import settings
from app.db.session import async_session
from app.db.models import User, Student, Teacher, AccessCode, Substitution
from app.keyboards.menus import admin_menu
from app.texts import messages as msg

router = Router()

# Фильтр админа — используется во всех хендлерах
ADMIN = F.from_user.id == settings.admin_telegram_id


@router.message(Command("start"), ADMIN)
async def admin_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(msg.ADMIN_WELCOME, reply_markup=admin_menu())


@router.message(Command("stats"), ADMIN)
async def cmd_stats(message: Message) -> None:
    await send_stats(message)


@router.message(F.text == "📊 Статистика", ADMIN)
async def btn_stats(message: Message) -> None:
    await send_stats(message)


async def send_stats(message: Message) -> None:
    async with async_session() as session:
        users_total = await session.scalar(select(func.count(User.id)))
        students_total = await session.scalar(select(func.count(Student.id)))
        teachers_total = await session.scalar(select(func.count(Teacher.id)))
        subs_total = await session.scalar(select(func.count(Substitution.id)))
        codes_total = await session.scalar(
            select(func.count(AccessCode.id)).where(AccessCode.is_active == True)
        )

    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {users_total}\n"
        f"🎓 Студентов: {students_total}\n"
        f"👨‍🏫 Преподавателей: {teachers_total}\n"
        f"🔄 Замен: {subs_total}\n"
        f"🔑 Активных кодов: {codes_total}",
    )


@router.message(F.text == "👥 Пользователи", ADMIN)
async def btn_users(message: Message) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(50)
        )
        users = result.scalars().all()

    if not users:
        await message.answer("Пока никто не зарегистрирован.")
        return

    lines = ["👥 <b>Последние 50 пользователей</b>\n"]
    for u in users:
        tg = f"@{u.telegram_id}" if u.telegram_id else "—"
        lines.append(f"• {u.full_name} — <b>{u.role}</b> ({tg})")

    await message.answer("\n".join(lines))


@router.message(F.text == "🔑 Коды доступа", ADMIN)
async def btn_codes(message: Message) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(AccessCode).where(AccessCode.is_active == True)
        )
        codes = result.scalars().all()

    if not codes:
        await message.answer(
            "Активных кодов нет.\n\n"
            "Создать:\n"
            "<code>/newcode dekan DEK-2026</code>\n"
            "<code>/newcode rector REKT-001</code>"
        )
        return

    lines = ["🔑 <b>Активные коды</b>\n"]
    for c in codes:
        lines.append(f"• <code>{c.code}</code> — {c.role}")

    lines.append("\n\nСоздать новый:\n<code>/newcode dekan НОВЫЙ_КОД</code>")
    await message.answer("\n".join(lines))


@router.message(Command("newcode"), ADMIN)
async def cmd_newcode(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование:\n"
            "<code>/newcode dekan DEK-2026</code>\n"
            "<code>/newcode rector REKT-001</code>"
        )
        return

    _, role, code = parts
    role = role.lower()

    if role not in ("dekan", "rector", "admin"):
        await message.answer("Роль должна быть: dekan, rector или admin.")
        return

    async with async_session() as session:
        existing = await session.scalar(
            select(AccessCode).where(AccessCode.code == code)
        )
        if existing:
            await message.answer(f"Код <code>{code}</code> уже существует.")
            return

        new_code = AccessCode(code=code, role=role, is_active=True)
        session.add(new_code)
        await session.commit()

    await message.answer(
        f"✅ Код создан:\n\n" f"Роль: <b>{role}</b>\n" f"Код: <code>{code}</code>"
    )


@router.message(F.text == "⚙️ Настройки", ADMIN)
async def btn_settings(message: Message) -> None:
    await message.answer(
        "⚙️ Настройки пока в разработке.\n\n"
        f"Твой Telegram ID: <code>{message.from_user.id}</code>"
    )
