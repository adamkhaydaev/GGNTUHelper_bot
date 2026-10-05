from datetime import datetime

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
    Substitution,
    Schedule,
    Teacher,
    Student,
    CertificateRequest,
)

router = Router()


CERT_TYPES = {
    "obuch": "📚 Справка об обучении",
    "vyzov": "🎓 Справка-вызов",
    "stip": "💰 Справка о стипендии",
    "soc": "📄 Справка для соцзащиты",
    "med": "🏥 Справка для медцелей",
    "other": "📝 Другое",
}


# ============ 📋 ЗАЯВКИ НА ЗАМЕНУ ============


@router.message(F.text == "📋 Заявки на замену")
async def btn_requests(message: Message) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Substitution)
            .where(Substitution.status == "pending")
            .order_by(Substitution.created_at)
        )
        subs = result.scalars().all()

        if not subs:
            await message.answer(
                "📋 <b>Заявок на замену нет</b>\n\nВсе заявки обработаны."
            )
            return

        lines = [f"📋 <b>Заявки на замену</b> ({len(subs)})\n"]

        for sub in subs:
            sched = await session.get(Schedule, sub.schedule_id)
            teacher_user = await session.scalar(
                select(User)
                .join(Teacher, Teacher.user_id == User.id)
                .where(Teacher.id == sub.original_teacher)
            )

            if not sched or not teacher_user:
                continue

            days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
            lines.append(
                f"<b>#{sub.id}</b> — {teacher_user.full_name}\n"
                f"   📚 {sched.subject}, группа {sched.group_name}\n"
                f"   📅 {days[sched.day_of_week]}, {sched.pair_number}-я пара, ауд. {sched.room}\n"
                f"   💬 Причина: {sub.reason}\n"
                f"   Статус: <i>{sub.status}</i>\n"
            )

        lines.append(
            "\nЧтобы подтвердить — напиши:\n"
            "<code>/approve_ID</code>\n"
            "Например: <code>/approve_1</code>"
        )

        await message.answer("\n".join(lines))


# ============ ✅ ПОДТВЕРДИТЬ ЗАМЕНЫ ============


@router.message(F.text == "✅ Подтвердить замены")
async def btn_approve_info(message: Message) -> None:
    await message.answer(
        "✅ <b>Подтверждение замен</b>\n\n"
        "Открой «📋 Заявки на замену» и подтверди нужную командой:\n"
        "<code>/approve_ID</code>\n\n"
        "Например: <code>/approve_1</code>"
    )


@router.message(F.text.startswith("/approve_"))
async def approve_substitution(message: Message) -> None:
    try:
        sub_id = int(message.text.split("_")[1])
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат. Используй: /approve_1")
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if not user:
            await message.answer("❌ Ты не зарегистрирован в боте.")
            return

        sub = await session.get(Substitution, sub_id)

        if not sub:
            await message.answer(f"❌ Заявка #{sub_id} не найдена.")
            return

        if sub.status != "pending":
            await message.answer(
                f"❌ Заявка #{sub_id} уже обработана (статус: {sub.status})."
            )
            return

        sub.status = "approved"
        sub.approved_by = user.id
        sub.approved_at = datetime.now()

        sched = await session.get(Schedule, sub.schedule_id)
        original_teacher_user = await session.scalar(
            select(User)
            .join(Teacher, Teacher.user_id == User.id)
            .where(Teacher.id == sub.original_teacher)
        )

        students_to_notify = []
        if sched:
            student_result = await session.execute(
                select(User)
                .join(Student, Student.user_id == User.id)
                .where(Student.group_name == sched.group_name)
            )
            students_to_notify = student_result.scalars().all()

        await session.commit()

    sent = 0
    if sched:
        days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        teacher_name = original_teacher_user.full_name if original_teacher_user else "—"

        notification = (
            f"🔄 <b>Замена в расписании</b>\n\n"
            f"📅 {days[sched.day_of_week]}, {sched.pair_number}-я пара\n"
            f"📚 {sched.subject}\n"
            f"📍 Ауд. {sched.room or '—'}\n\n"
            f"👨‍🏫 Вместо: {teacher_name}\n"
            f"💬 Причина: {sub.reason}\n\n"
            f"Замена подтверждена деканатом."
        )

        for student_user in students_to_notify:
            if student_user.telegram_id:
                try:
                    await message.bot.send_message(
                        chat_id=student_user.telegram_id,
                        text=notification,
                    )
                    sent += 1
                except Exception:
                    pass

    await message.answer(
        f"✅ <b>Заявка #{sub_id} подтверждена</b>\n\n"
        f"📨 Уведомлено студентов: {sent}"
    )


# ============ 📊 ЖУРНАЛ ЗАМЕН ============


@router.message(F.text == "📊 Журнал замен")
async def btn_journal(message: Message) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Substitution)
            .where(Substitution.status.in_(["approved", "rejected", "done"]))
            .order_by(Substitution.approved_at.desc())
            .limit(30)
        )
        subs = result.scalars().all()

        if not subs:
            await message.answer(
                "📊 <b>Журнал пуст</b>\n\nОбработанных замен пока нет."
            )
            return

        lines = [f"📊 <b>Журнал замен</b> (последние 30)\n"]

        for sub in subs:
            sched = await session.get(Schedule, sub.schedule_id)
            teacher_user = await session.scalar(
                select(User)
                .join(Teacher, Teacher.user_id == User.id)
                .where(Teacher.id == sub.original_teacher)
            )

            if not sched or not teacher_user:
                continue

            days = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
            emoji = "✅" if sub.status == "approved" else "❌"

            lines.append(
                f"{emoji} <b>#{sub.id}</b> — {teacher_user.full_name}\n"
                f"   📚 {sched.subject}, {sched.group_name}\n"
                f"   📅 {days[sched.day_of_week]}, {sched.pair_number}-я пара\n"
                f"   💬 {sub.reason}\n"
                f"   Статус: <b>{sub.status}</b>\n"
            )

        await message.answer("\n".join(lines))


# ============ 📄 СПРАВКИ СТУДЕНТОВ ============


@router.message(F.text == "📄 Справки студентов")
async def btn_certificates(message: Message) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(CertificateRequest)
            .where(CertificateRequest.status == "pending")
            .order_by(CertificateRequest.created_at)
        )
        requests = result.scalars().all()

        if not requests:
            await message.answer("📄 <b>Заявок на справки нет</b>\n\nВсе обработаны.")
            return

        lines = [f"📄 <b>Заявки на справки</b> ({len(requests)})\n"]

        for r in requests:
            student = await session.get(Student, r.student_id)
            student_user = await session.get(User, student.user_id) if student else None

            if not student or not student_user:
                continue

            cert_name = CERT_TYPES.get(r.cert_type, r.cert_type)
            date = r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else "—"
            comment = f"\n   💬 {r.comment}" if r.comment else ""

            lines.append(
                f"<b>#{r.id}</b> — {student_user.full_name}\n"
                f"   📄 {cert_name}\n"
                f"   🎓 {student.group_name}{comment}\n"
                f"   📅 {date}\n"
                f"   Статус: <i>{r.status}</i>\n"
            )

        lines.append(
            "\nЧтобы обработать:\n"
            "<code>/ready_ID</code> — справка готова\n"
            "<code>/reject_cert_ID</code> — отказано\n"
            "Например: <code>/ready_1</code>"
        )

        await message.answer("\n".join(lines))


@router.message(F.text.startswith("/ready_"))
async def ready_certificate(message: Message) -> None:
    try:
        cert_id = int(message.text.split("_")[1])
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат. Используй: /ready_1")
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if not user:
            await message.answer("❌ Ты не зарегистрирован в боте.")
            return

        req = await session.get(CertificateRequest, cert_id)

        if not req:
            await message.answer(f"❌ Заявка #{cert_id} не найдена.")
            return

        if req.status != "pending":
            await message.answer(
                f"❌ Заявка #{cert_id} уже обработана (статус: {req.status})."
            )
            return

        req.status = "ready"
        req.processed_by = user.id
        req.processed_at = datetime.now()

        student = await session.get(Student, req.student_id)
        student_user = await session.get(User, student.user_id) if student else None

        await session.commit()

    if student_user and student_user.telegram_id:
        cert_name = CERT_TYPES.get(req.cert_type, req.cert_type)
        try:
            await message.bot.send_message(
                chat_id=student_user.telegram_id,
                text=(
                    f"✅ <b>Ваша справка готова!</b>\n\n"
                    f"📄 Тип: {cert_name}\n"
                    f"💬 Комментарий: {req.comment or '—'}\n\n"
                    f"Заберите в деканате."
                ),
            )
        except Exception:
            pass

    await message.answer(
        f"✅ <b>Заявка #{cert_id} — справка готова</b>\n\n"
        f"Студент: {student_user.full_name if student_user else '—'}\n"
        f"📨 Уведомление отправлено."
    )


@router.message(F.text.startswith("/reject_cert_"))
async def reject_certificate(message: Message) -> None:
    try:
        cert_id = int(message.text.split("_")[2])
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат. Используй: /reject_cert_1")
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if not user:
            await message.answer("❌ Ты не зарегистрирован в боте.")
            return

        req = await session.get(CertificateRequest, cert_id)

        if not req:
            await message.answer(f"❌ Заявка #{cert_id} не найдена.")
            return

        if req.status != "pending":
            await message.answer(
                f"❌ Заявка #{cert_id} уже обработана (статус: {req.status})."
            )
            return

        req.status = "rejected"
        req.processed_by = user.id
        req.processed_at = datetime.now()

        student = await session.get(Student, req.student_id)
        student_user = await session.get(User, student.user_id) if student else None

        await session.commit()

    if student_user and student_user.telegram_id:
        cert_name = CERT_TYPES.get(req.cert_type, req.cert_type)
        try:
            await message.bot.send_message(
                chat_id=student_user.telegram_id,
                text=(
                    f"❌ <b>Заявка на справку отклонена</b>\n\n"
                    f"📄 Тип: {cert_name}\n\n"
                    f"Обратитесь в деканат за разъяснениями."
                ),
            )
        except Exception:
            pass

    await message.answer(
        f"❌ <b>Заявка #{cert_id} — отказано</b>\n\n📨 Уведомление отправлено."
    )
