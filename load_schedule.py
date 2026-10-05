import asyncio
import openpyxl

from sqlalchemy import select

from app.db.session import async_session
from app.db.models import Teacher, Schedule


async def load_schedule(path: str = "schedule.xlsx"):
    """Загрузить расписание из XLSX в БД."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    async with async_session() as session:
        count = 0
        errors = 0
        skipped = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            try:
                tab_number, subject, group_name, room, day, pair = row[:6]

                # Ищем преподавателя по табельному
                tab_str = str(tab_number).strip().zfill(4)  # 0001
                teacher = await session.scalar(
                    select(Teacher).where(Teacher.tab_number == tab_str)
                )

                if not teacher:
                    skipped += 1
                    if skipped <= 5:
                        print(f"⚠️ Преподаватель {tab_str} не найден — пропуск")
                    continue

                # Создаём Schedule
                sched = Schedule(
                    teacher_id=teacher.id,
                    subject=str(subject).strip(),
                    group_name=str(group_name).strip(),
                    room=str(room).strip(),
                    day_of_week=int(day),
                    pair_number=int(pair),
                    week_type="both",
                )
                session.add(sched)
                count += 1

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
    if skipped:
        print(f"⚠️ Пропущено (преподаватель не найден): {skipped}")
    if errors:
        print(f"❌ Ошибок: {errors}")


if __name__ == "__main__":
    asyncio.run(load_schedule())
