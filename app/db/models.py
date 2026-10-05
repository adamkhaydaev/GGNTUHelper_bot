from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('student','teacher','dekan','rector','admin')",
            name="users_role_check",
        ),
    )

    student: Mapped[Optional["Student"]] = relationship(
        back_populates="user", uselist=False
    )
    teacher: Mapped[Optional["Teacher"]] = relationship(
        back_populates="user", uselist=False
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    student_card: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    faculty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    course: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tab_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String(150), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subjects: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    max_hours_week: Mapped[int] = mapped_column(Integer, default=18)

    user: Mapped[User] = relationship(back_populates="teacher")


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    room: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_type: Mapped[str] = mapped_column(String(10), default="both")
    valid_from: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 1 AND 6", name="schedule_day_check"),
        CheckConstraint("pair_number BETWEEN 1 AND 6", name="schedule_pair_check"),
        CheckConstraint(
            "week_type IN ('odd','even','both')", name="schedule_week_check"
        ),
    )


class Substitution(Base):
    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedule.id"))
    original_teacher: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    substitute_teacher: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teachers.id"), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','done')",
            name="substitution_status_check",
        ),
    )


class AccessCode(Base):
    __tablename__ = "access_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('dekan','rector','admin')", name="access_role_check"),
    )


class EventLog(Base):
    __tablename__ = "events_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CertificateRequest(Base):
    __tablename__ = "certificate_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    cert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'ready', 'rejected')",
            name="cert_status_check",
        ),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_new_certs: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_new_substitutions: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
