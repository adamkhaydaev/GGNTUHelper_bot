import asyncio
import openpyxl

from app.db.session import async_session
from app.db.models import User, Student


async def load_students(path: str = "students.xlsx"):
    """Загрузить студентов из XLSX в БД."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    async with async_session() as session:
        count = 0
        errors = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            try:
                full_name, card, group, faculty, course, budget = row[:6]

                # Создаём User
                user = User(
                    full_name=str(full_name).strip(),
                    role="student",
                    is_verified=False,
                )
                session.add(user)
                await session.flush()

                # Создаём Student
                student = Student(
                    user_id=user.id,
                    student_card=str(card).strip(),
                    group_name=str(group).strip(),
                    faculty=str(faculty).strip(),
                    course=int(course),
                    budget=bool(budget),
                )
                session.add(student)

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

        # Финальный коммит
        await session.commit()

    print(f"\n🎉 Итого загружено: {count}")
    if errors:
        print(f"⚠️ Ошибок: {errors}")


if __name__ == "__main__":
    asyncio.run(load_students())
