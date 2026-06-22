"""
All database reads/writes live here. Handlers never touch SQLAlchemy
sessions directly - they call these functions. Keeps DB logic testable
and in one place if the schema or backend ever changes.
"""
from datetime import datetime
from typing import Optional

from database.models import User, Task, Reminder, FoodPlace, Recipe, TaskStatus, Priority
from database.session import SessionLocal


# ---------- Users ----------

def get_or_create_user(telegram_id: int, display_name: str) -> User:
    with SessionLocal() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            return user
        user = User(telegram_id=telegram_id, display_name=display_name)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter_by(telegram_id=telegram_id).first()


def get_all_users() -> list[User]:
    with SessionLocal() as session:
        return session.query(User).all()


def get_user_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter_by(id=user_id).first()


# ---------- Tasks ----------

def create_task(
    description: str,
    created_by_id: int,
    assigned_to_id: Optional[int],
    assigned_both: bool,
    due_date: Optional[datetime],
    priority: Priority,
) -> Task:
    with SessionLocal() as session:
        task = Task(
            description=description,
            created_by_id=created_by_id,
            assigned_to_id=assigned_to_id,
            assigned_both=assigned_both,
            due_date=due_date,
            priority=priority,
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def get_pending_tasks() -> list[Task]:
    """
    Ordered by priority (high -> normal -> low), then by due date within
    each priority group. SQLAlchemy's case() lets us assign a sort rank
    to the Priority enum since alphabetical order wouldn't put High first.
    """
    from sqlalchemy import case

    priority_order = case(
        (Task.priority == Priority.HIGH, 0),
        (Task.priority == Priority.NORMAL, 1),
        (Task.priority == Priority.LOW, 2),
        else_=3,
    )

    with SessionLocal() as session:
        return (
            session.query(Task)
            .filter_by(status=TaskStatus.PENDING)
            .order_by(priority_order, Task.due_date.asc().nullslast())
            .all()
        )


def find_pending_task_by_keyword(keyword: str) -> Optional[Task]:
    """Used by /done <keyword> - case-insensitive partial match on description."""
    with SessionLocal() as session:
        return (
            session.query(Task)
            .filter(Task.status == TaskStatus.PENDING)
            .filter(Task.description.ilike(f"%{keyword}%"))
            .first()
        )


def get_task_by_id(task_id: int) -> Optional[Task]:
    with SessionLocal() as session:
        return session.query(Task).filter_by(id=task_id).first()


def delete_task(task_id: int) -> bool:
    """Permanently removes a task. Returns True if something was actually deleted."""
    with SessionLocal() as session:
        task = session.query(Task).filter_by(id=task_id).first()
        if not task:
            return False
        session.delete(task)
        session.commit()
        return True


def complete_task(task_id: int, completed_by_id: int) -> Optional[Task]:
    with SessionLocal() as session:
        task = session.query(Task).filter_by(id=task_id).first()
        if not task:
            return None
        task.status = TaskStatus.DONE
        task.completed_by_id = completed_by_id
        task.completed_at = datetime.utcnow()
        session.commit()
        session.refresh(task)
        return task


# ---------- Reminders ----------

def create_reminder(
    text: str,
    created_by_id: int,
    remind_at: datetime,
    recurrence_unit: Optional[str] = None,
    recurrence_interval: Optional[int] = None,
    recurrence_weekday: Optional[int] = None,
    recurrence_end_date: Optional[datetime] = None,
    recurrence_max_count: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
    assigned_both: bool = False,
) -> Reminder:
    with SessionLocal() as session:
        reminder = Reminder(
            text=text,
            created_by_id=created_by_id,
            remind_at=remind_at,
            recurrence_unit=recurrence_unit,
            recurrence_interval=recurrence_interval,
            recurrence_weekday=recurrence_weekday,
            recurrence_end_date=recurrence_end_date,
            recurrence_max_count=recurrence_max_count,
            recurrence_count_so_far=0,
            assigned_to_id=assigned_to_id,
            assigned_both=assigned_both,
        )
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder


def get_due_reminders(now: datetime) -> list[Reminder]:
    with SessionLocal() as session:
        return (
            session.query(Reminder)
            .filter(Reminder.is_active == True)  # noqa: E712
            .filter(Reminder.remind_at <= now)
            .all()
        )


def reschedule_reminder(reminder_id: int, next_time: datetime):
    """Used for recurring reminders - push remind_at forward instead of deactivating, and track how many times it's fired."""
    with SessionLocal() as session:
        reminder = session.query(Reminder).filter_by(id=reminder_id).first()
        if reminder:
            reminder.remind_at = next_time
            reminder.recurrence_count_so_far = (reminder.recurrence_count_so_far or 0) + 1
            session.commit()


def deactivate_reminder(reminder_id: int):
    with SessionLocal() as session:
        reminder = session.query(Reminder).filter_by(id=reminder_id).first()
        if reminder:
            reminder.is_active = False
            session.commit()


def get_upcoming_reminders(limit: int = 5) -> list[Reminder]:
    with SessionLocal() as session:
        return (
            session.query(Reminder)
            .filter(Reminder.is_active == True)  # noqa: E712
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
            .all()
        )


def get_active_reminders() -> list[Reminder]:
    """All active reminders (any time in the future, not just today/tomorrow) - used by /reminders and the delete flow."""
    with SessionLocal() as session:
        return (
            session.query(Reminder)
            .filter(Reminder.is_active == True)  # noqa: E712
            .order_by(Reminder.remind_at.asc())
            .all()
        )


def get_reminder_by_id(reminder_id: int) -> Optional[Reminder]:
    with SessionLocal() as session:
        return session.query(Reminder).filter_by(id=reminder_id).first()


def delete_reminder(reminder_id: int) -> bool:
    """Permanently removes a reminder. Returns True if something was actually deleted."""
    with SessionLocal() as session:
        reminder = session.query(Reminder).filter_by(id=reminder_id).first()
        if not reminder:
            return False
        session.delete(reminder)
        session.commit()
        return True


def get_reminders_in_range(start: datetime, end: datetime) -> list[Reminder]:
    """Active reminders whose remind_at falls within [start, end) - used by /today to show today+tomorrow."""
    with SessionLocal() as session:
        return (
            session.query(Reminder)
            .filter(Reminder.is_active == True)  # noqa: E712
            .filter(Reminder.remind_at >= start)
            .filter(Reminder.remind_at < end)
            .order_by(Reminder.remind_at.asc())
            .all()
        )


# ---------- Food Places ----------

def create_food_place(name: str, cuisine: str, map_link: Optional[str], added_by_id: int) -> FoodPlace:
    with SessionLocal() as session:
        place = FoodPlace(name=name, cuisine=cuisine, map_link=map_link, added_by_id=added_by_id)
        session.add(place)
        session.commit()
        session.refresh(place)
        return place


def get_all_food_places() -> list[FoodPlace]:
    with SessionLocal() as session:
        return session.query(FoodPlace).order_by(FoodPlace.name.asc()).all()


def get_food_place_by_id(place_id: int) -> Optional[FoodPlace]:
    with SessionLocal() as session:
        return session.query(FoodPlace).filter_by(id=place_id).first()


def delete_food_place(place_id: int) -> bool:
    with SessionLocal() as session:
        place = session.query(FoodPlace).filter_by(id=place_id).first()
        if not place:
            return False
        session.delete(place)
        session.commit()
        return True


# ---------- Recipes ----------

def create_recipe(name: str, tag: str, link_or_desc: Optional[str], added_by_id: int) -> Recipe:
    with SessionLocal() as session:
        recipe = Recipe(name=name, tag=tag, link_or_desc=link_or_desc, added_by_id=added_by_id)
        session.add(recipe)
        session.commit()
        session.refresh(recipe)
        return recipe


def get_all_recipes() -> list[Recipe]:
    with SessionLocal() as session:
        return session.query(Recipe).order_by(Recipe.tag.asc(), Recipe.name.asc()).all()


def get_recipe_by_id(recipe_id: int) -> Optional[Recipe]:
    with SessionLocal() as session:
        return session.query(Recipe).filter_by(id=recipe_id).first()


def delete_recipe(recipe_id: int) -> bool:
    with SessionLocal() as session:
        recipe = session.query(Recipe).filter_by(id=recipe_id).first()
        if not recipe:
            return False
        session.delete(recipe)
        session.commit()
        return True
