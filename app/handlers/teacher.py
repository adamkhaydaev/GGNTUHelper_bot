from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from app.db.session import async_session
from app.db.models import User, Teacher, Schedule, Substitution

router = Router()


class TeacherState(StatesGroup):
    waiting_reason = State()


# ============ 📅 МОИ ПАРЫ ============


@router.message(F.text == "📅 Мои пары")
async def btn_lessons(message: Message) -> None:
    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not teacher:
            await message.answer("❌ Ты не найден как преподаватель.")
            return

        result = await session.execute(
            select(Schedule)
            .where(Schedule.teacher_id == teacher.id)
            .order_by(Schedule.day_of_week, Schedule.pair_number)
        )
        pairs = result.scalars().all()

    if not pairs:
        await message.answer("📅 <b>У тебя нет пар в расписании.</b>")
        return

    days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    lines = [f"📅 <b>Мои пары</b>\n"]

    for p in pairs:
        lines.append(
            f"• <b>{days[p.day_of_week]}</b>, {p.pair_number}-я пара — "
            f"{p.subject}\n"
            f"   Группа {p.group_name}, ауд. {p.room}"
        )

    await message.answer("\n".join(lines))


# ============ 🚫 Я НЕ СМОГУ ============


@router.message(F.text == "🚫 Я не смогу")
async def btn_cant(message: Message) -> None:
    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not teacher:
            await message.answer("❌ Ты не найден как преподаватель.")
            return

        result = await session.execute(
            select(Schedule)
            .where(Schedule.teacher_id == teacher.id)
            .order_by(Schedule.day_of_week, Schedule.pair_number)
        )
        pairs = result.scalars().all()

    if not pairs:
        await message.answer("📅 <b>У тебя нет пар в расписании.</b>")
        return

    days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for p in pairs:
        label = (
            f"{days[p.day_of_week]}, {p.pair_number}-я — {p.subject} ({p.group_name})"
        )
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"cant_{p.id}")]
        )

    await message.answer(
        "🚫 <b>Выбери пару, которую не сможешь провести:</b>",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("cant_"))
async def cb_choose_reason(callback: CallbackQuery, state: FSMContext) -> None:
    schedule_id = int(callback.data.split("_")[1])

    await state.update_data(schedule_id=schedule_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤒 Болезнь", callback_data="reason_Болезнь")],
            [
                InlineKeyboardButton(
                    text="✈️ Командировка", callback_data="reason_Командировка"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Личные обстоятельства",
                    callback_data="reason_Личные обстоятельства",
                )
            ],
            [InlineKeyboardButton(text="📝 Другое", callback_data="reason_Другое")],
        ]
    )

    await callback.message.answer(
        "💬 <b>Укажи причину:</b>",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reason_"))
async def cb_create_request(callback: CallbackQuery, state: FSMContext) -> None:
    reason = callback.data.split("_", 1)[1]

    data = await state.get_data()
    schedule_id = data.get("schedule_id")

    if not schedule_id:
        await callback.answer("Ошибка: потеряна пара.", show_alert=True)
        return

    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == callback.from_user.id)
        )

        if not teacher:
            await callback.answer("Ты не найден как преподаватель.", show_alert=True)
            return

        existing = await session.scalar(
            select(Substitution).where(
                Substitution.schedule_id == schedule_id,
                Substitution.original_teacher == teacher.id,
                Substitution.status == "pending",
            )
        )

        if existing:
            await callback.message.answer(
                f"⚠️ Заявка на эту пару уже создана (заявка #{existing.id})."
            )
            await state.clear()
            await callback.answer()
            return

        sub = Substitution(
            schedule_id=schedule_id,
            original_teacher=teacher.id,
            reason=reason,
            status="pending",
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

        # Уведомляем деканов
        from app.services.notifications import notify_role

        teacher_user = await session.get(User, teacher.user_id)
        sched = await session.get(Schedule, schedule_id)

        days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        notification = (
            f"🔄 <b>Новая заявка на замену</b>\n\n"
            f"👨‍🏫 {teacher_user.full_name if teacher_user else '—'}\n"
            f"📚 {sched.subject if sched else '—'}, "
            f"группа {sched.group_name if sched else '—'}\n"
            f"📅 {days[sched.day_of_week] if sched else '—'}, "
            f"{sched.pair_number if sched else '—'}-я пара\n"
            f"💬 Причина: {reason}\n\n"
            f"Заявка #{sub.id} — проверь в «📋 Заявки на замену»."
        )

        await notify_role(
            bot=callback.bot,
            session=session,
            role="dekan",
            text=notification,
            notification_type="new_substitution",
        )

    await callback.message.answer(
        f"✅ <b>Заявка #{sub.id} создана</b>\n\n"
        f"Причина: {reason}\n"
        f"Статус: ожидает подтверждения деканата."
    )
    await state.clear()
    await callback.answer()


# ============ 🔄 НАЙТИ ЗАМЕНУ ============


@router.message(F.text == "🔄 Найти замену")
async def btn_find_sub(message: Message) -> None:
    async with async_session() as session:
        teacher = await session.scalar(
            select(Teacher)
            .join(User, User.id == Teacher.user_id)
            .where(User.telegram_id == message.from_user.id)
        )

        if not teacher:
            await message.answer("❌ Ты не найден как преподаватель.")
            return

        result = await session.execute(
            select(Substitution)
            .where(Substitution.original_teacher == teacher.id)
            .order_by(Substitution.created_at.desc())
            .limit(20)
        )
        subs = result.scalars().all()

        if not subs:
            await message.answer(
                "🔄 <b>У тебя нет заявок на замену</b>\n\n"
                "Если не сможешь провести пару — нажми «🚫 Я не смогу»."
            )
            return

        days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "done": "✔️",
        }
        status_text = {
            "pending": "Ожидает деканат",
            "approved": "Подтверждена",
            "rejected": "Отклонена",
            "done": "Выполнена",
        }

        lines = [f"🔄 <b>Мои заявки на замену</b> ({len(subs)})\n"]

        for sub in subs:
            sched = await session.get(Schedule, sub.schedule_id)
            if not sched:
                continue

            emoji = status_emoji.get(sub.status, "•")
            text = status_text.get(sub.status, sub.status)

            lines.append(
                f"{emoji} <b>#{sub.id}</b> — {sched.subject}, {sched.group_name}\n"
                f"   📅 {days[sched.day_of_week]}, {sched.pair_number}-я пара\n"
                f"   💬 {sub.reason}\n"
                f"   Статус: <b>{text}</b>\n"
            )

    await message.answer("\n".join(lines))
