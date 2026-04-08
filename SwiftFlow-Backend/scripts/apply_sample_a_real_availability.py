from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import (  # noqa: E402
    Employee,
    EmployeeAvailability,
    EmployeeStoreAccess,
    EmploymentStatus,
    EmploymentType,
    NationalityStatus,
    SessionLocal,
    Store,
)


STORE_ID = 1
ANCHOR_MONDAY = date(2026, 3, 30)


def parse_hour_range(start_hour: int, end_hour: int) -> tuple[time, time]:
    return time(start_hour, 0), time(end_hour, 0)


FULL_DAY = parse_hour_range(9, 23)


def build_weekly_windows() -> dict[str, list[tuple[int, time, time]]]:
    return {
        "A_FT_1": [(day, *FULL_DAY) for day in range(7)],
        "A_FT_2": [(day, *FULL_DAY) for day in range(7)],
        "A_FT_3": [(day, *FULL_DAY) for day in range(7)],
        "A_FT_4": [(day, *FULL_DAY) for day in range(7)],
        "A_PT_1": [
            (0, *FULL_DAY),
            (1, *FULL_DAY),
            (2, *parse_hour_range(9, 15)),
            (3, *FULL_DAY),
            (4, *FULL_DAY),
            (6, *FULL_DAY),
        ],
        "A_PT_2": [
            (0, *parse_hour_range(7, 23)),
            (1, *parse_hour_range(7, 23)),
        ],
        "A_PT_3": [
            (1, *parse_hour_range(6, 23)),
            (5, *parse_hour_range(11, 15)),
        ],
        "A_PT_4": [
            (0, *FULL_DAY),
            (1, *FULL_DAY),
            (2, *FULL_DAY),
        ],
        "A_PT_5": [
            (1, *FULL_DAY),
            (2, *FULL_DAY),
            (3, *FULL_DAY),
            (4, *FULL_DAY),
            (5, *FULL_DAY),
            (6, *FULL_DAY),
        ],
        "A_PT_6": [
            (1, *parse_hour_range(15, 23)),
        ],
        "A_PT_7": [
            (0, *parse_hour_range(9, 17)),
            (1, *FULL_DAY),
            (2, *FULL_DAY),
            (3, *FULL_DAY),
        ],
        "A_PT_8": [
            (1, *FULL_DAY),
            (4, *FULL_DAY),
            (5, *FULL_DAY),
            (6, *FULL_DAY),
        ],
        "A_PT_9": [
            (0, *FULL_DAY),
            (1, *FULL_DAY),
            (2, *FULL_DAY),
            (3, *FULL_DAY),
            (4, *FULL_DAY),
            (6, *FULL_DAY),
        ],
    }


def ensure_employee(
    *,
    db,
    name: str,
    employment_type: EmploymentType,
    has_key: bool,
    priority: int,
) -> Employee:
    employee = db.query(Employee).filter(Employee.name == name).first()
    if employee is None:
        employee = Employee(
            name=name,
            employment_status=EmploymentStatus.ACTIVE,
            employment_type=employment_type,
            nationality_status=NationalityStatus.OTHER,
            work_skill_score=60 if employment_type == EmploymentType.FULL_TIME else 55,
            management_skill_score=60 if employment_type == EmploymentType.FULL_TIME else 50,
            preferred_shift="no_preference",
            monthly_worked_hours=0.0,
            hours_month="2026-03",
            availability_anchor_monday=ANCHOR_MONDAY,
        )
        db.add(employee)
        db.flush()
    else:
        employee.employment_status = EmploymentStatus.ACTIVE
        employee.employment_type = employment_type
        employee.availability_anchor_monday = ANCHOR_MONDAY

    link = (
        db.query(EmployeeStoreAccess)
        .filter(
            EmployeeStoreAccess.employee_id == employee.id,
            EmployeeStoreAccess.store_id == STORE_ID,
        )
        .first()
    )
    if link is None:
        link = EmployeeStoreAccess(
            employee_id=employee.id,
            store_id=STORE_ID,
            priority=priority,
            has_key=has_key,
        )
        db.add(link)
    else:
        link.priority = priority
        link.has_key = has_key

    return employee


def main() -> None:
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == STORE_ID).first()
        if store is None:
            raise RuntimeError(f"Store {STORE_ID} not found")

        weekly_windows = build_weekly_windows()

        # Remove legacy cross-store helper from Sample A test pool.
        legacy_link = (
            db.query(EmployeeStoreAccess)
            .filter(
                EmployeeStoreAccess.store_id == STORE_ID,
                EmployeeStoreAccess.employee_id == 22,
            )
            .first()
        )
        if legacy_link is not None:
            db.delete(legacy_link)

        employee_specs = [
            ("A_FT_1", EmploymentType.FULL_TIME, True, 1),
            ("A_FT_2", EmploymentType.FULL_TIME, True, 1),
            ("A_FT_3", EmploymentType.FULL_TIME, False, 2),
            ("A_FT_4", EmploymentType.FULL_TIME, False, 2),
            ("A_PT_1", EmploymentType.PART_TIME, False, 2),
            ("A_PT_2", EmploymentType.PART_TIME, False, 2),
            ("A_PT_3", EmploymentType.PART_TIME, False, 3),
            ("A_PT_4", EmploymentType.PART_TIME, False, 3),
            ("A_PT_5", EmploymentType.PART_TIME, False, 2),
            ("A_PT_6", EmploymentType.PART_TIME, False, 3),
            ("A_PT_7", EmploymentType.PART_TIME, False, 2),
            ("A_PT_8", EmploymentType.PART_TIME, False, 3),
            ("A_PT_9", EmploymentType.PART_TIME, False, 2),
        ]

        employees: dict[str, Employee] = {}
        for name, employment_type, has_key, priority in employee_specs:
            employees[name] = ensure_employee(
                db=db,
                name=name,
                employment_type=employment_type,
                has_key=has_key,
                priority=priority,
            )

        target_employee_ids = [employee.id for employee in employees.values()]
        (
            db.query(EmployeeStoreAccess)
            .filter(
                EmployeeStoreAccess.store_id == STORE_ID,
                ~EmployeeStoreAccess.employee_id.in_(target_employee_ids),
            )
            .delete(synchronize_session=False)
        )

        # Clear existing Sample A availability and rebuild from provided weekly data.
        (
            db.query(EmployeeAvailability)
            .filter(EmployeeAvailability.employee_id.in_(target_employee_ids))
            .delete(synchronize_session=False)
        )

        for name, windows in weekly_windows.items():
            employee = employees[name]
            for day_of_week, start_time, end_time in windows:
                db.add(
                    EmployeeAvailability(
                        employee_id=employee.id,
                        week_offset=0,
                        day_of_week=day_of_week,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )

        db.commit()
        print("Applied Sample A real-world weekly availability test set.")
        print("Assumption: all 4 full-time employees are available 09:00-23:00 daily.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
