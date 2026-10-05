from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import select

from app.db.session import async_session
from app.db.models import User, Student, Teacher, AccessCode
from app.keyboards.menus import (
    student_menu,
    teacher_menu,
    dekan_menu,
    rector_menu,
    main_menu,
)
from app.texts import messages as msg

router = Router()


# =========================================================
# СОСТОЯНИЯ РЕГИСТРАЦИИ
# =========================================================


class RegState(StatesGroup):
    waiting_student_card = State()
    waiting_tab_number = State()
    waiting_access_code = State()


# =========================================================
# РЕГИСТРАЦИЯ ДЕКАНАТА
# =========================================================


@router.message(F.text == "🏛 Деканат")
async def dekan_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_access_code)
    await state.update_data(role="dekan")

    await message.answer(msg.ASK_ACCESS_CODE)


# =========================================================
# РЕГИСТРАЦИЯ РЕКТОРА
# =========================================================


@router.message(F.text == "🎯 Ректор")
async def rector_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_access_code)
    await state.update_data(role="rector")

    await message.answer(msg.ASK_ACCESS_CODE)


# =========================================================
# ПРОВЕРКА КОДА ДОСТУПА
# =========================================================


@router.message(RegState.waiting_access_code)
async def check_access_code(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    role = data.get("role")

    code = (message.text or "").strip()

    if not code:
        await message.answer("❌ Введи код доступа текстом.")
        return

    if role not in ("dekan", "rector"):
        await message.answer("❌ Ошибка регистрации. Начни заново через /start.")
        await state.clear()
        return

    async with async_session() as session:
        # Блокируем строку кода на время проверки,
        # чтобы один код нельзя было одновременно использовать дважды.
        access = await session.scalar(
            select(AccessCode)
            .where(
                AccessCode.code == code,
                AccessCode.role == role,
                AccessCode.is_active.is_(True),
            )
            .with_for_update()
        )

        if not access:
            await message.answer(msg.ACCESS_CODE_INVALID)
            return

        # Проверяем срок действия кода
        if access.expires_at and access.expires_at < datetime.utcnow():
            access.is_active = False
            await session.commit()

            await message.answer(
                "❌ Срок действия этого кода истёк.\n"
                "Обратись к администратору за новым кодом."
            )
            return

        # Проверяем, не зарегистрирован ли уже этот Telegram
        existing_user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if existing_user:
            await message.answer(
                "❌ Этот Telegram уже зарегистрирован в системе.\n\n"
                f"Текущая роль: {existing_user.role}"
            )
            await state.clear()
            return

        # Создаём пользователя
        user = User(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            role=role,
            is_verified=True,
        )

        session.add(user)

        # Код становится одноразовым
        access.is_active = False

        await session.commit()
        await session.refresh(user)

    await state.clear()

    if role == "dekan":
        await message.answer(
            msg.DEKAN_WELCOME.format(
                full_name=user.full_name,
            ),
            reply_markup=dekan_menu(),
        )

    elif role == "rector":
        await message.answer(
            msg.RECTOR_WELCOME.format(
                full_name=user.full_name,
            ),
            reply_markup=rector_menu(),
        )


# =========================================================
# РЕГИСТРАЦИЯ СТУДЕНТА
# =========================================================


@router.message(F.text == "🎓 Студент")
async def student_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_student_card)

    await message.answer(msg.ASK_STUDENT_CARD)


@router.message(RegState.waiting_student_card)
async def check_student_card(
    message: Message,
    state: FSMContext,
) -> None:
    card = (message.text or "").strip()

    if not card:
        await message.answer("❌ Введи номер студенческого билета текстом.")
        return

    async with async_session() as session:
        student = await session.scalar(
            select(Student).where(Student.student_card == card)
        )

        if not student:
            await message.answer(msg.STUDENT_NOT_FOUND)
            return

        # Получаем связанную запись пользователя
        user = await session.scalar(
            select(User).where(User.id == student.user_id).with_for_update()
        )

        if not user:
            await message.answer(
                "❌ Ошибка данных студента.\n" "Обратись к администратору."
            )
            return

        # Если студенческий уже привязан к другому Telegram
        if user.telegram_id is not None and user.telegram_id != message.from_user.id:
            await message.answer(
                "❌ Этот студенческий билет уже привязан "
                "к другому Telegram-аккаунту."
            )
            return

        # Проверяем, не принадлежит ли этот Telegram
        # какому-то другому пользователю
        existing_user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if existing_user and existing_user.id != user.id:
            await message.answer("❌ Этот Telegram уже привязан " "к другому аккаунту.")
            await state.clear()
            return

        # Привязываем Telegram
        user.telegram_id = message.from_user.id
        user.is_verified = True

        await session.commit()

        full_name = user.full_name
        group_name = student.group_name

    await state.clear()

    await message.answer(
        msg.STUDENT_WELCOME.format(
            full_name=full_name,
            group=group_name,
        ),
        reply_markup=student_menu(),
    )


# =========================================================
# РЕГИСТРАЦИЯ ПРЕПОДАВАТЕЛЯ
# =========================================================


@router.message(F.text == "👨‍🏫 Преподаватель")
async def teacher_start(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(RegState.waiting_tab_number)

    await message.answer(msg.ASK_TAB_NUMBER)


@router.message(RegState.waiting_tab_number)
async def check_tab_number(
    message: Message,
    state: FSMContext,
) -> None:
    tab = (message.text or "").strip()

    if not tab:
        await message.answer("❌ Введи табельный номер текстом.")
        return

    async with async_session() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.tab_number == tab))

        if not teacher:
            await message.answer(msg.TEACHER_NOT_FOUND)
            return

        # Получаем пользователя преподавателя
        user = await session.scalar(
            select(User).where(User.id == teacher.user_id).with_for_update()
        )

        if not user:
            await message.answer(
                "❌ Ошибка данных преподавателя.\n" "Обратись к администратору."
            )
            return

        # Если табельный номер уже привязан
        # к другому Telegram
        if user.telegram_id is not None and user.telegram_id != message.from_user.id:
            await message.answer(
                "❌ Этот табельный номер уже привязан " "к другому Telegram-аккаунту."
            )
            return

        # Проверяем, не занят ли Telegram
        # другим пользователем
        existing_user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )

        if existing_user and existing_user.id != user.id:
            await message.answer("❌ Этот Telegram уже привязан " "к другому аккаунту.")
            await state.clear()
            return

        # Привязываем Telegram
        user.telegram_id = message.from_user.id
        user.is_verified = True

        await session.commit()

        full_name = user.full_name
        department = teacher.department

    await state.clear()

    await message.answer(
        msg.TEACHER_WELCOME.format(
            full_name=full_name,
            department=department,
        ),
        reply_markup=teacher_menu(),
    )


# =========================================================
# ОТМЕНА РЕГИСТРАЦИИ
# =========================================================


@router.message(F.text == "❌ Отмена")
async def cancel(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        msg.CANCELLED,
        reply_markup=main_menu(),
    )
