from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨‍🏫 Преподаватель")],
            [KeyboardButton(text="🎓 Студент")],
            [KeyboardButton(text="🏛 Деканат")],
            [KeyboardButton(text="🎯 Ректор")],
        ],
        resize_keyboard=True,
        # one_time_keyboard=True убрали — меню будет всегда внизу
    )
    return kb


def student_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="🔄 Замены")],
            [KeyboardButton(text="📄 Заказать справку")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )
    return kb


def teacher_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Мои пары"), KeyboardButton(text="🚫 Я не смогу")],
            [KeyboardButton(text="🔄 Найти замену")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )
    return kb


def dekan_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Заявки на замену")],
            [KeyboardButton(text="✅ Подтвердить замены")],
            [KeyboardButton(text="📊 Журнал замен")],
            [KeyboardButton(text="📄 Справки студентов")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )
    return kb


def rector_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Пульс дня")],
            [KeyboardButton(text="🚨 Тревожные сигналы")],
            [KeyboardButton(text="🤖 Ассистент")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )
    return kb


def cancel_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )
    return kb


def admin_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="🔑 Коды доступа")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )
    return kb
