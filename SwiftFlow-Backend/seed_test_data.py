from datetime import date, datetime

from database import (
    Area,
    EmploymentStatus,
    EmploymentType,
    Employee,
    EmployeeAvailability,
    EmployeeRelation,
    EmployeeSkill,
    EmployeeStoreAccess,
    NationalityStatus,
    RoleCode,
    ScheduleEntry,
    SessionLocal,
    SkillLevel,
    Store,
    StoreScheduleRuleConfig,
    StoreStaffingDemand,
    Role,
    User,
    UserAreaAccess,
    UserStoreAccess,
    init_db_and_seed,
)


def parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def hour_profile(*segments: tuple[int, int, int]) -> dict[int, int]:
    profile: dict[int, int] = {}
    for start_hour, end_hour, min_staff in segments:
        for hour in range(start_hour, end_hour + 1):
            profile[hour] = min_staff
    return profile


def week_profiles(
    weekday: dict[int, int],
    saturday: dict[int, int] | None = None,
    sunday: dict[int, int] | None = None,
) -> dict[int, dict[int, int]]:
    profiles = {day: dict(weekday) for day in range(7)}
    if saturday is not None:
        profiles[5] = dict(saturday)
    if sunday is not None:
        profiles[6] = dict(sunday)
    return profiles


def schedule_for_days(days: list[int], start_time: str, end_time: str) -> dict[int, tuple[str, str]]:
    return {day: (start_time, end_time) for day in days}


def merge_schedule_windows(*parts: dict[int, tuple[str, str]]) -> dict[int, tuple[str, str]]:
    merged: dict[int, tuple[str, str]] = {}
    for part in parts:
        merged.update(part)
    return merged


def upsert_store(db, name: str, open_time: str, close_time: str) -> Store:
    store = db.query(Store).filter(Store.name == name).first()
    if not store:
        store = Store(name=name)
        db.add(store)
        db.flush()
    store.open_time = parse_time(open_time)
    store.close_time = parse_time(close_time)
    return store


def upsert_area(db, name: str) -> Area:
    area = db.query(Area).filter(Area.name == name).first()
    if not area:
        area = Area(name=name)
        db.add(area)
        db.flush()
    area.name = name
    return area


def upsert_employee(
    db,
    *,
    name: str,
    employment_type: EmploymentType,
    nationality_status: NationalityStatus,
    work_skill_score: int,
    management_skill_score: int,
    monthly_worked_hours: float,
    preferred_shift: str = "no_preference",
):
    employee = db.query(Employee).filter(Employee.name == name).first()
    if not employee:
        employee = Employee(name=name, employment_type=employment_type)
        db.add(employee)
        db.flush()

    employee.employment_status = EmploymentStatus.ACTIVE
    employee.employment_type = employment_type
    employee.nationality_status = nationality_status
    employee.work_skill_score = work_skill_score
    employee.management_skill_score = management_skill_score
    employee.preferred_shift = preferred_shift
    employee.monthly_worked_hours = float(monthly_worked_hours)
    employee.hours_month = date.today().strftime("%Y-%m")
    return employee


def replace_employee_stores(db, employee: Employee, store_settings: list[dict]):
    for row in db.query(EmployeeStoreAccess).filter(EmployeeStoreAccess.employee_id == employee.id).all():
        db.delete(row)
    for item in store_settings:
        db.add(
            EmployeeStoreAccess(
                employee_id=employee.id,
                store_id=item["store_id"],
                priority=item.get("priority"),
                has_key=bool(item.get("has_key", False)),
            )
        )


def replace_employee_skills(db, employee: Employee, skills: list[dict]):
    for row in db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee.id).all():
        db.delete(row)
    for item in skills:
        db.add(
            EmployeeSkill(
                employee_id=employee.id,
                skill_code=item["skill_code"],
                level=item["level"],
            )
        )


def replace_employee_availability(db, employee: Employee, weekly_schedule: dict[int, tuple[str, str] | None]):
    for row in db.query(EmployeeAvailability).filter(EmployeeAvailability.employee_id == employee.id).all():
        db.delete(row)
    for week_offset in (0, 1):
        for day_of_week in range(7):
            slot = weekly_schedule.get(day_of_week)
            if not slot:
                continue
            start_time, end_time = slot
            db.add(
                EmployeeAvailability(
                    employee_id=employee.id,
                    week_offset=week_offset,
                    day_of_week=day_of_week,
                    start_time=parse_time(start_time),
                    end_time=parse_time(end_time),
                )
            )


def replace_store_rule_config(
    db,
    *,
    store_id: int,
    schedule_archetype: str,
    weekday_total_hours_limit: float,
    weekend_total_hours_limit: float,
    min_backroom_per_hour: int = 1,
    require_opening_dual_skill: bool = True,
    min_opening_keyholders: int = 1,
    min_closing_keyholders: int = 1,
    store_key_count: int = 0,
):
    config = db.query(StoreScheduleRuleConfig).filter(StoreScheduleRuleConfig.store_id == store_id).first()
    if not config:
        config = StoreScheduleRuleConfig(store_id=store_id)
        db.add(config)
    config.schedule_archetype = schedule_archetype
    config.weekday_total_hours_limit = weekday_total_hours_limit
    config.weekend_total_hours_limit = weekend_total_hours_limit
    config.min_backroom_per_hour = min_backroom_per_hour
    config.require_opening_dual_skill = require_opening_dual_skill
    config.min_opening_keyholders = min_opening_keyholders
    config.min_closing_keyholders = min_closing_keyholders
    config.store_key_count = store_key_count


def replace_store_staffing_demand(db, *, store_id: int, profiles_by_day: dict[int, dict[int, int]]):
    db.query(StoreStaffingDemand).filter(StoreStaffingDemand.store_id == store_id).delete(synchronize_session=False)
    for day_of_week, day_profile in sorted(profiles_by_day.items()):
        for hour, min_staff in sorted(day_profile.items()):
            db.add(
                StoreStaffingDemand(
                    store_id=store_id,
                    day_of_week=day_of_week,
                    hour=hour,
                    min_staff=min_staff,
                )
            )


def replace_manager_store_access(db, manager_username: str, store_ids: list[int]):
    manager = db.query(User).filter(User.username == manager_username).first()
    if not manager or manager.role.code != RoleCode.STORE_MANAGER:
        return
    for row in db.query(UserStoreAccess).filter(UserStoreAccess.user_id == manager.id).all():
        db.delete(row)
    for store_id in sorted(set(store_ids)):
        db.add(UserStoreAccess(user_id=manager.id, store_id=store_id))


def replace_area_manager_area_access(db, manager_username: str, area_names: list[str]):
    manager = db.query(User).filter(User.username == manager_username).first()
    if not manager or manager.role.code != RoleCode.AREA_MANAGER:
        return
    for row in db.query(UserAreaAccess).filter(UserAreaAccess.user_id == manager.id).all():
        db.delete(row)
    areas = db.query(Area).filter(Area.name.in_(sorted(set(area_names)))).all()
    for area in areas:
        db.add(UserAreaAccess(user_id=manager.id, area_id=area.id))


def upsert_demo_user(
    db,
    *,
    username: str,
    full_name: str,
    password: str,
    role_code: RoleCode,
    employee_id: int | None,
):
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        raise RuntimeError(f"Role not found: {role_code.value}")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            full_name=full_name,
            password_hash=password,
            role_id=role.id,
            employee_id=employee_id,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.full_name = full_name
        user.password_hash = password
        user.role_id = role.id
        user.employee_id = employee_id
        user.is_active = True
        for link in list(user.store_links):
            db.delete(link)
        for link in list(user.area_links):
            db.delete(link)
    return user


def replace_employee_relations(db, employee_name_to_id: dict[str, int]):
    db.query(EmployeeRelation).delete(synchronize_session=False)
    relation_specs = []
    for name_a, name_b, severity in relation_specs:
        id_a = employee_name_to_id.get(name_a)
        id_b = employee_name_to_id.get(name_b)
        if not id_a or not id_b:
            continue
        if id_a > id_b:
            id_a, id_b = id_b, id_a
        db.add(
            EmployeeRelation(
                employee_id_a=id_a,
                employee_id_b=id_b,
                relation_type="bad",
                severity=severity,
            )
        )


def clear_existing_business_rows(db):
    db.query(ScheduleEntry).delete(synchronize_session=False)
    db.query(StoreStaffingDemand).delete(synchronize_session=False)
    db.query(StoreScheduleRuleConfig).delete(synchronize_session=False)
    db.query(UserAreaAccess).delete(synchronize_session=False)
    db.query(EmployeeAvailability).delete(synchronize_session=False)
    db.query(EmployeeSkill).delete(synchronize_session=False)
    db.query(EmployeeRelation).delete(synchronize_session=False)
    db.query(EmployeeStoreAccess).delete(synchronize_session=False)
    db.query(UserStoreAccess).delete(synchronize_session=False)
    db.query(Employee).delete(synchronize_session=False)
    db.query(Store).delete(synchronize_session=False)
    db.query(Area).delete(synchronize_session=False)
    db.commit()


def main():
    init_db_and_seed()
    db = SessionLocal()
    try:
        clear_existing_business_rows(db)

        area_specs = [
            {"key": "north", "name": "示例北区"},
            {"key": "south", "name": "示例南区"},
        ]
        area_id_map: dict[str, int] = {}
        for spec in area_specs:
            area = upsert_area(db, spec["name"])
            db.flush()
            area_id_map[spec["key"]] = area.id

        store_specs = [
            {
                "key": "store_a",
                "name": "示例店A-高峰型",
                "area_key": "north",
                "open_time": "09:00",
                "close_time": "23:00",
                "schedule_archetype": "peak_dual_core",
                "weekday_total_hours_limit": 42.0,
                "weekend_total_hours_limit": 46.0,
                "store_key_count": 3,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 11, 1), (12, 12, 2), (13, 20, 3), (21, 23, 3)),
                    saturday=hour_profile((9, 11, 1), (12, 12, 2), (13, 23, 3)),
                    sunday=hour_profile((9, 11, 1), (12, 12, 2), (13, 23, 3)),
                ),
            },
            {
                "key": "store_b",
                "name": "示例店B-轻量型",
                "area_key": "north",
                "open_time": "09:00",
                "close_time": "21:30",
                "schedule_archetype": "light_single_core",
                "weekday_total_hours_limit": 14.0,
                "weekend_total_hours_limit": 18.0,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 22, 1)),
                    saturday=hour_profile((9, 13, 2), (14, 22, 1)),
                    sunday=hour_profile((9, 13, 2), (14, 22, 1)),
                ),
            },
            {
                "key": "store_c",
                "name": "示例店C-标准型",
                "area_key": "north",
                "open_time": "09:00",
                "close_time": "22:30",
                "schedule_archetype": "auto",
                "weekday_total_hours_limit": 30.0,
                "weekend_total_hours_limit": 30.0,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 11, 1), (12, 22, 2)),
                    saturday=hour_profile((9, 11, 1), (12, 22, 3)),
                    sunday=hour_profile((9, 11, 1), (12, 22, 3)),
                ),
            },
            {
                "key": "store_d",
                "name": "示例店D-网格型",
                "area_key": "south",
                "open_time": "09:00",
                "close_time": "22:30",
                "schedule_archetype": "auto",
                "weekday_total_hours_limit": 28.0,
                "weekend_total_hours_limit": 28.0,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 14, 1), (15, 22, 2)),
                    saturday=hour_profile((9, 14, 1), (15, 22, 2)),
                    sunday=hour_profile((9, 14, 1), (15, 22, 2)),
                ),
            },
            {
                "key": "store_e",
                "name": "示例店E-中量型",
                "area_key": "south",
                "open_time": "09:00",
                "close_time": "22:00",
                "schedule_archetype": "auto",
                "weekday_total_hours_limit": 26.0,
                "weekend_total_hours_limit": 28.0,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 11, 1), (12, 17, 2), (18, 22, 2)),
                    saturday=hour_profile((9, 11, 1), (12, 22, 2)),
                    sunday=hour_profile((9, 11, 1), (12, 22, 2)),
                ),
            },
            {
                "key": "store_f",
                "name": "示例店F-周末峰值型",
                "area_key": "south",
                "open_time": "09:00",
                "close_time": "22:30",
                "schedule_archetype": "auto",
                "weekday_total_hours_limit": 33.0,
                "weekend_total_hours_limit": 35.0,
                "profiles_by_day": week_profiles(
                    weekday=hour_profile((9, 11, 1), (12, 14, 2), (15, 22, 2)),
                    saturday=hour_profile((9, 11, 2), (12, 22, 3)),
                    sunday=hour_profile((9, 11, 2), (12, 22, 3)),
                ),
            },
        ]

        store_id_map: dict[str, int] = {}
        for spec in store_specs:
            store = upsert_store(db, spec["name"], spec["open_time"], spec["close_time"])
            db.flush()
            store.area_id = area_id_map[spec["area_key"]]
            store_id_map[spec["key"]] = store.id
            replace_store_rule_config(
                db,
                store_id=store.id,
                schedule_archetype=spec["schedule_archetype"],
                weekday_total_hours_limit=spec["weekday_total_hours_limit"],
                weekend_total_hours_limit=spec["weekend_total_hours_limit"],
                min_backroom_per_hour=spec.get("min_backroom_per_hour", 1),
                require_opening_dual_skill=spec.get("require_opening_dual_skill", True),
                min_opening_keyholders=spec.get("min_opening_keyholders", 1),
                min_closing_keyholders=spec.get("min_closing_keyholders", 1),
                store_key_count=spec.get("store_key_count", 0),
            )
            replace_store_staffing_demand(db, store_id=store.id, profiles_by_day=spec["profiles_by_day"])

        employee_specs = [
            {
                "name": "演示区域经理",
                "employment_type": EmploymentType.FULL_TIME,
                "preferred_shift": "opening",
                "nationality_status": NationalityStatus.OTHER,
                "work_skill_score": 90,
                "management_skill_score": 92,
                "monthly_worked_hours": 96.0,
                "stores": [
                    {"store_key": "store_a", "priority": 1, "has_key": True},
                    {"store_key": "store_b", "priority": 2, "has_key": False},
                    {"store_key": "store_c", "priority": 3, "has_key": False},
                ],
                "skills": [
                    {"skill_code": "front_service", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "cashier", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "backroom", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "inventory", "level": SkillLevel.PROFICIENT},
                ],
                "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4], "09:00", "18:00"),
            },
            {
                "name": "演示店长",
                "employment_type": EmploymentType.FULL_TIME,
                "preferred_shift": "opening",
                "nationality_status": NationalityStatus.OTHER,
                "work_skill_score": 86,
                "management_skill_score": 88,
                "monthly_worked_hours": 124.0,
                "stores": [
                    {"store_key": "store_c", "priority": 1, "has_key": True},
                ],
                "skills": [
                    {"skill_code": "front_service", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "cashier", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "floor", "level": SkillLevel.PROFICIENT},
                    {"skill_code": "backroom", "level": SkillLevel.BASIC},
                ],
                "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5], "09:00", "19:00"),
            },
            {
                "name": "演示员工",
                "employment_type": EmploymentType.PART_TIME,
                "preferred_shift": "midday",
                "nationality_status": NationalityStatus.OTHER,
                "work_skill_score": 74,
                "management_skill_score": 38,
                "monthly_worked_hours": 64.0,
                "stores": [
                    {"store_key": "store_c", "priority": 2, "has_key": False},
                ],
                "skills": [
                    {"skill_code": "front_service", "level": SkillLevel.BASIC},
                    {"skill_code": "cashier", "level": SkillLevel.BASIC},
                    {"skill_code": "floor", "level": SkillLevel.BASIC},
                ],
                "weekly_schedule": merge_schedule_windows(
                    schedule_for_days([1, 2, 4], "12:00", "20:00"),
                    schedule_for_days([5, 6], "14:00", "22:00"),
                ),
            },
            # Store A demo uses anonymized staff names and a generic availability sample.
            {"name": "FT_A1", "employment_type": EmploymentType.FULL_TIME, "preferred_shift": "opening", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 92, "management_skill_score": 84, "monthly_worked_hours": 128.0, "stores": [{"store_key": "store_a", "priority": 1, "has_key": True}], "skills": [{"skill_code": "front_service", "level": SkillLevel.PROFICIENT}, {"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}, {"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_backroom_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_machine_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_settlement", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "09:00", "23:00")},
            {"name": "FT_A2", "employment_type": EmploymentType.FULL_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 88, "management_skill_score": 80, "monthly_worked_hours": 134.0, "stores": [{"store_key": "store_a", "priority": 1, "has_key": True}], "skills": [{"skill_code": "front_service", "level": SkillLevel.PROFICIENT}, {"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}, {"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_backroom_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_machine_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_settlement", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "09:00", "23:00")},
            {"name": "FT_A3", "employment_type": EmploymentType.FULL_TIME, "preferred_shift": "opening", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 86, "management_skill_score": 66, "monthly_worked_hours": 120.0, "stores": [{"store_key": "store_a", "priority": 1, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.PROFICIENT}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}, {"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_machine_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_settlement", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "09:00", "23:00")},
            {"name": "FT_A4", "employment_type": EmploymentType.FULL_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 84, "management_skill_score": 68, "monthly_worked_hours": 122.0, "stores": [{"store_key": "store_a", "priority": 1, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.PROFICIENT}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}, {"skill_code": "customer_service", "level": SkillLevel.BASIC}, {"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_machine_clean", "level": SkillLevel.PROFICIENT}, {"skill_code": "close_settlement", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "09:00", "23:00")},
            {"name": "PT_A1", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 76, "management_skill_score": 40, "monthly_worked_hours": 62.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.BASIC}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "customer_service", "level": SkillLevel.BASIC}, {"skill_code": "backroom", "level": SkillLevel.BASIC}], "weekly_schedule": merge_schedule_windows(schedule_for_days([0, 2], "19:00", "23:00"), schedule_for_days([1], "15:00", "23:00"))},
            {"name": "PT_A2", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 72, "management_skill_score": 36, "monthly_worked_hours": 48.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "backroom", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.BASIC}], "weekly_schedule": merge_schedule_windows(schedule_for_days([0, 1], "15:00", "23:00"), schedule_for_days([4], "18:00", "23:00"))},
            {"name": "PT_A3", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "midday", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 74, "management_skill_score": 34, "monthly_worked_hours": 44.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.BASIC}, {"skill_code": "inventory", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.BASIC}, {"skill_code": "backroom", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_machine_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_settlement", "level": SkillLevel.BASIC}], "weekly_schedule": merge_schedule_windows(merge_schedule_windows(schedule_for_days([1], "06:00", "23:00"), schedule_for_days([4], "11:00", "21:00")), schedule_for_days([5, 6], "18:00", "23:00"))},
            {"name": "PT_A4", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 70, "management_skill_score": 30, "monthly_worked_hours": 56.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.BASIC}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_machine_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_settlement", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([1], "15:00", "23:00")},
            {"name": "PT_A5", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 75, "management_skill_score": 32, "monthly_worked_hours": 78.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.BASIC}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.BASIC}, {"skill_code": "backroom", "level": SkillLevel.BASIC}, {"skill_code": "close_backroom_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_machine_clean", "level": SkillLevel.BASIC}, {"skill_code": "close_settlement", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([3], "15:00", "23:00")},
            {"name": "PT_A6", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 73, "management_skill_score": 33, "monthly_worked_hours": 52.0, "stores": [{"store_key": "store_a", "priority": 2, "has_key": False}], "skills": [{"skill_code": "front_service", "level": SkillLevel.BASIC}, {"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "backroom", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([3], "18:00", "23:00")},
            {"name": "PT_extra_1", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 69, "management_skill_score": 28, "monthly_worked_hours": 24.0, "stores": [{"store_key": "store_a", "priority": 4, "has_key": False}], "skills": [{"skill_code": "customer_service", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2], "09:00", "23:00")},
            {"name": "PT_extra_2", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 71, "management_skill_score": 31, "monthly_worked_hours": 54.0, "stores": [{"store_key": "store_a", "priority": 4, "has_key": False}], "skills": [{"skill_code": "floor", "level": SkillLevel.BASIC}, {"skill_code": "customer_service", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([1, 4, 5, 6], "09:00", "23:00")},
            {"name": "PT_extra_3", "employment_type": EmploymentType.PART_TIME, "preferred_shift": "closing", "nationality_status": NationalityStatus.OTHER, "work_skill_score": 77, "management_skill_score": 35, "monthly_worked_hours": 80.0, "stores": [{"store_key": "store_a", "priority": 4, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 6], "09:00", "23:00")},
            {"name": "B_core_full", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 85, "management_skill_score": 72, "monthly_worked_hours": 138.0, "stores": [{"store_key": "store_b", "priority": 1, "has_key": True}], "skills": [{"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "09:00", "21:30")},
            {"name": "B_open_support", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 70, "management_skill_score": 36, "monthly_worked_hours": 79.0, "stores": [{"store_key": "store_b", "priority": 2, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.BASIC}], "weekly_schedule": merge_schedule_windows(schedule_for_days([3], "09:00", "15:00"), schedule_for_days([5, 6], "09:00", "16:00"))},
            {"name": "B_close_support", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.OTHER, "work_skill_score": 68, "management_skill_score": 32, "monthly_worked_hours": 41.0, "stores": [{"store_key": "store_b", "priority": 3, "has_key": False}, {"store_key": "store_d", "priority": 4, "has_key": False}], "skills": [{"skill_code": "customer_service", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([3, 5, 6], "12:00", "21:30")},
            {"name": "C_core_open", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 84, "management_skill_score": 78, "monthly_worked_hours": 126.0, "stores": [{"store_key": "store_c", "priority": 1, "has_key": True}], "skills": [{"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4], "09:00", "19:00")},
            {"name": "C_core_close", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.OTHER, "work_skill_score": 82, "management_skill_score": 64, "monthly_worked_hours": 122.0, "stores": [{"store_key": "store_c", "priority": 1, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 3, 4, 5, 6], "12:30", "22:30")},
            {"name": "C_mid_sg", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 75, "management_skill_score": 40, "monthly_worked_hours": 78.0, "stores": [{"store_key": "store_c", "priority": 2, "has_key": False}, {"store_key": "store_d", "priority": 3, "has_key": False}], "skills": [{"skill_code": "customer_service", "level": SkillLevel.BASIC}, {"skill_code": "floor", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "12:30", "22:30")},
            {"name": "D_core_full", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 80, "management_skill_score": 70, "monthly_worked_hours": 132.0, "stores": [{"store_key": "store_d", "priority": 1, "has_key": True}], "skills": [{"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 1, 3, 4, 5, 6], "09:00", "19:00")},
            {"name": "D_close_full", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.OTHER, "work_skill_score": 78, "management_skill_score": 60, "monthly_worked_hours": 116.0, "stores": [{"store_key": "store_d", "priority": 2, "has_key": False}], "skills": [{"skill_code": "inventory", "level": SkillLevel.BASIC}, {"skill_code": "cashier", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "12:30", "22:30")},
            {"name": "D_close_pt", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_PR, "work_skill_score": 68, "management_skill_score": 34, "monthly_worked_hours": 156.0, "stores": [{"store_key": "store_d", "priority": 2, "has_key": False}], "skills": [{"skill_code": "customer_service", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 2, 3, 4], "14:30", "22:30")},
            {"name": "E_core_open", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 82, "management_skill_score": 72, "monthly_worked_hours": 130.0, "stores": [{"store_key": "store_e", "priority": 1, "has_key": True}], "skills": [{"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "cashier", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 5], "09:00", "19:00")},
            {"name": "E_core_close", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.OTHER, "work_skill_score": 80, "management_skill_score": 64, "monthly_worked_hours": 124.0, "stores": [{"store_key": "store_e", "priority": 1, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 2, 3, 4, 5, 6], "12:00", "22:00")},
            {"name": "E_close_pt", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 69, "management_skill_score": 35, "monthly_worked_hours": 74.0, "stores": [{"store_key": "store_e", "priority": 2, "has_key": False}], "skills": [{"skill_code": "floor", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 3, 4, 5, 6], "16:00", "22:00")},
            {"name": "F_core_open", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 86, "management_skill_score": 75, "monthly_worked_hours": 136.0, "stores": [{"store_key": "store_f", "priority": 1, "has_key": True}], "skills": [{"skill_code": "backroom", "level": SkillLevel.PROFICIENT}, {"skill_code": "floor", "level": SkillLevel.PROFICIENT}], "weekly_schedule": schedule_for_days([0, 2, 3, 4, 6], "09:00", "19:00")},
            {"name": "F_core_close", "employment_type": EmploymentType.FULL_TIME, "nationality_status": NationalityStatus.OTHER, "work_skill_score": 84, "management_skill_score": 67, "monthly_worked_hours": 129.0, "stores": [{"store_key": "store_f", "priority": 1, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.PROFICIENT}, {"skill_code": "inventory", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 4, 5, 6], "12:30", "22:30")},
            {"name": "F_mid_sg", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_CITIZEN, "work_skill_score": 73, "management_skill_score": 37, "monthly_worked_hours": 77.0, "stores": [{"store_key": "store_f", "priority": 2, "has_key": False}], "skills": [{"skill_code": "cashier", "level": SkillLevel.BASIC}, {"skill_code": "customer_service", "level": SkillLevel.BASIC}], "weekly_schedule": schedule_for_days([0, 1, 2, 3, 4, 5, 6], "12:30", "22:30")},
            {"name": "F_weekend_pt", "employment_type": EmploymentType.PART_TIME, "nationality_status": NationalityStatus.SG_PR, "work_skill_score": 71, "management_skill_score": 34, "monthly_worked_hours": 158.0, "stores": [{"store_key": "store_f", "priority": 2, "has_key": False}], "skills": [{"skill_code": "floor", "level": SkillLevel.BASIC}], "weekly_schedule": merge_schedule_windows(schedule_for_days([0, 3, 4], "16:30", "22:30"), schedule_for_days([5, 6], "14:30", "22:30"))},
        ]

        employees = []
        employee_name_to_id: dict[str, int] = {}
        for spec in employee_specs:
            employee = upsert_employee(
                db,
                name=spec["name"],
                employment_type=spec["employment_type"],
                nationality_status=spec["nationality_status"],
                work_skill_score=spec["work_skill_score"],
                management_skill_score=spec["management_skill_score"],
                monthly_worked_hours=spec["monthly_worked_hours"],
                preferred_shift=spec.get("preferred_shift", "no_preference"),
            )
            db.flush()
            replace_employee_stores(
                db,
                employee,
                [
                    {
                        "store_id": store_id_map[item["store_key"]],
                        "priority": item.get("priority"),
                        "has_key": item.get("has_key", False),
                    }
                    for item in spec["stores"]
                ],
            )
            replace_employee_skills(db, employee, spec["skills"])
            replace_employee_availability(db, employee, spec["weekly_schedule"])
            employees.append(employee)
            employee_name_to_id[employee.name] = employee.id

        replace_employee_relations(db, employee_name_to_id)
        upsert_demo_user(
            db,
            username="demo_area_manager",
            full_name="Demo Area Manager",
            password="demo_area_manager",
            role_code=RoleCode.AREA_MANAGER,
            employee_id=employee_name_to_id.get("演示区域经理"),
        )
        upsert_demo_user(
            db,
            username="demo_store_manager",
            full_name="Demo Store Manager",
            password="demo_store_manager",
            role_code=RoleCode.STORE_MANAGER,
            employee_id=employee_name_to_id.get("演示店长"),
        )
        upsert_demo_user(
            db,
            username="demo_staff",
            full_name="Demo Staff",
            password="demo_staff",
            role_code=RoleCode.STAFF,
            employee_id=employee_name_to_id.get("演示员工"),
        )
        replace_area_manager_area_access(db, "demo_area_manager", ["示例北区"])
        replace_manager_store_access(db, "demo_store_manager", [store_id_map["store_c"]])
        db.commit()

        print("Seeded generic demo scheduling data successfully.")
        print("Areas:", [spec["name"] for spec in area_specs])
        print("Stores:", [spec["name"] for spec in store_specs])
        print("Employees:", len(employees))
        print(
            "Demo accounts:",
            [
                "demo_area_manager / demo_area_manager",
                "demo_store_manager / demo_store_manager",
                "demo_staff / demo_staff",
            ],
        )
        print(
            "Part-time employees near 80h:",
            sorted(
                [
                    employee.name
                    for employee in employees
                    if employee.employment_type == EmploymentType.PART_TIME
                    and 72.0 <= float(employee.monthly_worked_hours) < 80.0
                ]
            ),
        )
        print(
            "Part-time employees near 160h:",
            sorted(
                [
                    employee.name
                    for employee in employees
                    if employee.employment_type == EmploymentType.PART_TIME
                    and 150.0 <= float(employee.monthly_worked_hours) < 160.0
                ]
            ),
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

