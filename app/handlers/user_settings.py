from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select, func

from app.db.session import async_session
from app.db.models import (
    User,
    Student,
    Teacher,
    Schedule,
    Substitution,
    CertificateRequest,
)
from app.services.notifications import get_or_create_settings

router = Router()


# ============ ⚙️ НАСТРОЙКИ — ВХОД ============


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(message: Message) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

    if not user:
        await message.answer("❌ Ты не зарегистрирован.")
        return

    role = user.role

    if role == "student":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Моя статистика", callback_data="my_stats_student"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профиль", callback_data="my_profile_student"
                    )
                ],
            ]
        )
    elif role == "teacher":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Моя статистика", callback_data="my_stats_teacher"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профиль", callback_data="my_profile_teacher"
                    )
                ],
            ]
        )
    elif role == "dekan":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Моя статистика", callback_data="my_stats_dekan"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профиль", callback_data="my_profile_dekan"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔔 Уведомления", callback_data="dekan_notifications"
                    )
                ],
            ]
        )
    elif role == "rector":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Полная статистика", callback_data="my_stats_rector"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профиль", callback_data="my_profile_rector"
                    )
                ],
            ]
        )
    else:
        await message.answer(f"⚙️ Настройки для роли «{role}» в разработке.")
        return

    await message.answer(
        "⚙️ <b>Настройки</b>\n\nВыбери раздел:",
        reply_markup=kb,
    )


# ============ 📊 СТАТИСТИКА — СТУДЕНТ ============


@router.callback_query(F.data == "my_stats_student")
async def cb_stats_student(callback: CallbackQuery) -> None:
    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not student:
            await callback.answer("Эта функция для студентов.", show_alert=True)
            return

        sched_result = await session.execute(
            select(Schedule.id).where(Schedule.group_name == student.group_name)
        )
        schedule_ids = [row[0] for row in sched_result.all()]
        total_pairs = len(schedule_ids)

        if schedule_ids:
            result = await session.execute(
                select(Substitution).where(
                    Substitution.schedule_id.in_(schedule_ids),
                    Substitution.status.in_(["approved", "done"]),
                )
            )
            subs_count = len(result.scalars().all())
        else:
            subs_count = 0

    await callback.message.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 {student.group_name}\n"
        f"📚 Пар в неделю: <b>{total_pairs}</b>\n"
        f"🔄 Активных замен: <b>{subs_count}</b>"
    )
    await callback.answer()


# ============ 📊 СТАТИСТИКА — ПРЕПОДАВАТЕЛЬ ============


@router.callback_query(F.data == "my_stats_teacher")
async def cb_stats_teacher(callback: CallbackQuery) -> None:
    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not teacher:
            await callback.answer("Эта функция для преподавателей.", show_alert=True)
            return

        total = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.original_teacher == teacher.id
            )
        )
        pending = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.original_teacher == teacher.id,
                Substitution.status == "pending",
            )
        )
        approved = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.original_teacher == teacher.id,
                Substitution.status == "approved",
            )
        )

    await callback.message.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📥 Всего заявок: <b>{total}</b>\n"
        f"⏳ В ожидании: <b>{pending}</b>\n"
        f"✅ Подтверждено: <b>{approved}</b>"
    )
    await callback.answer()


# ============ 📊 СТАТИСТИКА — ДЕКАНАТ ============


@router.callback_query(F.data == "my_stats_dekan")
async def cb_stats_dekan(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user or user.role != "dekan":
            await callback.answer("Эта функция для деканата.", show_alert=True)
            return

        total = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.approved_by == user.id
            )
        )
        approved = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.approved_by == user.id,
                Substitution.status == "approved",
            )
        )
        pending = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "pending")
        )
        certs_pending = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "pending"
            )
        )
        certs_ready = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.processed_by == user.id,
                CertificateRequest.status == "ready",
            )
        )

    await callback.message.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 {user.full_name}\n\n"
        f"<b>Замены:</b>\n"
        f"✅ Подтверждено: <b>{approved}</b>\n"
        f"📥 Всего обработано: <b>{total}</b>\n"
        f"⏳ В ожидании: <b>{pending}</b>\n\n"
        f"<b>Справки:</b>\n"
        f"✅ Выдано: <b>{certs_ready}</b>\n"
        f"⏳ В ожидании: <b>{certs_pending}</b>"
    )
    await callback.answer()


# ============ 📊 СТАТИСТИКА — РЕКТОР ============


@router.callback_query(F.data == "my_stats_rector")
async def cb_stats_rector(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user or user.role != "rector":
            await callback.answer("Эта функция для ректора.", show_alert=True)
            return

        users_total = await session.scalar(select(func.count(User.id)))
        users_verified = await session.scalar(
            select(func.count(User.id)).where(User.telegram_id.isnot(None))
        )
        students_total = await session.scalar(select(func.count(Student.id)))
        teachers_total = await session.scalar(select(func.count(Teacher.id)))
        subs_total = await session.scalar(select(func.count(Substitution.id)))
        certs_total = await session.scalar(select(func.count(CertificateRequest.id)))

    await callback.message.answer(
        f"📊 <b>Полная статистика</b>\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"   Всего: {users_total}\n"
        f"   С Telegram: {users_verified}\n"
        f"   🎓 Студентов: {students_total}\n"
        f"   👨‍🏫 Преподавателей: {teachers_total}\n\n"
        f"<b>📈 Активность:</b>\n"
        f"   🔄 Замен всего: {subs_total}\n"
        f"   📄 Справок всего: {certs_total}"
    )
    await callback.answer()


# ============ 👤 ПРОФИЛЬ — СТУДЕНТ ============


@router.callback_query(F.data == "my_profile_student")
async def cb_profile_student(callback: CallbackQuery) -> None:
    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not student:
            await callback.answer("Эта функция для студентов.", show_alert=True)
            return

        user = await session.get(User, student.user_id)

    created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    await callback.message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ФИО: <b>{user.full_name}</b>\n"
        f"Группа: <b>{student.group_name}</b>\n"
        f"Факультет: <b>{student.faculty or '—'}</b>\n"
        f"Курс: <b>{student.course or '—'}</b>\n"
        f"Номер билета: <code>{student.student_card}</code>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {created}"
    )
    await callback.answer()


# ============ 👤 ПРОФИЛЬ — ПРЕПОДАВАТЕЛЬ ============


@router.callback_query(F.data == "my_profile_teacher")
async def cb_profile_teacher(callback: CallbackQuery) -> None:
    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not teacher:
            await callback.answer("Эта функция для преподавателей.", show_alert=True)
            return

        user = await session.get(User, teacher.user_id)

    created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    await callback.message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ФИО: <b>{user.full_name}</b>\n"
        f"Кафедра: <b>{teacher.department}</b>\n"
        f"Должность: <b>{teacher.position or '—'}</b>\n"
        f"Табельный номер: <code>{teacher.tab_number}</code>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {created}"
    )
    await callback.answer()


# ============ 👤 ПРОФИЛЬ — ДЕКАНАТ ============


@router.callback_query(F.data == "my_profile_dekan")
async def cb_profile_dekan(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user or user.role != "dekan":
            await callback.answer("Эта функция для деканата.", show_alert=True)
            return

    created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    await callback.message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ФИО: <b>{user.full_name}</b>\n"
        f"Роль: <b>{user.role}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {created}"
    )
    await callback.answer()


# ============ 👤 ПРОФИЛЬ — РЕКТОР ============


@router.callback_query(F.data == "my_profile_rector")
async def cb_profile_rector(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user or user.role != "rector":
            await callback.answer("Эта функция для ректора.", show_alert=True)
            return

    created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    await callback.message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ФИО: <b>{user.full_name}</b>\n"
        f"Роль: <b>{user.role}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {created}"
    )
    await callback.answer()


# ============ 🔔 УВЕДОМЛЕНИЯ — ДЕКАНАТ ============


@router.callback_query(F.data == "dekan_notifications")
async def cb_notifications(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user:
            await callback.answer("Ты не зарегистрирован.", show_alert=True)
            return

        settings = await get_or_create_settings(session, user.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if settings.notifications_enabled else '❌'} Все уведомления",
                    callback_data="toggle_notif_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if settings.notify_new_certs else '❌'} Новые справки",
                    callback_data="toggle_notif_certs",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if settings.notify_new_substitutions else '❌'} Новые замены",
                    callback_data="toggle_notif_subs",
                )
            ],
        ]
    )

    status = (
        "🔔 <b>Уведомления включены</b>"
        if settings.notifications_enabled
        else "🔕 <b>Уведомления отключены</b>"
    )

    await callback.message.answer(
        f"{status}\n\nНастрой, какие уведомления получать:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_notif_"))
async def cb_toggle_notification(callback: CallbackQuery) -> None:
    field_map = {
        "toggle_notif_enabled": "notifications_enabled",
        "toggle_notif_certs": "notify_new_certs",
        "toggle_notif_subs": "notify_new_substitutions",
    }

    field = field_map.get(callback.data)
    if not field:
        await callback.answer("Неизвестная команда.")
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        if not user:
            await callback.answer("Ты не зарегистрирован.", show_alert=True)
            return

        settings = await get_or_create_settings(session, user.id)
        setattr(settings, field, not getattr(settings, field))
        await session.commit()

    await cb_notifications(callback)
