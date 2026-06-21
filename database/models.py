"""
Database models.

Tasks and Reminders are used in v1. ShoppingItem and Expense are defined
now so the schema doesn't need a migration when those features are built -
the tables just sit empty until handlers are added for them.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Float
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Priority(str, enum.Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"


class User(Base):
    """
    A household member. Created automatically the first time someone runs
    /start in the group. display_name is what shows up on buttons and
    task cards (e.g. "Alex", "Sam") rather than raw Telegram usernames,
    since not everyone sets a Telegram username.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    display_name = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks_assigned = relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assigned_to_id"
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    description = Column(String(255), nullable=False)

    # Nullable: if assigned_both is True, assigned_to_id is ignored.
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_both = Column(Boolean, default=False)

    due_date = Column(DateTime, nullable=True)
    priority = Column(Enum(Priority), default=Priority.NORMAL)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignee = relationship("User", foreign_keys=[assigned_to_id])
    creator = relationship("User", foreign_keys=[created_by_id])
    completer = relationship("User", foreign_keys=[completed_by_id])


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    text = Column(String(255), nullable=False)
    remind_at = Column(DateTime, nullable=False)  # next (or only) fire time

    # Recurrence, broken into structured fields rather than one string:
    #   recurrence_unit: None (one-off), "day", "week"
    #   recurrence_interval: e.g. 1 = every day/week, 4 = every 4 days
    #   recurrence_weekday: 0=Mon..6=Sun, only used when unit="week"
    # This replaces the old single "weekly:sun" style string so we can
    # support "every 4 days" / "every 3 weeks" etc, not just weekly.
    recurrence_unit = Column(String(10), nullable=True)
    recurrence_interval = Column(Integer, nullable=True)
    recurrence_weekday = Column(Integer, nullable=True)

    # End condition for a recurring reminder - at most one of these is set.
    # If both are None and recurrence_unit is set, it repeats forever.
    recurrence_end_date = Column(DateTime, nullable=True)
    recurrence_max_count = Column(Integer, nullable=True)
    recurrence_count_so_far = Column(Integer, default=0)

    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_both = Column(Boolean, default=False)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by_id])
    assignee = relationship("User", foreign_keys=[assigned_to_id])


class ShoppingItem(Base):
    """Not wired up to any handler yet - reserved for a future /shopping command."""
    __tablename__ = "shopping_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_bought = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FoodPlace(Base):
    """A restaurant/cafe/brunch spot recommendation."""
    __tablename__ = "food_places"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    cuisine = Column(String(100), nullable=False)
    map_link = Column(String(500), nullable=True)
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    added_by = relationship("User", foreign_keys=[added_by_id])


class Expense(Base):
    """Not wired up to any handler yet - reserved for a future /expense command."""
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    paid_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
