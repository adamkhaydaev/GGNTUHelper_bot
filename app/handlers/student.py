from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from app.db.session import async_session
from app.db.models import (
    User,
    Student,
    Teacher,
    Schedule,
    Substitution,
    CertificateRequest,
)

router = Router()


# Типы справок
CERT_TYPES = {
    "obuch": "📚 Справка об обучении",
    "vyzov": "🎓 Справка-вызов",
    "stip": "💰 Справка о стипендии",
    "soc": "📄 Справка для соцзащиты",
    "med": "🏥 Справка для медцелей",
    "other": "📝 Другое",
}


class CertState(StatesGroup):
    waiting_comment = State()


# ============ 📅 РАСПИСАНИЕ ============


@router.message(F.text == "📅 Расписание")
async def btn_schedule(message: Message) -> None:
    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not student:
            await message.answer("❌ Ты не найден как студент.")
            return

        result = await session.execute(
            select(Schedule)
            .where(Schedule.group_name == student.group_name)
            .order_by(Schedule.day_of_week, Schedule.pair_number)
        )
        pairs = result.scalars().all()

        if not pairs:
            await message.answer(
                f"📅 <b>Расписание для группы {student.group_name}</b>\n\n"
                "Пока нет пар."
            )
            return

        days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        lines = [f"📅 <b>Расписание — {student.group_name}</b>\n"]

        for p in pairs:
            teacher = await session.get(Teacher, p.teacher_id)
            teacher_user = await session.get(User, teacher.user_id) if teacher else None
            teacher_name = teacher_user.full_name if teacher_user else "—"

            lines.append(
                f"• <b>{days[p.day_of_week]}</b>, {p.pair_number}-я пара — "
                f"{p.subject}\n"
                f"   👨‍🏫 {teacher_name}\n"
                f"   📍 Ауд. {p.room or '—'}"
            )

    await message.answer("\n".join(lines))


# ============ 🔄 ЗАМЕНЫ ============


@router.message(F.text == "🔄 Замены")
async def btn_substitutions(message: Message) -> None:
    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not student:
            await message.answer("❌ Ты не найден как студент.")
            return

        sched_result = await session.execute(
            select(Schedule.id).where(Schedule.group_name == student.group_name)
        )
        schedule_ids = [row[0] for row in sched_result.all()]

        if not schedule_ids:
            await message.answer("🔄 <b>Замен для твоей группы нет.</b>")
            return

        result = await session.execute(
            select(Substitution)
            .where(
                Substitution.schedule_id.in_(schedule_ids),
                Substitution.status.in_(["approved", "done"]),
            )
            .order_by(Substitution.created_at.desc())
        )
        subs = result.scalars().all()

        if not subs:
            await message.answer("🔄 <b>Активных замен для твоей группы нет.</b>")
            return

        days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        lines = [f"🔄 <b>Замены для группы {student.group_name}</b>\n"]

        for sub in subs:
            sched = await session.get(Schedule, sub.schedule_id)
            teacher = await session.get(Teacher, sub.original_teacher)
            teacher_user = await session.get(User, teacher.user_id) if teacher else None

            if not sched:
                continue

            teacher_name = teacher_user.full_name if teacher_user else "—"

            lines.append(
                f"• <b>{days[sched.day_of_week]}</b>, {sched.pair_number}-я пара — "
                f"{sched.subject}\n"
                f"   🔁 Замена: вместо {teacher_name}\n"
                f"   💬 Причина: {sub.reason}\n"
                f"   📍 Ауд. {sched.room or '—'}"
            )

    await message.answer("\n".join(lines))


# ============ 📄 ЗАКАЗАТЬ СПРАВКУ ============


@router.message(F.text == "📄 Заказать справку")
async def btn_request(message: Message) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"cert_{code}")]
            for code, name in CERT_TYPES.items()
        ]
        + [[InlineKeyboardButton(text="📋 Мои справки", callback_data="cert_my_list")]]
    )

    await message.answer(
        "📄 <b>Заказ справки</b>\n\nВыбери тип справки:",
        reply_markup=kb,
    )


@router.callback_query(F.data == "cert_my_list")
async def cb_cert_my_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not student:
            await callback.answer("Ты не найден как студент.", show_alert=True)
            return

        result = await session.execute(
            select(CertificateRequest)
            .where(CertificateRequest.student_id == student.id)
            .order_by(CertificateRequest.created_at.desc())
            .limit(20)
        )
        requests = result.scalars().all()

    if not requests:
        await callback.message.answer("📋 <b>У тебя нет заявок на справки.</b>")
        await callback.answer()
        return

    status_emoji = {"pending": "⏳", "ready": "✅", "rejected": "❌"}
    status_text = {"pending": "В обработке", "ready": "Готова", "rejected": "Отказано"}

    lines = ["📋 <b>Мои заявки на справки</b>\n"]
    for r in requests:
        emoji = status_emoji.get(r.status, "•")
        text = status_text.get(r.status, r.status)
        cert_name = CERT_TYPES.get(r.cert_type, r.cert_type)
        date = r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else "—"

        lines.append(
            f"{emoji} <b>#{r.id}</b> — {cert_name}\n"
            f"   📅 {date}\n"
            f"   Статус: <b>{text}</b>\n"
        )

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith("cert_") & ~F.data.in_(["cert_my_list"]))
async def cb_cert_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    cert_code = callback.data.split("_", 1)[1]

    if cert_code not in CERT_TYPES:
        await callback.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(cert_type=cert_code)
    await state.set_state(CertState.waiting_comment)

    await callback.message.answer(
        f"📄 Тип: <b>{CERT_TYPES[cert_code]}</b>\n\n"
        "Напиши <b>комментарий</b> (или «-», если не нужно):\n"
        "Например: «для военкомата» или «для банка»."
    )
    await callback.answer()


@router.message(CertState.waiting_comment)
async def cb_cert_comment(message: Message, state: FSMContext) -> None:
    comment = message.text.strip()
    if comment == "-":
        comment = None

    data = await state.get_data()
    cert_type = data.get("cert_type")

    if not cert_type:
        await message.answer("❌ Ошибка: тип потерян. Начни заново.")
        await state.clear()
        return

    async with async_session() as session:
        student = await session.scalar(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not student:
            await message.answer("❌ Ты не найден как студент.")
            await state.clear()
            return

        student_user = await session.get(User, student.user_id)

        req = CertificateRequest(
            student_id=student.id,
            cert_type=cert_type,
            comment=comment,
            status="pending",
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)

        # Уведомляем деканов
        from app.services.notifications import notify_role

        cert_name = CERT_TYPES[cert_type]
        notification = (
            f"📄 <b>Новая заявка на справку</b>\n\n"
            f"👤 {student_user.full_name if student_user else '—'} "
            f"({student.group_name})\n"
            f"📄 {cert_name}\n"
            f"💬 {comment or '—'}\n\n"
            f"Заявка #{req.id} — проверь в «📄 Справки студентов»."
        )

        await notify_role(
            bot=message.bot,
            session=session,
            role="dekan",
            text=notification,
            notification_type="new_cert",
        )

    await message.answer(
        f"✅ <b>Заявка #{req.id} создана</b>\n\n"
        f"Тип: {CERT_TYPES[cert_type]}\n"
        f"Статус: ожидает обработки деканатом.\n\n"
        f"Проверить статус: 📄 Заказать справку → 📋 Мои справки."
    )
    await state.clear()
