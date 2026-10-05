import asyncio
import openpyxl

from app.db.session import async_session
from app.db.models import User, Teacher


async def load_teachers(path: str = "teachers.xlsx"):
    """Загрузить преподавателей из XLSX в БД."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    async with async_session() as session:
        count = 0
        errors = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            try:
                full_name, tab_number, department, position, max_hours = row[:5]

                # Создаём User
                user = User(
                    full_name=str(full_name).strip(),
                    role="teacher",
                    is_verified=False,
                )
                session.add(user)
                await session.flush()

                # Создаём Teacher
                teacher = Teacher(
                    user_id=user.id,
                    tab_number=str(tab_number).strip(),
                    department=str(department).strip(),
                    position=str(position).strip(),
                    max_hours_week=int(max_hours),
                )
                session.add(teacher)

                count += 1

                # Коммитим пачками по 100
                if count % 100 == 0:
                    await session.commit()
                    print(f"✅ Загружено: {count}")

            except Exception as e:
                errors += 1
                print(f"❌ Ошибка в строке {count + errors}: {e}")
                await session.rollback()
                continue

        await session.commit()

    print(f"\n🎉 Итого загружено: {count}")
    if errors:
        print(f"⚠️ Ошибок: {errors}")


if __name__ == "__main__":
    asyncio.run(load_teachers())
