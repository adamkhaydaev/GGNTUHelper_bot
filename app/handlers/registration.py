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


# Состояния регистрации
class RegState(StatesGroup):
    waiting_student_card = State()
    waiting_tab_number = State()
    waiting_access_code = State()


# ============ РЕГИСТРАЦИЯ ДЕКАНАТА ============


@router.message(F.text == "🏛 Деканат")
async def dekan_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_access_code)
    await state.update_data(role="dekan")
    await message.answer(msg.ASK_ACCESS_CODE)


# ============ РЕГИСТРАЦИЯ РЕКТОРА ============


@router.message(F.text == "🎯 Ректор")
async def rector_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_access_code)
    await state.update_data(role="rector")
    await message.answer(msg.ASK_ACCESS_CODE)


# ============ ПРОВЕРКА КОДА ============


@router.message(RegState.waiting_access_code)
async def check_access_code(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    role = data.get("role")  # dekan или rector
    code = message.text.strip()

    async with async_session() as session:
        # Ищем активный код с нужной ролью
        result = await session.execute(
            select(AccessCode).where(
                AccessCode.code == code,
                AccessCode.role == role,
                AccessCode.is_active == True,
            )
        )
        access = result.scalar_one_or_none()

        if not access:
            await message.answer(msg.ACCESS_CODE_INVALID)
            return

        # Создаём пользователя
        user = User(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            role=role,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await state.clear()

    if role == "dekan":
        await message.answer(
            msg.DEKAN_WELCOME.format(full_name=user.full_name),
            reply_markup=dekan_menu(),
        )
    elif role == "rector":
        await message.answer(
            msg.RECTOR_WELCOME.format(full_name=user.full_name),
            reply_markup=rector_menu(),
        )


# ============ РЕГИСТРАЦИЯ СТУДЕНТА ============


@router.message(F.text == "🎓 Студент")
async def student_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_student_card)
    await message.answer(msg.ASK_STUDENT_CARD)


@router.message(RegState.waiting_student_card)
async def check_student_card(message: Message, state: FSMContext) -> None:
    card = message.text.strip()

    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.student_card == card)
        )
        student = result.scalar_one_or_none()

        if not student:
            await message.answer(msg.STUDENT_NOT_FOUND)
            return

        # Обновляем пользователя
        user = await session.get(User, student.user_id)
        user.telegram_id = message.from_user.id
        user.is_verified = True
        await session.commit()

    await state.clear()

    await message.answer(
        msg.STUDENT_WELCOME.format(
            full_name=user.full_name,
            group=student.group_name,
        ),
        reply_markup=student_menu(),
    )


# ============ РЕГИСТРАЦИЯ ПРЕПОДАВАТЕЛЯ ============


@router.message(F.text == "👨‍🏫 Преподаватель")
async def teacher_start(message: Message, state: FSMContext) -> None:
    await state.set_state(RegState.waiting_tab_number)
    await message.answer(msg.ASK_TAB_NUMBER)


@router.message(RegState.waiting_tab_number)
async def check_tab_number(message: Message, state: FSMContext) -> None:
    tab = message.text.strip()

    async with async_session() as session:
        result = await session.execute(select(Teacher).where(Teacher.tab_number == tab))
        teacher = result.scalar_one_or_none()

        if not teacher:
            await message.answer(msg.TEACHER_NOT_FOUND)
            return

        # Обновляем пользователя
        user = await session.get(User, teacher.user_id)
        user.telegram_id = message.from_user.id
        user.is_verified = True
        await session.commit()

    await state.clear()

    await message.answer(
        msg.TEACHER_WELCOME.format(
            full_name=user.full_name,
            department=teacher.department,
        ),
        reply_markup=teacher_menu(),
    )


# ============ ОТМЕНА ============


@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(msg.CANCELLED, reply_markup=main_menu())
