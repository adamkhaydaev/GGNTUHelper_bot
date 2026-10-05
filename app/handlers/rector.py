from datetime import datetime, timedelta

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

router = Router()


# ============ 📊 ПУЛЬС ДНЯ ============


@router.message(F.text == "📊 Пульс дня")
async def btn_pulse(message: Message) -> None:
    async with async_session() as session:
        # Пользователи
        users_total = await session.scalar(select(func.count(User.id)))
        students_total = await session.scalar(select(func.count(Student.id)))
        teachers_total = await session.scalar(select(func.count(Teacher.id)))

        # Расписание
        schedule_total = await session.scalar(select(func.count(Schedule.id)))

        # Замены
        subs_pending = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "pending")
        )
        subs_approved = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "approved")
        )

        # Справки
        certs_pending = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "pending"
            )
        )
        certs_ready = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "ready"
            )
        )

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    await message.answer(
        f"📊 <b>Пульс дня</b> — {now}\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"   Всего: {users_total}\n"
        f"   🎓 Студентов: {students_total}\n"
        f"   👨‍🏫 Преподавателей: {teachers_total}\n\n"
        f"<b>📚 Учебный процесс:</b>\n"
        f"   Пар в расписании: {schedule_total}\n\n"
        f"<b>🔄 Замены:</b>\n"
        f"   ⏳ В ожидании: {subs_pending}\n"
        f"   ✅ Подтверждено: {subs_approved}\n\n"
        f"<b>📄 Справки:</b>\n"
        f"   ⏳ В ожидании: {certs_pending}\n"
        f"   ✅ Готово: {certs_ready}"
    )


# ============ 🚨 ТРЕВОЖНЫЕ СИГНАЛЫ ============


@router.message(F.text == "🚨 Тревожные сигналы")
async def btn_alerts(message: Message) -> None:
    async with async_session() as session:
        alerts = []

        # 1. Много pending-заявок на замену
        subs_pending = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "pending")
        )
        if subs_pending and subs_pending >= 3:
            alerts.append(
                f"⚠️ <b>Замен в ожидании:</b> {subs_pending}\n"
                f"   Деканат не обрабатывает заявки."
            )

        # 2. Много pending-справок
        certs_pending = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "pending"
            )
        )
        if certs_pending and certs_pending >= 3:
            alerts.append(
                f"⚠️ <b>Справок в ожидании:</b> {certs_pending}\n"
                f"   Деканат не выдаёт справки."
            )

        # 3. «Зависшие» заявки на замену (pending больше 3 дней)
        three_days_ago = datetime.now() - timedelta(days=3)
        old_subs = await session.scalar(
            select(func.count(Substitution.id)).where(
                Substitution.status == "pending",
                Substitution.created_at < three_days_ago,
            )
        )
        if old_subs and old_subs > 0:
            alerts.append(
                f"🚨 <b>Зависшие заявки на замену:</b> {old_subs}\n"
                f"   Висят больше 3 дней без обработки."
            )

        # 4. «Зависшие» справки
        old_certs = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "pending",
                CertificateRequest.created_at < three_days_ago,
            )
        )
        if old_certs and old_certs > 0:
            alerts.append(
                f"🚨 <b>Зависшие справки:</b> {old_certs}\n" f"   Висят больше 3 дней."
            )

        # 5. Нет расписания
        schedule_total = await session.scalar(select(func.count(Schedule.id)))
        if not schedule_total:
            alerts.append("⚠️ <b>Нет расписания</b> — пары не добавлены.")

    if not alerts:
        await message.answer(
            "🚨 <b>Тревожных сигналов нет</b>\n\n" "Все процессы работают нормально."
        )
        return

    lines = ["🚨 <b>Тревожные сигналы</b>\n"]
    for i, alert in enumerate(alerts, 1):
        lines.append(f"{i}. {alert}\n")

    await message.answer("\n".join(lines))


# ============ 🤖 АССИСТЕНТ ============


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command


class RectorState(StatesGroup):
    waiting_question = State()


@router.message(F.text == "🤖 Ассистент")
async def btn_assistant(message: Message, state: FSMContext) -> None:
    await state.set_state(RectorState.waiting_question)
    await message.answer(
        "🤖 <b>Ассистент ректора</b>\n\n"
        "Задай вопрос — я отвечу.\n\n"
        "Например:\n"
        "• «Сколько замен за неделю?»\n"
        "• «Сгенерируй тезисы для выступления»\n"
        "• «Какие проблемы в расписании?»\n\n"
        "Выйти — /cancel"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вышел из режима ассистента.")


@router.message(RectorState.waiting_question)
async def handle_question(message: Message, state: FSMContext) -> None:
    question = message.text.strip()

    await message.bot.send_chat_action(
        chat_id=message.chat.id,
        action="typing",
    )

    # ← Собираем свежие данные из БД
    context = await _build_context()

    from app.services.llm import ask_llm

    try:
        answer = await ask_llm(question, context=context)
        await message.answer(
            f"🤖 <b>Ассистент:</b>\n\n{answer}\n\n"
            f"<i>Задай следующий вопрос или /cancel.</i>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


async def _build_context() -> str:
    """Собрать актуальную статистику для LLM."""
    async with async_session() as session:
        users_total = await session.scalar(select(func.count(User.id)))
        students_total = await session.scalar(select(func.count(Student.id)))
        teachers_total = await session.scalar(select(func.count(Teacher.id)))

        schedule_total = await session.scalar(select(func.count(Schedule.id)))

        subs_pending = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "pending")
        )
        subs_approved = await session.scalar(
            select(func.count(Substitution.id)).where(Substitution.status == "approved")
        )

        certs_pending = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "pending"
            )
        )
        certs_ready = await session.scalar(
            select(func.count(CertificateRequest.id)).where(
                CertificateRequest.status == "ready"
            )
        )

    return (
        f"👥 Всего пользователей: {users_total}\n"
        f"🎓 Студентов: {students_total}\n"
        f"👨‍🏫 Преподавателей: {teachers_total}\n\n"
        f"📚 Пар в расписании: {schedule_total}\n\n"
        f"🔄 Замены:\n"
        f"   ⏳ В ожидании: {subs_pending}\n"
        f"   ✅ Подтверждено: {subs_approved}\n\n"
        f"📄 Справки:\n"
        f"   ⏳ В ожидании: {certs_pending}\n"
        f"   ✅ Готово: {certs_ready}"
    )
