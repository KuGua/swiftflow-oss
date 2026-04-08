import base64
import hashlib
import hmac
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, time, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import importlib.util
from types import SimpleNamespace
from typing import List, Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import distinct, func, or_

from database import (
    Area,
    EmploymentStatus,
    EmploymentType,
    NationalityStatus,
    SkillLevel,
    Employee as DBEmployee,
    EmployeeAvailability,
    EmployeeStoreAccess,
    EmployeeSkill,
    EmployeeRelation,
    UserAreaAccess,
    UserStoreAccess,
    StoreScheduleRuleConfig,
    StoreStaffingDemand,
    ScheduleEntry,
    Role,
    RoleCode,
    Store,
    User,
    ensure_employee_month_hours,
    get_db,
    init_db_and_seed,
    roll_employee_availability_window,
)

app = FastAPI(title="SwiftFlow Backend", version="1.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 算法目录
ALGORITHMS_DIR = "algorithms"
SECRET_KEY = os.getenv("SWIFTFLOW_SECRET_KEY", "swiftflow-dev-secret-change-me")
TOKEN_EXPIRE_HOURS = int(os.getenv("SWIFTFLOW_TOKEN_EXPIRE_HOURS", "12"))

# 数据模型
class ScheduleEmployee(BaseModel):
    id: str
    name: str
    department: str = ""
    preferences: Dict[str, Any] = {}

class ScheduleRequest(BaseModel):
    employees: List[ScheduleEmployee]
    rules: Dict[str, Any]

class AlgorithmResponse(BaseModel):
    success: bool
    message: str
    schedule: Dict[str, List[Dict[str, Any]]] = {}
    error: str = ""


class StoreCreateRequest(BaseModel):
    name: str
    area_id: int | None = None
    open_time: str = "09:00"
    close_time: str = "23:00"


class StoreHoursUpdateRequest(BaseModel):
    name: str | None = None
    area_id: int | None = None
    open_time: str
    close_time: str


class StoreResponse(BaseModel):
    id: int
    name: str
    area_id: int | None = None
    open_time: str
    close_time: str


class AreaResponse(BaseModel):
    id: int
    name: str


class AreaCreateRequest(BaseModel):
    name: str


class AreaUpdateRequest(BaseModel):
    name: str


class MyScheduleStoreResponse(BaseModel):
    id: int
    name: str
    open_time: str
    close_time: str
    assigned_hours: int


class MyVisibleEmployeeResponse(BaseModel):
    id: int
    name: str
    employment_type: str


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    employee_id: int | None = None
    store_ids: List[int] = []
    area_ids: List[int] = []


class HomeSummaryResponse(BaseModel):
    role: str
    total_stores: int = 0
    total_employees: int = 0
    managed_stores: int = 0
    managed_employees: int = 0
    employee_id: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_at: str


class RegisterRequest(BaseModel):
    name: str
    phone_country_code: str
    phone_number: str
    nationality_status: NationalityStatus
    password: str
    password_confirm: str


class RegisterResponse(BaseModel):
    user_id: int
    employee_id: int
    username: str
    role: str


class MyProfileResponse(BaseModel):
    username: str
    role: str
    employee_id: int
    name: str
    phone_country_code: str
    phone_number: str
    nationality_status: NationalityStatus


class MyProfileUpdateRequest(BaseModel):
    name: str
    phone_country_code: str
    phone_number: str
    nationality_status: NationalityStatus
    password: str | None = None
    password_confirm: str | None = None


class UserStoreAccessUpdateRequest(BaseModel):
    store_ids: List[int]


class UserAreaAccessUpdateRequest(BaseModel):
    area_ids: List[int]


class UserRoleUpdateRequest(BaseModel):
    role: str
    store_ids: List[int] | None = None


class UserEmployeeBindingUpdateRequest(BaseModel):
    employee_id: int | None = None


class EmployeeAvailabilityItem(BaseModel):
    week_offset: int  # 0=本周, 1=下周
    day_of_week: int  # 0=周一, 6=周日
    start_time: str
    end_time: str


class EmployeeStoreSettingItem(BaseModel):
    store_id: int
    priority: int | None = None
    has_key: bool = False


class MyAvailabilityUpdateRequest(BaseModel):
    availabilities: List[EmployeeAvailabilityItem] = []


class EmployeeSkillItem(BaseModel):
    skill_code: str
    level: SkillLevel = SkillLevel.NONE


class EmployeeCreateRequest(BaseModel):
    name: str
    phone_country_code: str | None = None
    phone_number: str | None = None
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    employment_type: EmploymentType
    preferred_shift: str = "no_preference"
    nationality_status: NationalityStatus = NationalityStatus.OTHER
    work_skill_score: int = 50
    management_skill_score: int = 50
    store_ids: List[int] = []
    store_settings: List[EmployeeStoreSettingItem] | None = None
    skills: List[EmployeeSkillItem] = []
    availabilities: List[EmployeeAvailabilityItem] = []


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    phone_country_code: str | None = None
    phone_number: str | None = None
    employment_status: EmploymentStatus | None = None
    employment_type: EmploymentType | None = None
    preferred_shift: str | None = None
    nationality_status: NationalityStatus | None = None
    work_skill_score: int | None = None
    management_skill_score: int | None = None
    store_ids: List[int] | None = None
    store_settings: List[EmployeeStoreSettingItem] | None = None
    skills: List[EmployeeSkillItem] | None = None
    availabilities: List[EmployeeAvailabilityItem] | None = None


class EmployeeMonthHoursUpdateRequest(BaseModel):
    hours_delta: float


class EmployeeAvailabilityResponse(BaseModel):
    week_offset: int
    day_of_week: int
    start_time: str
    end_time: str


class EmployeeStoreSettingResponse(BaseModel):
    store_id: int
    priority: int | None = None
    has_key: bool


class EmployeeSkillResponse(BaseModel):
    skill_code: str
    level: str


class EmployeeResponse(BaseModel):
    id: int
    name: str
    phone_country_code: str | None = None
    phone_number: str | None = None
    employment_status: str
    employment_type: str
    preferred_shift: str
    nationality_status: str
    work_skill_score: int
    management_skill_score: int
    monthly_worked_hours: float
    hours_month: str
    store_ids: List[int]
    store_settings: List[EmployeeStoreSettingResponse]
    skills: List[EmployeeSkillResponse]
    availabilities: List[EmployeeAvailabilityResponse]
    availability_customized: bool


class EmployeeRelationCreateRequest(BaseModel):
    employee_id_a: int
    employee_id_b: int
    relation_type: str = "bad"
    severity: float


class EmployeeRelationResponse(BaseModel):
    id: int
    employee_id_a: int
    employee_id_b: int
    relation_type: str
    severity: float


class StoreRuleConfigUpdateRequest(BaseModel):
    store_id: int
    schedule_archetype: str = "auto"
    weekday_total_hours_limit: float = 40.0
    weekend_total_hours_limit: float = 45.0
    sg_part_time_min_hours: float = 80.0
    sg_part_time_target_hours: float = 160.0
    target_160_last_week_days: int = 7
    min_backroom_per_hour: int = 1
    require_opening_dual_skill: bool = True
    min_opening_keyholders: int = 1
    min_closing_keyholders: int = 1
    store_key_count: int = 0


class StoreRuleConfigResponse(BaseModel):
    store_id: int
    schedule_archetype: str
    weekday_total_hours_limit: float
    weekend_total_hours_limit: float
    sg_part_time_min_hours: float
    sg_part_time_target_hours: float
    target_160_last_week_days: int
    min_backroom_per_hour: int
    require_opening_dual_skill: bool
    min_opening_keyholders: int
    min_closing_keyholders: int
    store_key_count: int


class StoreStaffingDemandItem(BaseModel):
    day_of_week: int | None = None
    day_type: str | None = None  # weekday | weekend
    hour: int
    min_staff: int


class StoreStaffingDemandProfileItem(BaseModel):
    day_type: str  # weekday | weekend
    hour: int
    min_staff: int


class StoreStaffingDemandUpdateRequest(BaseModel):
    store_id: int
    items: List[StoreStaffingDemandItem] = []
    profiles: List[StoreStaffingDemandProfileItem] = []


class StoreStaffingDemandResponse(BaseModel):
    store_id: int
    items: List[StoreStaffingDemandItem]
    profiles: List[StoreStaffingDemandProfileItem] = []


class ScheduleItem(BaseModel):
    date: str  # YYYY-MM-DD
    hour: int  # dynamic store hour
    employee_id: int


class ScheduleAnomalyReason(BaseModel):
    code: str
    label: str
    detail: str


class ScheduleAnomalyItem(BaseModel):
    date: str
    hour: int
    kind: str
    required: int
    assigned: int
    reasons: List[ScheduleAnomalyReason] = []


class ScheduleReplaceRequest(BaseModel):
    store_id: int
    week_start: str  # YYYY-MM-DD, Monday
    items: List[ScheduleItem] = []


class ScheduleResponse(BaseModel):
    store_id: int
    week_start: str
    items: List[ScheduleItem]
    anomalies: List[ScheduleAnomalyItem] = []


class ScheduleRepairSlot(BaseModel):
    date: str  # YYYY-MM-DD
    hour: int


class ScheduleRepairRequest(BaseModel):
    store_id: int
    week_start: str  # YYYY-MM-DD, Monday
    slots: List[ScheduleRepairSlot] = []
    algorithm: str = "default_schedule"


class ScheduleRepairResponse(BaseModel):
    success: bool
    message: str
    store_id: int
    week_start: str
    affected_dates: List[str]
    requested_slots: int
    assignments_removed: int
    assignments_added: int
    unresolved_slots: int
    unresolved_details: List[ScheduleAnomalyItem] = []


class GenerateAllSchedulesRequest(BaseModel):
    week_start: str  # YYYY-MM-DD Monday
    algorithm: str = "default_schedule"
    cycle_days: int = 7


class GenerateStoreScheduleRequest(BaseModel):
    store_id: int
    week_start: str  # YYYY-MM-DD Monday
    algorithm: str = "default_schedule"
    cycle_days: int = 7


class StoreGenerationResult(BaseModel):
    store_id: int
    store_name: str
    employees_considered: int
    assignments_saved: int
    assignments_skipped_conflict: int


class GenerateAllSchedulesResponse(BaseModel):
    success: bool
    message: str
    week_start: str
    results: List[StoreGenerationResult]


class GenerateStoreScheduleResponse(BaseModel):
    success: bool
    message: str
    week_start: str
    result: StoreGenerationResult

# 创建算法目录（如果不存在）
os.makedirs(ALGORITHMS_DIR, exist_ok=True)


@app.on_event("startup")
def startup_event():
    init_db_and_seed()

def load_algorithm(algorithm_name: str):
    """安全加载算法模块。"""
    if not algorithm_name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid algorithm name")
    
    algorithm_path = os.path.join(ALGORITHMS_DIR, f"{algorithm_name}.py")
    if not os.path.exists(algorithm_path):
        raise FileNotFoundError(f"Algorithm '{algorithm_name}' not found")
    
    spec = importlib.util.spec_from_file_location(algorithm_name, algorithm_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # 验证必需函数
    if not hasattr(module, 'generate_schedule'):
        raise AttributeError(f"Algorithm '{algorithm_name}' missing generate_schedule function")
    
    return module


def parse_time_str(time_text: str) -> time:
    try:
        if str(time_text).strip() == "24:00":
            return time(hour=23, minute=59)
        hours, minutes = time_text.split(":")
        return time(hour=int(hours), minute=int(minutes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"时间格式错误: {time_text}，请使用 HH:MM") from exc


def parse_date_str(date_text: str) -> date:
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {date_text}，请使用 YYYY-MM-DD") from exc


def week_range(week_start_text: str) -> tuple[date, date]:
    start_date = parse_date_str(week_start_text)
    if start_date.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start 必须是周一")
    end_date = start_date + timedelta(days=6)
    return start_date, end_date


def hour_bounds_for_store(store: Store) -> tuple[int, int]:
    start_hour = store.open_time.hour + (1 if store.open_time.minute > 0 else 0)
    end_hour = store.close_time.hour if store.close_time.minute > 0 else store.close_time.hour - 1
    safe_start = max(0, min(start_hour, 23))
    safe_end = max(safe_start, min(end_hour, 23))
    return safe_start, safe_end


def resolve_hour_from_assignment(assignment: dict, default_hour: int) -> int:
    raw_hour = assignment.get("hour")
    if isinstance(raw_hour, (int, float)):
        return int(raw_hour)
    shift = str(assignment.get("shift", "")).strip().lower()
    shift_map = {
        "早班": 9,
        "中班": 13,
        "晚班": 18,
        "morning": 9,
        "afternoon": 13,
        "evening": 18,
        "night": 18,
    }
    return int(shift_map.get(shift, default_hour))


def build_external_schedule_context(
    rows: list[ScheduleEntry],
    *,
    exclude_store_id: int | None = None,
) -> tuple[set[tuple[int, date, int]], dict[int, set[str]], dict[int, dict[str, int]]]:
    occupied_slots: set[tuple[int, date, int]] = set()
    external_store_days: dict[int, set[str]] = {}
    external_daily_hours: dict[int, dict[str, int]] = {}

    for row in rows:
        if exclude_store_id is not None and row.store_id == exclude_store_id:
            continue
        occupied_slots.add((row.employee_id, row.work_date, row.hour))
        date_key = row.work_date.strftime("%Y-%m-%d")
        external_store_days.setdefault(row.employee_id, set()).add(date_key)
        external_daily_hours.setdefault(row.employee_id, {})
        external_daily_hours[row.employee_id][date_key] = external_daily_hours[row.employee_id].get(date_key, 0) + 1

    return occupied_slots, external_store_days, external_daily_hours


def prune_short_store_blocks(
    pending_entries: list[ScheduleEntry],
    *,
    minimum_block_hours: int = 3,
) -> tuple[list[ScheduleEntry], int]:
    if minimum_block_hours <= 1 or not pending_entries:
        return pending_entries, 0

    grouped_entries: dict[tuple[int, int, date], list[ScheduleEntry]] = defaultdict(list)
    for entry in pending_entries:
        grouped_entries[(int(entry.store_id), int(entry.employee_id), entry.work_date)].append(entry)

    kept_entries: list[ScheduleEntry] = []
    removed_entries = 0

    for _, entries in grouped_entries.items():
        ordered = sorted(entries, key=lambda item: int(item.hour))
        current_block: list[ScheduleEntry] = []

        for entry in ordered:
            if not current_block or int(entry.hour) == int(current_block[-1].hour) + 1:
                current_block.append(entry)
                continue

            if len(current_block) >= minimum_block_hours:
                kept_entries.extend(current_block)
            else:
                removed_entries += len(current_block)
            current_block = [entry]

        if current_block:
            if len(current_block) >= minimum_block_hours:
                kept_entries.extend(current_block)
            else:
                removed_entries += len(current_block)

    kept_entries.sort(key=lambda item: (item.work_date, int(item.store_id), int(item.employee_id), int(item.hour)))
    return kept_entries, removed_entries


def prune_short_schedule_entries_in_db(
    db: Session,
    *,
    store_ids: list[int],
    start_date: date,
    end_date: date,
    minimum_block_hours: int = 3,
) -> int:
    if minimum_block_hours <= 1 or not store_ids:
        return 0

    rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id.in_(store_ids),
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .order_by(ScheduleEntry.store_id, ScheduleEntry.employee_id, ScheduleEntry.work_date, ScheduleEntry.hour)
        .all()
    )
    if not rows:
        return 0

    grouped_rows: dict[tuple[int, int, date], list[ScheduleEntry]] = defaultdict(list)
    for row in rows:
        grouped_rows[(int(row.store_id), int(row.employee_id), row.work_date)].append(row)

    removed = 0
    for group_rows in grouped_rows.values():
        current_block: list[ScheduleEntry] = []
        for row in group_rows:
            if not current_block or int(row.hour) == int(current_block[-1].hour) + 1:
                current_block.append(row)
                continue

            if len(current_block) < minimum_block_hours:
                for item in current_block:
                    db.delete(item)
                removed += len(current_block)
            current_block = [row]

        if current_block and len(current_block) < minimum_block_hours:
            for item in current_block:
                db.delete(item)
            removed += len(current_block)

    return removed


def build_demand_by_day_hour(rows: list[StoreStaffingDemand]) -> dict[str, dict[str, int]]:
    demand_by_day_hour: dict[str, dict[str, int]] = {}
    for row in rows:
        day_key = str(int(row.day_of_week))
        if day_key not in demand_by_day_hour:
            demand_by_day_hour[day_key] = {}
        demand_by_day_hour[day_key][str(int(row.hour))] = int(row.min_staff)
    return demand_by_day_hour


def build_bad_relations(db: Session) -> list[dict[str, Any]]:
    relation_rows = db.query(EmployeeRelation).all()
    return [
        {
            "employee_id_a": row.employee_id_a,
            "employee_id_b": row.employee_id_b,
            "relation_type": row.relation_type,
            "severity": float(row.severity),
        }
        for row in relation_rows
        if row.relation_type == "bad"
    ]


def current_month_progress(today: date | None = None) -> tuple[int, int]:
    base_day = today or date.today()
    month_start = base_day.replace(day=1)
    if base_day.month == 12:
        next_month_start = date(base_day.year + 1, 1, 1)
    else:
        next_month_start = date(base_day.year, base_day.month + 1, 1)
    month_days = (next_month_start - month_start).days
    days_left_in_month = (next_month_start - base_day).days
    return month_days, days_left_in_month


def build_local_repair_windows(
    target_slots: set[tuple[str, int]],
    min_hour: int,
    max_hour: int,
    *,
    padding_hours: int = 1,
    minimum_span_hours: int = 4,
) -> dict[str, list[tuple[int, int]]]:
    windows_by_date: dict[str, list[tuple[int, int]]] = {}
    grouped_hours: dict[str, list[int]] = {}
    for date_text, hour in sorted(target_slots):
        grouped_hours.setdefault(date_text, []).append(int(hour))

    for date_text, hours in grouped_hours.items():
        unique_hours = sorted(set(hours))
        clusters: list[list[int]] = []
        for hour in unique_hours:
            if not clusters or hour > clusters[-1][-1] + 1:
                clusters.append([hour])
            else:
                clusters[-1].append(hour)

        expanded_windows: list[tuple[int, int]] = []
        for cluster in clusters:
            start_hour = max(min_hour, cluster[0] - padding_hours)
            end_hour = min(max_hour, cluster[-1] + padding_hours)
            while end_hour - start_hour + 1 < minimum_span_hours:
                can_expand_left = start_hour > min_hour
                can_expand_right = end_hour < max_hour
                if not can_expand_left and not can_expand_right:
                    break
                if can_expand_left:
                    start_hour -= 1
                if end_hour - start_hour + 1 >= minimum_span_hours:
                    break
                if can_expand_right:
                    end_hour += 1
            expanded_windows.append((start_hour, end_hour))

        merged_windows: list[tuple[int, int]] = []
        for start_hour, end_hour in expanded_windows:
            if not merged_windows or start_hour > merged_windows[-1][1] + 1:
                merged_windows.append((start_hour, end_hour))
            else:
                merged_start, merged_end = merged_windows[-1]
                merged_windows[-1] = (merged_start, max(merged_end, end_hour))
        windows_by_date[date_text] = merged_windows

    return windows_by_date


def _availability_week_offset(anchor_monday: date, target_date: date) -> int:
    day_delta = (target_date - anchor_monday).days
    if day_delta < 0:
        return -1
    if day_delta < 7:
        return 0
    if day_delta < 14:
        return 1
    return 2


def _db_employee_available_at(employee: DBEmployee, target_date: date, hour: int) -> bool:
    week_offset = _availability_week_offset(employee.availability_anchor_monday, target_date)
    if week_offset not in {0, 1}:
        return False
    day_of_week = target_date.weekday()
    for row in get_effective_employee_availability_rows(employee):
        if row.week_offset != week_offset or row.day_of_week != day_of_week:
            continue
        start_hour = row.start_time.hour + (1 if row.start_time.minute > 0 else 0)
        end_hour = row.end_time.hour if row.end_time.minute > 0 else row.end_time.hour - 1
        if start_hour <= hour <= end_hour:
            return True
    return False


def _default_availability_rows_for_employee(employee: DBEmployee):
    if employee.employment_type != EmploymentType.FULL_TIME:
        return []
    return [
        SimpleNamespace(
            week_offset=week_offset,
            day_of_week=day_of_week,
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        for week_offset in (0, 1)
        for day_of_week in range(7)
    ]


def get_effective_employee_availability_rows(employee: DBEmployee):
    availability_rows = [row for row in employee.availabilities if row.week_offset in (0, 1)]
    if availability_rows or getattr(employee, "availability_customized", False):
        return availability_rows
    return _default_availability_rows_for_employee(employee)


def build_employee_availability_response_rows(employee: DBEmployee) -> list[EmployeeAvailabilityResponse]:
    actual_rows = {
        (int(row.week_offset), int(row.day_of_week)): row
        for row in employee.availabilities
        if row.week_offset in (0, 1)
    }
    if getattr(employee, "availability_customized", False):
        base_rows = [
            EmployeeAvailabilityResponse(
                week_offset=week_offset,
                day_of_week=day_of_week,
                start_time="",
                end_time="",
            )
            for week_offset in (0, 1)
            for day_of_week in range(7)
        ]
    else:
        base_rows = [
            EmployeeAvailabilityResponse(
                week_offset=int(row.week_offset),
                day_of_week=int(row.day_of_week),
                start_time=row.start_time.strftime("%H:%M"),
                end_time=row.end_time.strftime("%H:%M"),
            )
            for row in _default_availability_rows_for_employee(employee)
        ]

    merged_rows: list[EmployeeAvailabilityResponse] = []
    for row in base_rows:
        actual = actual_rows.get((row.week_offset, row.day_of_week))
        if actual is None:
            merged_rows.append(row)
            continue
        merged_rows.append(
            EmployeeAvailabilityResponse(
                week_offset=row.week_offset,
                day_of_week=row.day_of_week,
                start_time=actual.start_time.strftime("%H:%M"),
                end_time=actual.end_time.strftime("%H:%M"),
            )
        )
    return merged_rows


def format_availability_time_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return value.strftime("%H:%M")


def _slot_skill_codes(hour: int, opening_hour: int, closing_hour: int) -> tuple[str, ...]:
    if hour <= opening_hour + 1:
        return ("backroom", "inventory", "cashier")
    if hour >= closing_hour - 1:
        return ("cashier", "customer_service", "inventory")
    return ("cashier", "floor", "customer_service")


def _employee_has_slot_skill(employee: DBEmployee, hour: int, opening_hour: int, closing_hour: int) -> bool:
    employee_skills = {
        str(skill.skill_code).lower(): str(skill.level.value).lower()
        for skill in employee.skills
    }

    def has_any(codes: tuple[str, ...] | set[str]) -> bool:
        return any(employee_skills.get(code) in {"basic", "proficient"} for code in codes)

    if hour <= opening_hour + 1:
        has_front = has_any(("front_service", "cashier", "floor", "customer_service"))
        has_back = has_any(("backroom", "inventory"))
        return (has_front and has_back) or int(employee.work_skill_score or 0) >= 85

    relevant_skills = set(_slot_skill_codes(hour, opening_hour, closing_hour))
    if any(employee_skills.get(code) in {"basic", "proficient"} for code in relevant_skills):
        return True
    return int(employee.work_skill_score or 0) >= 70


def _reason_item(code: str, label: str, detail: str) -> ScheduleAnomalyReason:
    return ScheduleAnomalyReason(code=code, label=label, detail=detail)


def analyze_schedule_anomalies(
    *,
    store: Store,
    start_date: date,
    end_date: date,
    current_rows: list[ScheduleEntry],
    external_rows: list[ScheduleEntry],
    employee_rows: list[DBEmployee],
    demand_by_day_hour: dict[str, dict[str, int]],
    bad_relations: list[dict[str, Any]],
    target_slots: set[tuple[str, int]] | None = None,
    include_local_repair_reason: bool = False,
) -> list[ScheduleAnomalyItem]:
    opening_hour, closing_hour = hour_bounds_for_store(store)
    assigned_by_slot: dict[tuple[str, int], list[int]] = {}
    daily_hours_by_employee: dict[tuple[int, str], int] = {}
    external_hours_by_employee: dict[tuple[int, str], int] = {}
    external_conflicts = {
        (row.employee_id, row.work_date.strftime("%Y-%m-%d"), int(row.hour))
        for row in external_rows
    }
    relation_map: dict[tuple[int, int], float] = {}

    for relation in bad_relations:
        try:
            a = int(relation.get("employee_id_a"))
            b = int(relation.get("employee_id_b"))
            severity = float(relation.get("severity", 0.0))
        except Exception:
            continue
        relation_map[(a, b)] = severity
        relation_map[(b, a)] = severity

    for row in current_rows:
        date_key = row.work_date.strftime("%Y-%m-%d")
        assigned_by_slot.setdefault((date_key, int(row.hour)), []).append(int(row.employee_id))
        daily_hours_by_employee[(int(row.employee_id), date_key)] = (
            daily_hours_by_employee.get((int(row.employee_id), date_key), 0) + 1
        )

    for row in external_rows:
        date_key = row.work_date.strftime("%Y-%m-%d")
        external_hours_by_employee[(int(row.employee_id), date_key)] = (
            external_hours_by_employee.get((int(row.employee_id), date_key), 0) + 1
        )

    anomalies: list[ScheduleAnomalyItem] = []
    day_count = (end_date - start_date).days + 1
    for day_index in range(max(0, day_count)):
        work_date = start_date + timedelta(days=day_index)
        date_key = work_date.strftime("%Y-%m-%d")
        weekday_key = str(work_date.weekday())
        day_demands = demand_by_day_hour.get(weekday_key, {})
        candidate_hours = sorted(
            {
                int(hour_text)
                for hour_text, min_staff in day_demands.items()
                if int(min_staff or 0) > 0 and opening_hour <= int(hour_text) <= closing_hour
            }
        )
        for hour in candidate_hours:
            if target_slots is not None and (date_key, hour) not in target_slots:
                continue
            required = int(day_demands.get(str(hour), 0))
            assigned_employee_ids = sorted(assigned_by_slot.get((date_key, hour), []))
            assigned = len(assigned_employee_ids)
            if assigned >= required:
                continue

            available_candidates = 0
            cross_store_candidates = 0
            hour_limit_candidates = 0
            relation_block_candidates = 0
            skill_block_candidates = 0
            feasible_candidates = 0

            for employee in employee_rows:
                employee_id = int(employee.id)
                if not _db_employee_available_at(employee, work_date, hour):
                    continue
                available_candidates += 1

                if (employee_id, date_key, hour) in external_conflicts:
                    cross_store_candidates += 1
                    continue

                total_hours_for_day = (
                    daily_hours_by_employee.get((employee_id, date_key), 0)
                    + external_hours_by_employee.get((employee_id, date_key), 0)
                )
                already_assigned_here = employee_id in assigned_employee_ids
                if total_hours_for_day >= 12 and not already_assigned_here:
                    hour_limit_candidates += 1
                    continue

                severe_conflict = False
                for assigned_employee_id in assigned_employee_ids:
                    if assigned_employee_id == employee_id:
                        severe_conflict = False
                        break
                    if relation_map.get((employee_id, assigned_employee_id), 0.0) >= 0.85:
                        severe_conflict = True
                        break
                if severe_conflict:
                    relation_block_candidates += 1
                    continue

                if not _employee_has_slot_skill(employee, hour, opening_hour, closing_hour):
                    skill_block_candidates += 1
                    continue

                feasible_candidates += 1

            reasons: list[ScheduleAnomalyReason] = []
            if available_candidates == 0:
                reasons.append(
                    _reason_item("no_availability", "无人可用", "该时段没有任何授权员工提供可上班时间。")
                )
            else:
                if cross_store_candidates > 0:
                    reasons.append(
                        _reason_item(
                            "cross_store_conflict",
                            "跨店冲突",
                            f"有 {cross_store_candidates} 名可用员工在该时段已被其他门店占用。",
                        )
                    )
                if hour_limit_candidates > 0:
                    reasons.append(
                        _reason_item(
                            "hour_limit",
                            "工时限制",
                            f"有 {hour_limit_candidates} 名可用员工已达到当日工时上限。",
                        )
                    )
                if relation_block_candidates > 0:
                    reasons.append(
                        _reason_item(
                            "relation_conflict",
                            "关系冲突",
                            f"有 {relation_block_candidates} 名可用员工与当前在岗人员存在高冲突约束。",
                        )
                    )
                if skill_block_candidates > 0:
                    reasons.append(
                        _reason_item(
                            "skill_shortage",
                            "技能不足",
                            f"有 {skill_block_candidates} 名可用员工未满足该时段的优先技能要求。",
                        )
                    )
                if feasible_candidates > 0:
                    reasons.append(
                        _reason_item(
                            "local_repair_failed" if include_local_repair_reason else "algorithm_gap",
                            "局部修复失败" if include_local_repair_reason else "算法未补齐",
                            f"仍有 {feasible_candidates} 名候选员工具备补排条件，但当前结果未完成覆盖。",
                        )
                    )
            if not reasons:
                reasons.append(
                    _reason_item("unknown", "原因待确认", "当前缺口未匹配到明确原因，请进一步检查规则配置。")
                )

            anomalies.append(
                ScheduleAnomalyItem(
                    date=date_key,
                    hour=hour,
                    kind="empty" if assigned == 0 else "shortage",
                    required=required,
                    assigned=assigned,
                    reasons=reasons,
                )
            )

    anomalies.sort(key=lambda item: (item.date, item.hour))
    return anomalies


def build_store_generation_payload(
    *,
    db: Session,
    store: Store,
    config_response: "StoreRuleConfigResponse",
    store_links: list[EmployeeStoreAccess],
    employee_rows: list[DBEmployee],
    occupied_slots: set[tuple[int, date, int]],
    external_store_days: dict[int, set[str]],
    external_daily_hours: dict[int, dict[str, int]],
    bad_relations: list[dict[str, Any]],
    demand_by_day_hour: dict[str, dict[str, int]],
    algorithm_name: str,
    cycle_days: int,
    week_start: str,
    min_hour: int,
    max_hour: int,
    month_days: int,
    days_left_in_month: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    employees_dict = []
    for employee in employee_rows:
        normalize_employee_state(db, employee)
        is_sg_pt = (
            employee.employment_type == EmploymentType.PART_TIME
            and employee.nationality_status in {NationalityStatus.SG_CITIZEN, NationalityStatus.SG_PR}
        )
        remaining_to_160 = max(
            0.0, config_response.sg_part_time_target_hours - float(employee.monthly_worked_hours)
        )
        availability_rows = get_effective_employee_availability_rows(employee)
        remaining_capacity_hours = 0.0
        for row in availability_rows:
            remaining_capacity_hours += max(
                0.0,
                (row.end_time.hour + row.end_time.minute / 60)
                - (row.start_time.hour + row.start_time.minute / 60),
            )
        can_push_to_160 = True
        if (
            days_left_in_month <= config_response.target_160_last_week_days
            and remaining_to_160 > remaining_capacity_hours
        ):
            can_push_to_160 = False

        blocked_slots = [
            f"{slot_date.strftime('%Y-%m-%d')}|{slot_hour}"
            for (slot_emp, slot_date, slot_hour) in occupied_slots
            if slot_emp == employee.id
        ]
        employee_external_store_days = sorted(external_store_days.get(employee.id, set()))
        employee_external_daily_hours = dict(external_daily_hours.get(employee.id, {}))
        backroom_skill = next(
            (skill for skill in employee.skills if skill.skill_code == "backroom"),
            None,
        )
        skill_levels = {
            str(skill.skill_code): str(skill.level.value)
            for skill in employee.skills
        }
        employees_dict.append(
            {
                "id": str(employee.id),
                "name": employee.name,
                "department": "",
                "preferences": {
                    "preferred_shift": str(employee.preferred_shift or "no_preference"),
                },
                "meta": {
                    "employment_type": employee.employment_type.value,
                    "preferred_shift": str(employee.preferred_shift or "no_preference"),
                    "nationality_status": employee.nationality_status.value,
                    "monthly_worked_hours": float(employee.monthly_worked_hours),
                    "work_skill_score": int(employee.work_skill_score),
                    "management_skill_score": int(employee.management_skill_score),
                    "is_sg_part_time": is_sg_pt,
                    "sg_priority_to_80": bool(
                        is_sg_pt and employee.monthly_worked_hours < config_response.sg_part_time_min_hours
                    ),
                    "sg_priority_to_160": bool(
                        is_sg_pt
                        and can_push_to_160
                        and employee.monthly_worked_hours < config_response.sg_part_time_target_hours
                    ),
                    "days_left_in_month": days_left_in_month,
                    "month_days": month_days,
                    "availability_anchor_monday": employee.availability_anchor_monday.strftime("%Y-%m-%d"),
                    "availability_windows": [
                        {
                            "week_offset": row.week_offset,
                            "day_of_week": row.day_of_week,
                            "start_time": row.start_time.strftime("%H:%M"),
                            "end_time": row.end_time.strftime("%H:%M"),
                        }
                        for row in availability_rows
                    ],
                    "backroom_level": (
                        backroom_skill.level.value if backroom_skill is not None else SkillLevel.NONE.value
                    ),
                    "skill_levels": skill_levels,
                    "blocked_slots": blocked_slots,
                    "external_store_days": employee_external_store_days,
                    "external_daily_hours": employee_external_daily_hours,
                },
            }
        )

    store_rules = {
        "algorithm": algorithm_name,
        "store_id": store.id,
        "store_archetype": config_response.schedule_archetype,
        "cycle_days": cycle_days,
        "start_date": week_start,
        "weekday_total_hours_limit": config_response.weekday_total_hours_limit,
        "weekend_total_hours_limit": config_response.weekend_total_hours_limit,
        "sg_part_time_min_hours": config_response.sg_part_time_min_hours,
        "sg_part_time_target_hours": config_response.sg_part_time_target_hours,
        "target_160_last_week_days": config_response.target_160_last_week_days,
        "min_backroom_per_hour": config_response.min_backroom_per_hour,
        "require_opening_dual_skill": config_response.require_opening_dual_skill,
        "min_opening_keyholders": config_response.min_opening_keyholders,
        "min_closing_keyholders": config_response.min_closing_keyholders,
        "store_key_count": config_response.store_key_count,
        "store_hour_start": min_hour,
        "store_hour_end": max_hour,
        "store_key_holder_employee_ids": [link.employee_id for link in store_links if bool(link.has_key)],
        "store_employee_priority": {
            str(link.employee_id): link.priority
            for link in store_links
            if link.priority is not None
        },
        "bad_relations": bad_relations,
        "demand_by_day_hour": demand_by_day_hour,
    }
    return employees_dict, store_rules


def can_manage_store(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def can_update_store_hours(role_code: RoleCode) -> bool:
    return can_edit_store_profile(role_code)


def can_manage_employee(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN}


def can_edit_employee_availability(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER, RoleCode.STAFF}


def can_edit_employee_name(role_code: RoleCode) -> bool:
    return role_code == RoleCode.SUPER_ADMIN


def is_admin_role(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def is_platform_admin_role(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def is_area_manager_role(role_code: RoleCode) -> bool:
    return role_code == RoleCode.AREA_MANAGER


def is_store_manager_role(role_code: RoleCode) -> bool:
    return role_code == RoleCode.STORE_MANAGER


def is_staff_role(role_code: RoleCode) -> bool:
    return role_code == RoleCode.STAFF


def is_developer_role(role_code: RoleCode) -> bool:
    return role_code == RoleCode.DEVELOPER


def can_view_operations_workspace(role_code: RoleCode) -> bool:
    return role_code in {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.AREA_MANAGER,
        RoleCode.STORE_MANAGER,
    }


def can_edit_schedule(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def can_generate_schedule(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def can_manage_user_roles(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def can_assign_store_manager(role_code: RoleCode) -> bool:
    return role_code == RoleCode.AREA_MANAGER


def can_reset_other_user_password(role_code: RoleCode) -> bool:
    return role_code in {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.AREA_MANAGER,
        RoleCode.STORE_MANAGER,
    }


def can_edit_store_profile(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.AREA_MANAGER}


def can_edit_store_area(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def can_edit_store_rules(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def can_edit_staffing_demand(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def can_edit_employee_profile(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def can_edit_employee_admin_fields(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


def can_edit_own_availability(role_code: RoleCode) -> bool:
    return role_code == RoleCode.STAFF


def can_edit_own_profile(role_code: RoleCode) -> bool:
    return role_code in {RoleCode.STAFF, RoleCode.AREA_MANAGER, RoleCode.STORE_MANAGER}


def get_authorized_area_ids(db: Session, user: User) -> set[int]:
    if is_platform_admin_role(user.role.code):
        rows = db.query(Area.id).all()
        return {row[0] for row in rows}
    rows = db.query(UserAreaAccess.area_id).filter(UserAreaAccess.user_id == user.id).all()
    return {row[0] for row in rows}


def validate_store_ids_exist(db: Session, store_ids: list[int]) -> list[int]:
    normalized = sorted(set(int(store_id) for store_id in store_ids))
    if not normalized:
        return []
    found = db.query(Store.id).filter(Store.id.in_(normalized)).all()
    found_ids = {item[0] for item in found}
    missing = [sid for sid in normalized if sid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"店铺不存在: {missing}")
    return normalized


def ensure_store_ids_in_scope(db: Session, current_user: User, store_ids: list[int]) -> list[int]:
    normalized = validate_store_ids_exist(db, store_ids)
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    out_of_scope = [sid for sid in normalized if sid not in authorized_store_ids]
    if out_of_scope:
        raise HTTPException(status_code=403, detail=f"当前角色无权操作这些店铺: {out_of_scope}")
    return normalized


def validate_area_id_exists(db: Session, area_id: int | None) -> int | None:
    if area_id is None:
        return None
    area = db.query(Area.id).filter(Area.id == area_id).first()
    if area is None:
        raise HTTPException(status_code=400, detail=f"区域不存在: {area_id}")
    return int(area_id)


def role_from_value(role_value: str) -> RoleCode:
    try:
        return RoleCode(str(role_value).strip().lower())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无效角色: {role_value}") from exc


def get_role_row(db: Session, role_code: RoleCode):
    role = db.query(Role).filter(Role.code == role_code).first()
    if role is None:
        raise HTTPException(status_code=500, detail=f"角色不存在: {role_code.value}")
    return role


SUPPORTED_PHONE_CODES = {"+65", "+60"}


def normalize_phone_identity(phone_country_code: str, phone_number: str) -> tuple[str, str, str]:
    country_code = str(phone_country_code or "").strip()
    digits = re.sub(r"\D", "", str(phone_number or ""))
    if country_code not in SUPPORTED_PHONE_CODES:
        raise HTTPException(status_code=400, detail="目前仅支持 +65 和 +60 手机号注册")
    if not digits:
        raise HTTPException(status_code=400, detail="请输入有效手机号")
    digits = digits.lstrip("0") or digits
    if len(digits) < 7 or len(digits) > 12:
        raise HTTPException(status_code=400, detail="手机号长度不正确")
    return country_code, digits, f"{country_code}{digits}"


def normalize_employee_phone(phone_country_code: str | None, phone_number: str | None) -> tuple[str | None, str | None]:
    has_country_code = bool(str(phone_country_code or "").strip())
    has_phone_number = bool(str(phone_number or "").strip())
    if not has_country_code and not has_phone_number:
        return None, None
    if has_country_code != has_phone_number:
        raise HTTPException(status_code=400, detail="手机号区号和号码需要同时填写")
    country_code, digits, _ = normalize_phone_identity(str(phone_country_code), str(phone_number))
    return country_code, digits


def get_authorized_store_ids(db: Session, user: User) -> set[int]:
    if is_platform_admin_role(user.role.code):
        stores = db.query(Store.id).all()
        return {row[0] for row in stores}
    if is_area_manager_role(user.role.code):
        area_ids = get_authorized_area_ids(db, user)
        if not area_ids:
            return set()
        stores = db.query(Store.id).filter(Store.area_id.in_(area_ids)).all()
        return {row[0] for row in stores}
    rows = db.query(UserStoreAccess.store_id).filter(UserStoreAccess.user_id == user.id).all()
    return {row[0] for row in rows}


def get_employee_query_in_scope(db: Session, user: User):
    if is_platform_admin_role(user.role.code):
        return db.query(DBEmployee)
    authorized_store_ids = get_authorized_store_ids(db, user)
    include_unassigned = is_area_manager_role(user.role.code) or is_store_manager_role(user.role.code)
    if not authorized_store_ids:
        if include_unassigned:
            if user.employee_id:
                return db.query(DBEmployee).outerjoin(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id).filter(
                    or_(EmployeeStoreAccess.employee_id.is_(None), DBEmployee.id == user.employee_id)
                ).distinct()
            return db.query(DBEmployee).outerjoin(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id).filter(
                EmployeeStoreAccess.employee_id.is_(None)
            ).distinct()
        if user.employee_id:
            return db.query(DBEmployee).filter(DBEmployee.id == user.employee_id)
        return db.query(DBEmployee).filter(DBEmployee.id == -1)
    query = (
        db.query(DBEmployee)
        .outerjoin(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
        .filter(
            or_(
                EmployeeStoreAccess.store_id.in_(authorized_store_ids),
                EmployeeStoreAccess.employee_id.is_(None) if include_unassigned else DBEmployee.id == -1,
                DBEmployee.id == user.employee_id if user.employee_id else DBEmployee.id == -1,
            )
        )
        .distinct()
    )
    return query


def manager_can_access_employee(db: Session, user: User, employee_id: int) -> bool:
    if is_platform_admin_role(user.role.code):
        return True
    if user.employee_id and int(user.employee_id) == int(employee_id):
        return True
    if is_area_manager_role(user.role.code) or is_store_manager_role(user.role.code):
        has_store_link = (
            db.query(EmployeeStoreAccess.employee_id)
            .filter(EmployeeStoreAccess.employee_id == employee_id)
            .first()
        )
        if has_store_link is None:
            return True
    authorized_store_ids = get_authorized_store_ids(db, user)
    if not authorized_store_ids:
        return False
    row = (
        db.query(EmployeeStoreAccess.employee_id)
        .filter(
            EmployeeStoreAccess.employee_id == employee_id,
            EmployeeStoreAccess.store_id.in_(authorized_store_ids),
        )
        .first()
    )
    return row is not None


def get_bound_employee_or_403(db: Session, user: User) -> DBEmployee:
    if not user.employee_id:
        raise HTTPException(status_code=403, detail="当前账号尚未绑定员工档案")
    employee = db.query(DBEmployee).filter(DBEmployee.id == user.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail=f"员工不存在: {user.employee_id}")
    normalize_employee_state(db, employee)
    return employee


def get_staff_visible_store_ids_for_week(
    db: Session,
    user: User,
    start_date: date,
    end_date: date,
) -> set[int]:
    if not is_staff_role(user.role.code):
        return get_authorized_store_ids(db, user)
    if not user.employee_id:
        return set()
    rows = (
        db.query(ScheduleEntry.store_id)
        .filter(
            ScheduleEntry.employee_id == user.employee_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .distinct()
        .all()
    )
    return {int(row[0]) for row in rows}


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user: User) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user.username,
        "role": user.role.code.value,
        "exp": int(expires_at.timestamp()),
    }
    payload_part = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    sign_part = _b64_encode(hmac.new(SECRET_KEY.encode(), payload_part.encode(), hashlib.sha256).digest())
    token = f"{payload_part}.{sign_part}"
    return token, expires_at


def decode_access_token(token: str) -> dict:
    try:
        payload_part, sign_part = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="token 格式错误") from exc

    expected_sign = _b64_encode(hmac.new(SECRET_KEY.encode(), payload_part.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sign_part, expected_sign):
        raise HTTPException(status_code=401, detail="token 签名无效")

    try:
        payload = json.loads(_b64_decode(payload_part).decode())
    except Exception as exc:
        raise HTTPException(status_code=401, detail="token 载荷无效") from exc

    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="token 已过期")
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="token 缺少用户信息")
    return payload


def get_user_from_token(authorization: str, db: Session) -> User | None:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization 头格式应为 Bearer <token>")
    token = authorization[7:].strip()
    payload = decode_access_token(token)
    username = payload["sub"]
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="token 对应用户不存在或已禁用")
    return user


def get_current_user(
    authorization: str = Header(default="", alias="Authorization"),
    x_user: str = Header(default="", alias="X-User"),
    db: Session = Depends(get_db),
) -> User:
    token_user = get_user_from_token(authorization, db)
    if token_user is not None:
        return token_user

    if not x_user:
        raise HTTPException(
            status_code=401,
            detail="缺少认证信息，请先登录",
        )
    user = db.query(User).filter(User.username == x_user).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail=f"用户不存在或被禁用: {x_user}")
    return user


def store_to_response(store: Store) -> StoreResponse:
    return StoreResponse(
        id=store.id,
        name=store.name,
        area_id=store.area_id,
        open_time=store.open_time.strftime("%H:%M"),
        close_time=store.close_time.strftime("%H:%M"),
    )


def normalize_employee_state(db: Session, employee: DBEmployee):
    roll_employee_availability_window(db, employee)
    ensure_employee_month_hours(employee)


def validate_availability_item(item: EmployeeAvailabilityItem):
    if item.week_offset not in (0, 1):
        raise HTTPException(status_code=400, detail="week_offset 仅支持 0(本周) 或 1(下周)")
    if item.day_of_week < 0 or item.day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week 必须在 0-6")
    if not item.start_time and not item.end_time:
        return None, None
    if not item.start_time or not item.end_time:
        raise HTTPException(status_code=400, detail="Availability must have both start and end time, or neither")
    start = parse_time_str(item.start_time)
    end = parse_time_str(item.end_time)
    if start >= end:
        raise HTTPException(status_code=400, detail="可用时间 start_time 必须早于 end_time")
    return start, end


def has_non_empty_availability(items: List[EmployeeAvailabilityItem]) -> bool:
    return any(item.start_time and item.end_time for item in items)


def sync_employee_availabilities(db: Session, employee: DBEmployee, items: List[EmployeeAvailabilityItem]):
    for row in list(employee.availabilities):
        db.delete(row)
    db.flush()
    employee.availability_customized = True
    for item in items:
        start, end = validate_availability_item(item)
        if start is None or end is None:
            continue
        db.add(
            EmployeeAvailability(
                employee_id=employee.id,
                week_offset=item.week_offset,
                day_of_week=item.day_of_week,
                start_time=start,
                end_time=end,
            )
        )


def reset_employee_default_availabilities(db: Session, employee: DBEmployee):
    for row in list(employee.availabilities):
        db.delete(row)
    db.flush()
    employee.availability_customized = False


def sync_employee_store_links(db: Session, employee: DBEmployee, store_ids: List[int]):
    uniq_store_ids = sorted(set(store_ids))
    if uniq_store_ids:
        found = db.query(Store.id).filter(Store.id.in_(uniq_store_ids)).all()
        found_ids = {item[0] for item in found}
        missing = [sid for sid in uniq_store_ids if sid not in found_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"店铺不存在: {missing}")

    for row in list(employee.store_links):
        db.delete(row)
    for store_id in uniq_store_ids:
        db.add(EmployeeStoreAccess(employee_id=employee.id, store_id=store_id))


def ensure_employee_store_links(db: Session, employee_id: int | None, store_ids: List[int] | set[int]):
    if not employee_id:
        return
    uniq_store_ids = sorted({int(store_id) for store_id in store_ids if store_id is not None})
    if not uniq_store_ids:
        return
    existing_store_ids = {
        int(row[0])
        for row in db.query(EmployeeStoreAccess.store_id)
        .filter(EmployeeStoreAccess.employee_id == employee_id)
        .all()
    }
    missing_store_ids = [store_id for store_id in uniq_store_ids if store_id not in existing_store_ids]
    for store_id in missing_store_ids:
        db.add(EmployeeStoreAccess(employee_id=employee_id, store_id=store_id))


def sync_employee_store_settings(db: Session, employee: DBEmployee, settings: List[EmployeeStoreSettingItem]):
    uniq_store_ids = sorted({item.store_id for item in settings})
    if uniq_store_ids:
        found = db.query(Store.id).filter(Store.id.in_(uniq_store_ids)).all()
        found_ids = {item[0] for item in found}
        missing = [sid for sid in uniq_store_ids if sid not in found_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"Store not found: {missing}")

    for row in list(employee.store_links):
        db.delete(row)
    for item in settings:
        priority = item.priority
        if priority is not None and priority < 1:
            raise HTTPException(status_code=400, detail="Store priority must be >= 1")
        db.add(
            EmployeeStoreAccess(
                employee_id=employee.id,
                store_id=item.store_id,
                priority=priority,
                has_key=bool(item.has_key),
            )
        )


def sync_employee_skills(db: Session, employee: DBEmployee, skills: List[EmployeeSkillItem]):
    for row in db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee.id).all():
        db.delete(row)
    db.flush()

    deduped_skills: dict[str, EmployeeSkillItem] = {}
    for item in skills:
        skill_code = item.skill_code.strip().lower()
        if not skill_code:
            raise HTTPException(status_code=400, detail="skill_code cannot be empty")
        deduped_skills[skill_code] = item

    for skill_code, item in deduped_skills.items():
        db.add(
            EmployeeSkill(
                employee_id=employee.id,
                skill_code=skill_code,
                level=item.level,
            )
        )


def score_in_range(value: int, field: str) -> int:
    if value < 0 or value > 100:
        raise HTTPException(status_code=400, detail=f"{field} must be between 0 and 100")
    return value


def relation_to_ordered_pair(a: int, b: int) -> tuple[int, int]:
    if a == b:
        raise HTTPException(status_code=400, detail="Relation employees cannot be same person")
    return (a, b) if a < b else (b, a)


def validate_relation_payload(request: EmployeeRelationCreateRequest):
    if request.severity < 0 or request.severity > 1:
        raise HTTPException(status_code=400, detail="severity must be in [0, 1]")
    if not request.relation_type.strip():
        raise HTTPException(status_code=400, detail="relation_type is required")


def default_store_rule_config(store_id: int) -> StoreRuleConfigResponse:
    return StoreRuleConfigResponse(
        store_id=store_id,
        schedule_archetype="auto",
        weekday_total_hours_limit=40.0,
        weekend_total_hours_limit=45.0,
        sg_part_time_min_hours=80.0,
        sg_part_time_target_hours=160.0,
        target_160_last_week_days=7,
        min_backroom_per_hour=1,
        require_opening_dual_skill=True,
        min_opening_keyholders=1,
        min_closing_keyholders=1,
        store_key_count=0,
    )


def store_rule_config_to_response(config: StoreScheduleRuleConfig | None, store_id: int) -> StoreRuleConfigResponse:
    if config is None:
        return default_store_rule_config(store_id)
    return StoreRuleConfigResponse(
        store_id=config.store_id,
        schedule_archetype=str(getattr(config, "schedule_archetype", "auto") or "auto"),
        weekday_total_hours_limit=float(config.weekday_total_hours_limit),
        weekend_total_hours_limit=float(config.weekend_total_hours_limit),
        sg_part_time_min_hours=float(config.sg_part_time_min_hours),
        sg_part_time_target_hours=float(config.sg_part_time_target_hours),
        target_160_last_week_days=int(config.target_160_last_week_days),
        min_backroom_per_hour=int(getattr(config, "min_backroom_per_hour", 1) or 1),
        require_opening_dual_skill=bool(getattr(config, "require_opening_dual_skill", True)),
        min_opening_keyholders=int(getattr(config, "min_opening_keyholders", 1) or 0),
        min_closing_keyholders=int(getattr(config, "min_closing_keyholders", 1) or 0),
        store_key_count=int(getattr(config, "store_key_count", 0) or 0),
    )


def staffing_demands_to_response(store_id: int, rows: List[StoreStaffingDemand]) -> StoreStaffingDemandResponse:
    items = [
        StoreStaffingDemandItem(
            day_of_week=int(row.day_of_week),
            hour=int(row.hour),
            min_staff=int(row.min_staff),
        )
        for row in sorted(rows, key=lambda x: (x.day_of_week, x.hour))
    ]
    profile_map: dict[tuple[str, int], List[int]] = {}
    for row in rows:
        day_type = "weekday" if int(row.day_of_week) <= 4 else "weekend"
        key = (day_type, int(row.hour))
        if key not in profile_map:
            profile_map[key] = []
        profile_map[key].append(int(row.min_staff))
    profiles = [
        StoreStaffingDemandProfileItem(
            day_type=day_type,
            hour=hour,
            min_staff=max(values) if values else 0,
        )
        for (day_type, hour), values in sorted(profile_map.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    return StoreStaffingDemandResponse(store_id=store_id, items=items, profiles=profiles)


def employee_to_response(employee: DBEmployee) -> EmployeeResponse:
    availabilities = build_employee_availability_response_rows(employee)
    store_settings = sorted(
        employee.store_links,
        key=lambda x: (x.priority is None, x.priority or 999999, x.store_id),
    )
    return EmployeeResponse(
        id=employee.id,
        name=employee.name,
        phone_country_code=employee.phone_country_code,
        phone_number=employee.phone_number,
        employment_status=employee.employment_status.value,
        employment_type=employee.employment_type.value,
        preferred_shift=str(employee.preferred_shift or "no_preference"),
        nationality_status=employee.nationality_status.value,
        work_skill_score=int(employee.work_skill_score),
        management_skill_score=int(employee.management_skill_score),
        monthly_worked_hours=round(employee.monthly_worked_hours, 2),
        hours_month=employee.hours_month,
        store_ids=sorted({link.store_id for link in employee.store_links}),
        store_settings=[
            EmployeeStoreSettingResponse(
                store_id=item.store_id,
                priority=item.priority,
                has_key=bool(item.has_key),
            )
            for item in store_settings
        ],
        skills=[
            EmployeeSkillResponse(
                skill_code=item.skill_code,
                level=item.level.value,
            )
            for item in sorted(employee.skills, key=lambda x: x.skill_code)
        ],
        availabilities=[
            EmployeeAvailabilityResponse(
                week_offset=item.week_offset,
                day_of_week=item.day_of_week,
                start_time=format_availability_time_value(item.start_time),
                end_time=format_availability_time_value(item.end_time),
            )
            for item in availabilities
        ],
        availability_customized=bool(getattr(employee, "availability_customized", False)),
    )

@app.get("/api")
def read_root():
    return {"message": "SwiftFlow Backend is running!"}


@app.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == str(request.username or "").strip()).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not hmac.compare_digest(user.password_hash or "", request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token, expires_at = create_access_token(user)
    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role.code.value,
        expires_at=expires_at.isoformat(),
    )


@app.post("/api/register", response_model=RegisterResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    name = str(request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请输入姓名")
    if request.password != request.password_confirm:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")
    if len(str(request.password or "")) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少需要 6 位")

    country_code, digits, username = normalize_phone_identity(
        request.phone_country_code,
        request.phone_number,
    )
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    staff_role = get_role_row(db, RoleCode.STAFF)

    employee = DBEmployee(
        name=name,
        phone_country_code=country_code,
        phone_number=digits,
        employment_status=EmploymentStatus.ACTIVE,
        employment_type=EmploymentType.PART_TIME,
        preferred_shift="no_preference",
        nationality_status=request.nationality_status,
        work_skill_score=50,
        management_skill_score=50,
    )
    ensure_employee_month_hours(employee)
    db.add(employee)
    db.flush()

    user = User(
        username=username,
        full_name=name,
        password_hash=request.password,
        is_active=True,
        role_id=staff_role.id,
        employee_id=employee.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterResponse(
        user_id=user.id,
        employee_id=employee.id,
        username=user.username,
        role=user.role.code.value,
    )


@app.get("/api/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if can_manage_user_roles(current_user.role.code):
        users = db.query(User).all()
    elif can_reset_other_user_password(current_user.role.code):
        visible_employee_ids = {
            employee.id for employee in get_employee_query_in_scope(db, current_user).all()
        }
        if current_user.employee_id:
            visible_employee_ids.add(int(current_user.employee_id))
        users = db.query(User).filter(
            or_(
                User.id == current_user.id,
                User.employee_id.in_(visible_employee_ids) if visible_employee_ids else User.id == -1,
            )
        ).all()
    else:
        raise HTTPException(status_code=403, detail="当前角色没有查看用户列表权限")
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role.code.value,
            employee_id=user.employee_id,
            store_ids=sorted({link.store_id for link in user.store_links}),
            area_ids=sorted({link.area_id for link in user.area_links}),
        )
        for user in users
    ]


@app.get("/api/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.code.value,
        employee_id=current_user.employee_id,
        store_ids=sorted({link.store_id for link in current_user.store_links}),
        area_ids=sorted({link.area_id for link in current_user.area_links}),
    )


@app.get("/api/me/profile", response_model=MyProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_own_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有个人资料入口")
    employee = get_bound_employee_or_403(db, current_user)
    return my_profile_to_response(current_user, employee)


@app.put("/api/me/profile", response_model=MyProfileResponse)
def update_my_profile(
    request: MyProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_own_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有修改个人资料权限")

    employee = get_bound_employee_or_403(db, current_user)
    name = str(request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请输入姓名")

    country_code, digits, username = normalize_phone_identity(
        request.phone_country_code,
        request.phone_number,
    )
    existing_user = db.query(User).filter(User.username == username, User.id != current_user.id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    password = str(request.password or "")
    password_confirm = str(request.password_confirm or "")
    if password or password_confirm:
        if password != password_confirm:
            raise HTTPException(status_code=400, detail="两次输入的密码不一致")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码长度至少需要 6 位")
        current_user.password_hash = hash_password(password)

    employee.name = name
    employee.phone_country_code = country_code
    employee.phone_number = digits
    employee.nationality_status = request.nationality_status
    current_user.username = username
    current_user.full_name = name

    db.commit()
    db.refresh(current_user)
    db.refresh(employee)
    return my_profile_to_response(current_user, employee)


@app.get("/api/stores", response_model=List[StoreResponse])
def list_stores(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if not authorized_store_ids:
        return []
    stores = (
        db.query(Store)
        .filter(Store.id.in_(authorized_store_ids))
        .order_by(Store.id.asc())
        .all()
    )
    return [store_to_response(item) for item in stores]


@app.get("/api/areas", response_model=List[AreaResponse])
def list_areas(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if is_platform_admin_role(current_user.role.code):
        areas = db.query(Area).order_by(Area.name.asc(), Area.id.asc()).all()
    elif is_area_manager_role(current_user.role.code):
        authorized_area_ids = get_authorized_area_ids(db, current_user)
        if not authorized_area_ids:
            return []
        areas = (
            db.query(Area)
            .filter(Area.id.in_(authorized_area_ids))
            .order_by(Area.name.asc(), Area.id.asc())
            .all()
        )
    else:
        raise HTTPException(status_code=403, detail="当前角色没有查看区域权限")

    return [AreaResponse(id=item.id, name=item.name) for item in areas]


@app.post("/api/areas", response_model=AreaResponse)
def create_area(
    request: AreaCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_store(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有新增区域权限")

    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="区域名称不能为空")

    exists = db.query(Area).filter(func.lower(Area.name) == name.lower()).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"区域已存在: {name}")

    area = Area(name=name)
    db.add(area)
    db.commit()
    db.refresh(area)
    return AreaResponse(id=area.id, name=area.name)


@app.put("/api/areas/{area_id}", response_model=AreaResponse)
def update_area(
    area_id: int,
    request: AreaUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_store(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有修改区域权限")

    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail=f"区域不存在: {area_id}")

    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="区域名称不能为空")

    exists = (
        db.query(Area)
        .filter(func.lower(Area.name) == name.lower(), Area.id != area_id)
        .first()
    )


def my_profile_to_response(user: User, employee: DBEmployee) -> MyProfileResponse:
    return MyProfileResponse(
        username=user.username,
        role=user.role.code.value,
        employee_id=employee.id,
        name=employee.name,
        phone_country_code=str(employee.phone_country_code or ""),
        phone_number=str(employee.phone_number or ""),
        nationality_status=employee.nationality_status,
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"区域已存在: {name}")

    area.name = name
    db.commit()
    db.refresh(area)
    return AreaResponse(id=area.id, name=area.name)


@app.delete("/api/areas/{area_id}")
def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_store(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有删除区域权限")

    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail=f"区域不存在: {area_id}")

    db.query(Store).filter(Store.area_id == area_id).update({Store.area_id: None})
    db.delete(area)
    db.commit()
    return {"message": "区域已删除，原区域门店已转为未分配区域"}


@app.post("/api/stores", response_model=StoreResponse)
def create_store(
    request: StoreCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_store(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有新增店铺权限")

    exists = db.query(Store).filter(Store.name == request.name).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"店铺已存在: {request.name}")

    open_time = parse_time_str(request.open_time)
    close_time = parse_time_str(request.close_time)
    area_id = validate_area_id_exists(db, request.area_id)
    store = Store(name=request.name, area_id=area_id, open_time=open_time, close_time=close_time)
    db.add(store)
    db.commit()
    db.refresh(store)
    return store_to_response(store)


@app.put("/api/stores/{store_id}/hours", response_model=StoreResponse)
def update_store_hours(
    store_id: int,
    request: StoreHoursUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_store_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有修改营业时间权限")

    if not is_platform_admin_role(current_user.role.code):
        authorized_store_ids = get_authorized_store_ids(db, current_user)
        if store_id not in authorized_store_ids:
            raise HTTPException(status_code=403, detail="当前角色无权修改该店铺营业时间")

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail=f"店铺不存在: {store_id}")

    if is_platform_admin_role(current_user.role.code):
        if current_user.role.code == RoleCode.ADMIN:
            if request.name is not None and str(request.name).strip() and str(request.name).strip() != store.name:
                raise HTTPException(status_code=403, detail="当前角色无权修改店铺名称")

            next_area_id = validate_area_id_exists(db, request.area_id)
            store.area_id = next_area_id
            store.open_time = parse_time_str(request.open_time)
            store.close_time = parse_time_str(request.close_time)
        else:
            next_name = str(request.name or "").strip()
            if not next_name:
                raise HTTPException(status_code=400, detail="店铺名称不能为空")
            exists = db.query(Store).filter(Store.name == next_name, Store.id != store_id).first()
            if exists:
                raise HTTPException(status_code=409, detail=f"店铺已存在: {next_name}")
            store.name = next_name
    else:
        if request.name is not None and str(request.name).strip() and str(request.name).strip() != store.name:
            raise HTTPException(status_code=403, detail="当前角色无权修改店铺名称")

        next_area_id = validate_area_id_exists(db, request.area_id)
        if next_area_id != store.area_id and not can_edit_store_area(current_user.role.code):
            raise HTTPException(status_code=403, detail="当前角色无权修改店铺所属区域")
        if is_area_manager_role(current_user.role.code) and next_area_id != store.area_id:
            authorized_area_ids = get_authorized_area_ids(db, current_user)
            if next_area_id not in authorized_area_ids:
                raise HTTPException(status_code=403, detail="当前角色无权将门店调整到该区域")

        store.area_id = next_area_id
        store.open_time = parse_time_str(request.open_time)
        store.close_time = parse_time_str(request.close_time)

    db.commit()
    db.refresh(store)
    return store_to_response(store)


@app.delete("/api/stores/{store_id}")
def delete_store(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_store(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有删除店铺权限")

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail=f"店铺不存在: {store_id}")

    db.delete(store)
    db.commit()
    return {"success": True, "message": f"店铺已删除: {store.name}"}


@app.put("/api/users/{user_id}/store-access")
def update_user_store_access(
    user_id: int,
    request: UserStoreAccessUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_user_roles(current_user.role.code) and not can_assign_store_manager(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有设置店铺授权权限")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
    if target.role.code != RoleCode.STORE_MANAGER:
        raise HTTPException(status_code=400, detail="仅支持给 STORE_MANAGER 分配店铺授权")

    if can_assign_store_manager(current_user.role.code) and not can_manage_user_roles(current_user.role.code):
        store_ids = ensure_store_ids_in_scope(db, current_user, request.store_ids)
    else:
        store_ids = validate_store_ids_exist(db, request.store_ids)

    for link in list(target.store_links):
        db.delete(link)
    for store_id in store_ids:
        db.add(UserStoreAccess(user_id=target.id, store_id=store_id))
    ensure_employee_store_links(db, target.employee_id, store_ids)
    db.commit()
    return {"success": True, "user_id": user_id, "store_ids": store_ids}


@app.put("/api/users/{user_id}/area-access")
def update_user_area_access(
    user_id: int,
    request: UserAreaAccessUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_user_roles(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有设置区域授权权限")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
    if target.role.code != RoleCode.AREA_MANAGER:
        raise HTTPException(status_code=400, detail="仅支持给 AREA_MANAGER 分配区域授权")

    area_ids = []
    if request.area_ids:
        areas = db.query(Area.id).filter(Area.id.in_(request.area_ids)).all()
        found_ids = sorted({row[0] for row in areas})
        missing_ids = sorted(set(request.area_ids) - set(found_ids))
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"区域不存在: {missing_ids}")
        area_ids = found_ids

    for link in list(target.area_links):
        db.delete(link)
    for area_id in area_ids:
        db.add(UserAreaAccess(user_id=target.id, area_id=area_id))
    area_store_ids = []
    if area_ids:
        area_store_ids = [int(row[0]) for row in db.query(Store.id).filter(Store.area_id.in_(area_ids)).all()]
    ensure_employee_store_links(db, target.employee_id, area_store_ids)
    db.commit()
    return {"success": True, "user_id": user_id, "area_ids": area_ids}


@app.put("/api/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    request: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")

    next_role_code = role_from_value(request.role)

    if can_manage_user_roles(current_user.role.code):
        if target.id == current_user.id and next_role_code not in {RoleCode.ADMIN, RoleCode.SUPER_ADMIN}:
            raise HTTPException(status_code=400, detail="不能将当前登录管理员降为非管理员角色")
    elif can_assign_store_manager(current_user.role.code):
        if next_role_code not in {RoleCode.STORE_MANAGER, RoleCode.STAFF}:
            raise HTTPException(status_code=403, detail="区域经理仅可将用户设为店长或员工")
        target_store_ids = ensure_store_ids_in_scope(db, current_user, request.store_ids or [])
        if next_role_code == RoleCode.STORE_MANAGER and not target_store_ids:
            raise HTTPException(status_code=400, detail="设置店长时必须同时分配至少一个区域内门店")
    else:
        raise HTTPException(status_code=403, detail="当前角色没有修改用户角色权限")

    role_row = get_role_row(db, next_role_code)
    target.role_id = role_row.id

    if next_role_code == RoleCode.STORE_MANAGER:
        store_ids = (
            ensure_store_ids_in_scope(db, current_user, request.store_ids or [])
            if can_assign_store_manager(current_user.role.code) and not can_manage_user_roles(current_user.role.code)
            else validate_store_ids_exist(db, request.store_ids or [])
        )
        for link in list(target.store_links):
            db.delete(link)
        for store_id in store_ids:
            db.add(UserStoreAccess(user_id=target.id, store_id=store_id))
        ensure_employee_store_links(db, target.employee_id, store_ids)
    elif request.store_ids is not None:
        for link in list(target.store_links):
            db.delete(link)

    db.commit()
    db.refresh(target)
    return UserResponse(
        id=target.id,
        username=target.username,
        full_name=target.full_name,
        role=target.role.code.value,
        employee_id=target.employee_id,
        store_ids=sorted({link.store_id for link in target.store_links}),
        area_ids=sorted({link.area_id for link in target.area_links}),
    )


@app.put("/api/users/{user_id}/employee-binding", response_model=UserResponse)
def update_user_employee_binding(
    user_id: int,
    request: UserEmployeeBindingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_user_roles(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有绑定员工档案权限")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")

    if request.employee_id is None:
        target.employee_id = None
    else:
        employee = db.query(DBEmployee).filter(DBEmployee.id == request.employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail=f"员工不存在: {request.employee_id}")
        binding_conflict = (
            db.query(User.id)
            .filter(User.employee_id == employee.id, User.id != user_id)
            .first()
        )
        if binding_conflict:
            raise HTTPException(status_code=409, detail="该员工档案已绑定其他账号")
        target.employee_id = employee.id
        if target.role.code == RoleCode.STORE_MANAGER:
            ensure_employee_store_links(
                db,
                target.employee_id,
                [int(link.store_id) for link in target.store_links],
            )
        elif target.role.code == RoleCode.AREA_MANAGER:
            area_ids = [int(link.area_id) for link in target.area_links]
            area_store_ids = (
                [int(row[0]) for row in db.query(Store.id).filter(Store.area_id.in_(area_ids)).all()]
                if area_ids
                else []
            )
            ensure_employee_store_links(db, target.employee_id, area_store_ids)

    db.commit()
    db.refresh(target)
    return UserResponse(
        id=target.id,
        username=target.username,
        full_name=target.full_name,
        role=target.role.code.value,
        employee_id=target.employee_id,
        store_ids=sorted({link.store_id for link in target.store_links}),
        area_ids=sorted({link.area_id for link in target.area_links}),
    )


@app.put("/api/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_reset_other_user_password(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有重置密码权限")

    if int(user_id) == int(current_user.id):
        raise HTTPException(status_code=400, detail="不能重置当前登录账号自己的密码")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")

    if not is_platform_admin_role(current_user.role.code):
        if not target.employee_id or not manager_can_access_employee(db, current_user, int(target.employee_id)):
            raise HTTPException(status_code=403, detail="当前角色无权重置该账号密码")

    target.password_hash = "Qwerty1234"
    db.commit()
    return {"message": "密码已重置为默认密码 Qwerty1234"}


@app.get("/api/home-summary", response_model=HomeSummaryResponse)
def home_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if is_platform_admin_role(current_user.role.code):
        return HomeSummaryResponse(
            role=current_user.role.code.value,
            total_stores=db.query(func.count(Store.id)).scalar() or 0,
            total_employees=db.query(func.count(DBEmployee.id)).scalar() or 0,
            employee_id=current_user.employee_id,
        )

    authorized_store_ids = get_authorized_store_ids(db, current_user)
    managed_store_count = len(authorized_store_ids)
    if not authorized_store_ids:
        return HomeSummaryResponse(
            role=current_user.role.code.value,
            managed_stores=0,
            managed_employees=0,
            employee_id=current_user.employee_id,
        )

    managed_employee_count = (
        db.query(func.count(distinct(EmployeeStoreAccess.employee_id)))
        .filter(EmployeeStoreAccess.store_id.in_(authorized_store_ids))
        .scalar()
        or 0
    )
    return HomeSummaryResponse(
        role=current_user.role.code.value,
        managed_stores=managed_store_count,
        managed_employees=managed_employee_count,
        employee_id=current_user.employee_id,
    )


@app.get("/api/me/employee", response_model=EmployeeResponse)
def get_my_employee_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = get_bound_employee_or_403(db, current_user)
    db.commit()
    db.refresh(employee)
    return employee_to_response(employee)


@app.put("/api/me/availability", response_model=EmployeeResponse)
def update_my_availability(
    request: MyAvailabilityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_own_availability(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有修改个人可排时间权限")
    employee = get_bound_employee_or_403(db, current_user)
    sync_employee_availabilities(db, employee, request.availabilities)
    db.commit()
    db.refresh(employee)
    return employee_to_response(employee)


@app.get("/api/me/schedule-stores", response_model=List[MyScheduleStoreResponse])
def list_my_schedule_stores(
    week_start: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date, end_date = week_range(week_start)
    store_ids = get_staff_visible_store_ids_for_week(db, current_user, start_date, end_date)
    if not store_ids:
        return []

    stores = (
        db.query(Store)
        .filter(Store.id.in_(store_ids))
        .order_by(Store.name.asc(), Store.id.asc())
        .all()
    )
    assigned_hours_rows = (
        db.query(ScheduleEntry.store_id, func.count(ScheduleEntry.id))
        .filter(
            ScheduleEntry.employee_id == current_user.employee_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
            ScheduleEntry.store_id.in_(store_ids),
        )
        .group_by(ScheduleEntry.store_id)
        .all()
    )
    assigned_hours_map = {int(row[0]): int(row[1]) for row in assigned_hours_rows}
    return [
        MyScheduleStoreResponse(
            id=store.id,
            name=store.name,
            open_time=store.open_time.strftime("%H:%M"),
            close_time=store.close_time.strftime("%H:%M"),
            assigned_hours=assigned_hours_map.get(store.id, 0),
        )
        for store in stores
    ]


@app.get("/api/me/store-employees", response_model=List[MyVisibleEmployeeResponse])
def list_my_visible_store_employees(
    store_id: int,
    week_start: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date, end_date = week_range(week_start)
    visible_store_ids = get_staff_visible_store_ids_for_week(db, current_user, start_date, end_date)
    if store_id not in visible_store_ids:
        raise HTTPException(status_code=403, detail="当前角色无权查看该店铺员工名单")

    employee_ids_rows = (
        db.query(ScheduleEntry.employee_id)
        .filter(
            ScheduleEntry.store_id == store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .distinct()
        .all()
    )
    employee_ids = [int(row[0]) for row in employee_ids_rows]
    if not employee_ids:
        return []
    employees = (
        db.query(DBEmployee)
        .filter(DBEmployee.id.in_(employee_ids))
        .order_by(DBEmployee.name.asc(), DBEmployee.id.asc())
        .all()
    )
    return [
        MyVisibleEmployeeResponse(
            id=employee.id,
            name=employee.name,
            employment_type=employee.employment_type.value,
        )
        for employee in employees
    ]


@app.get("/api/schedules", response_model=ScheduleResponse)
def get_schedule(
    store_id: int,
    week_start: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date, end_date = week_range(week_start)
    authorized_store_ids = get_staff_visible_store_ids_for_week(db, current_user, start_date, end_date)
    store = db.query(Store).filter(Store.id == store_id).first()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    if store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="当前角色无权访问该店铺排班")

    rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id == store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .order_by(ScheduleEntry.work_date.asc(), ScheduleEntry.hour.asc(), ScheduleEntry.employee_id.asc())
        .all()
    )
    items = [
        ScheduleItem(
            date=row.work_date.strftime("%Y-%m-%d"),
            hour=row.hour,
            employee_id=row.employee_id,
        )
        for row in rows
    ]
    external_rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id != store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .all()
    )
    demand_rows = (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store_id)
        .all()
    )
    employee_rows = (
        db.query(DBEmployee)
        .join(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
        .filter(
            EmployeeStoreAccess.store_id == store_id,
            DBEmployee.employment_status == EmploymentStatus.ACTIVE,
        )
        .distinct()
        .all()
    )
    for employee in employee_rows:
        normalize_employee_state(db, employee)
    anomalies = analyze_schedule_anomalies(
        store=store,
        start_date=start_date,
        end_date=end_date,
        current_rows=rows,
        external_rows=external_rows,
        employee_rows=employee_rows,
        demand_by_day_hour=build_demand_by_day_hour(demand_rows),
        bad_relations=build_bad_relations(db),
    )
    return ScheduleResponse(store_id=store_id, week_start=week_start, items=items, anomalies=anomalies)


@app.put("/api/schedules", response_model=ScheduleResponse)
def replace_schedule(
    request: ScheduleReplaceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date, end_date = week_range(request.week_start)
    if not can_edit_schedule(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有编辑排班权限")
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if request.store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="?????????????")

    store = db.query(Store).filter(Store.id == request.store_id).first()
    if store is None:
        raise HTTPException(status_code=404, detail="?????")
    min_hour, max_hour = hour_bounds_for_store(store)

    visible_employee_ids = {emp.id for emp in get_employee_query_in_scope(db, current_user).all()}
    employee_hours_by_day: dict[tuple[str, int], set[int]] = {}
    for item in request.items:
        work_date = parse_date_str(item.date)
        if work_date < start_date or work_date > end_date:
            raise HTTPException(status_code=400, detail=f"??????????: {item.date}")
        if item.hour < min_hour or item.hour > max_hour:
            raise HTTPException(status_code=400, detail=f"?????????????({min_hour}-{max_hour}): {item.hour}")
        if item.employee_id not in visible_employee_ids:
            raise HTTPException(status_code=403, detail=f"?????????: {item.employee_id}")
        key = (item.date, item.employee_id)
        if key not in employee_hours_by_day:
            employee_hours_by_day[key] = set()
        employee_hours_by_day[key].add(item.hour)

    for (work_date, employee_id), hours_set in employee_hours_by_day.items():
        sorted_hours = sorted(hours_set)
        if not sorted_hours:
            continue
        expected_span = sorted_hours[-1] - sorted_hours[0] + 1
        if expected_span != len(sorted_hours):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Employee {employee_id} has split shifts on {work_date}. "
                    "One continuous work block per day is required."
                ),
            )

    requested_slots = {
        (item.employee_id, parse_date_str(item.date), item.hour)
        for item in request.items
    }
    if requested_slots:
        employee_ids = {slot[0] for slot in requested_slots}
        dates = {slot[1] for slot in requested_slots}
        hours = {slot[2] for slot in requested_slots}
        conflict_rows = (
            db.query(ScheduleEntry)
            .filter(
                ScheduleEntry.store_id != request.store_id,
                ScheduleEntry.employee_id.in_(employee_ids),
                ScheduleEntry.work_date.in_(dates),
                ScheduleEntry.hour.in_(hours),
            )
            .all()
        )
        conflict = next(
            (
                row
                for row in conflict_rows
                if (row.employee_id, row.work_date, row.hour) in requested_slots
            ),
            None,
        )
        if conflict is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Employee {conflict.employee_id} has cross-store conflict at "
                    f"{conflict.work_date.strftime('%Y-%m-%d')} {conflict.hour}:00"
                ),
            )

    (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id == request.store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .delete(synchronize_session=False)
    )

    for item in request.items:
        db.add(
            ScheduleEntry(
                store_id=request.store_id,
                employee_id=item.employee_id,
                work_date=parse_date_str(item.date),
                hour=item.hour,
            )
        )
    db.commit()
    return request


@app.post("/api/schedules/repair", response_model=ScheduleRepairResponse)
def repair_schedule_anomalies(
    request: ScheduleRepairRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date, end_date = week_range(request.week_start)
    if not can_edit_schedule(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有修复排班权限")
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if request.store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission to repair this store schedule")

    target_slots = {
        (item.date, int(item.hour))
        for item in request.slots
    }
    if not target_slots:
        raise HTTPException(status_code=400, detail="No anomaly slots provided for repair")

    store = db.query(Store).filter(Store.id == request.store_id).first()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    min_hour, max_hour = hour_bounds_for_store(store)

    affected_dates_set: set[date] = set()
    for date_text, hour in target_slots:
        work_date = parse_date_str(date_text)
        if work_date < start_date or work_date > end_date:
            raise HTTPException(status_code=400, detail=f"Repair slot outside requested week: {date_text}")
        if hour < min_hour or hour > max_hour:
            raise HTTPException(
                status_code=400,
                detail=f"Repair slot hour out of store bounds ({min_hour}-{max_hour}): {hour}",
            )
        affected_dates_set.add(work_date)

    affected_dates = sorted(affected_dates_set)
    affected_date_keys = {work_date.strftime("%Y-%m-%d") for work_date in affected_dates}
    repair_windows = build_local_repair_windows(target_slots, min_hour, max_hour)

    current_store_rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id == request.store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .all()
    )
    locked_store_rows = [row for row in current_store_rows if row.work_date not in affected_dates_set]
    assigned_count_by_slot: dict[tuple[str, int], int] = {}
    for row in current_store_rows:
        slot_key = (row.work_date.strftime("%Y-%m-%d"), int(row.hour))
        assigned_count_by_slot[slot_key] = assigned_count_by_slot.get(slot_key, 0) + 1

    external_rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id != request.store_id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .all()
    )
    occupied_slots, external_store_days, external_daily_hours = build_external_schedule_context(
        [*external_rows, *current_store_rows]
    )

    config = (
        db.query(StoreScheduleRuleConfig)
        .filter(StoreScheduleRuleConfig.store_id == store.id)
        .first()
    )
    config_response = store_rule_config_to_response(config, store.id)
    store_links = (
        db.query(EmployeeStoreAccess)
        .filter(EmployeeStoreAccess.store_id == store.id)
        .all()
    )
    demand_rows = (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store.id)
        .all()
    )
    demand_by_day_hour = build_demand_by_day_hour(demand_rows)
    bad_relations = build_bad_relations(db)
    month_days, days_left_in_month = current_month_progress()

    employee_rows = (
        db.query(DBEmployee)
        .join(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
        .filter(
            EmployeeStoreAccess.store_id == store.id,
            DBEmployee.employment_status == EmploymentStatus.ACTIVE,
        )
        .distinct()
        .all()
    )
    algorithm_module = load_algorithm(request.algorithm)
    employee_id_set = {employee.id for employee in employee_rows}
    repaired_entries: List[ScheduleEntry] = []
    repaired_date_keys: set[str] = set()
    def run_repair_pass(windows_by_date: dict[str, list[tuple[int, int]]], *, block_hours: int) -> None:
        for date_text, windows in windows_by_date.items():
            if date_text not in affected_date_keys:
                continue
            work_date = parse_date_str(date_text)
            weekday_key = str(work_date.weekday())

            for window_start, window_end in windows:
                window_demand: dict[str, dict[str, int]] = {weekday_key: {}}
                shortage_found = False
                for hour in range(window_start, window_end + 1):
                    required = int(demand_by_day_hour.get(weekday_key, {}).get(str(hour), 0))
                    assigned = int(assigned_count_by_slot.get((date_text, hour), 0))
                    residual_shortage = max(0, required - assigned)
                    window_demand[weekday_key][str(hour)] = residual_shortage
                    if residual_shortage > 0:
                        shortage_found = True

                if not shortage_found:
                    continue

                repair_employees, repair_rules = build_store_generation_payload(
                    db=db,
                    store=store,
                    config_response=config_response,
                    store_links=store_links,
                    employee_rows=employee_rows,
                    occupied_slots=occupied_slots,
                    external_store_days=external_store_days,
                    external_daily_hours=external_daily_hours,
                    bad_relations=bad_relations,
                    demand_by_day_hour=window_demand,
                    algorithm_name=request.algorithm,
                    cycle_days=1,
                    week_start=date_text,
                    min_hour=window_start,
                    max_hour=window_end,
                    month_days=month_days,
                    days_left_in_month=days_left_in_month,
                )
                repair_rules["repair_mode"] = True
                repair_rules["allow_zero_demand_hours"] = True
                repair_rules["repair_min_block_hours"] = block_hours
                repair_rules["required_shifts_per_day"] = 0

                schedule_result = algorithm_module.generate_schedule(repair_employees, repair_rules)
                assignments = schedule_result.get(date_text, []) if isinstance(schedule_result, dict) else []
                added_in_window = 0

                for assignment in assignments:
                    try:
                        employee_id = int(assignment.get("employee_id"))
                    except Exception:
                        continue
                    if employee_id not in employee_id_set:
                        continue
                    hour = resolve_hour_from_assignment(assignment, window_start)
                    if hour < window_start or hour > window_end:
                        continue
                    slot_key = (employee_id, work_date, hour)
                    if slot_key in occupied_slots:
                        continue
                    repaired_entries.append(
                        ScheduleEntry(
                            store_id=store.id,
                            employee_id=employee_id,
                            work_date=work_date,
                            hour=hour,
                        )
                    )
                    occupied_slots.add(slot_key)
                    external_store_days.setdefault(employee_id, set()).add(date_text)
                    external_daily_hours.setdefault(employee_id, {})
                    external_daily_hours[employee_id][date_text] = external_daily_hours[employee_id].get(date_text, 0) + 1
                    assigned_count_by_slot[(date_text, hour)] = assigned_count_by_slot.get((date_text, hour), 0) + 1
                    added_in_window += 1

                if added_in_window:
                    repaired_date_keys.add(date_text)

    run_repair_pass(repair_windows, block_hours=2)

    remaining_slots = {
        (date_text, hour)
        for date_text, hour in target_slots
        if int(assigned_count_by_slot.get((date_text, hour), 0))
        < int(demand_by_day_hour.get(str(parse_date_str(date_text).weekday()), {}).get(str(hour), 0))
    }
    if remaining_slots:
        widened_windows = build_local_repair_windows(
            remaining_slots,
            min_hour,
            max_hour,
            padding_hours=3,
            minimum_span_hours=6,
        )
        run_repair_pass(widened_windows, block_hours=3)

    for entry in repaired_entries:
        db.add(entry)
    db.flush()
    prune_short_schedule_entries_in_db(
        db,
        store_ids=[request.store_id],
        start_date=start_date,
        end_date=end_date,
        minimum_block_hours=3,
    )
    db.commit()

    unresolved_slots = 0
    for date_text, hour in target_slots:
        weekday_key = str(parse_date_str(date_text).weekday())
        required = int(demand_by_day_hour.get(weekday_key, {}).get(str(hour), 0))
        assigned = int(assigned_count_by_slot.get((date_text, hour), 0))
        if assigned < required:
            unresolved_slots += 1
    unresolved_details: list[ScheduleAnomalyItem] = []
    if unresolved_slots:
        refreshed_rows = (
            db.query(ScheduleEntry)
            .filter(
                ScheduleEntry.store_id == request.store_id,
                ScheduleEntry.work_date >= start_date,
                ScheduleEntry.work_date <= end_date,
            )
            .all()
        )
        unresolved_details = analyze_schedule_anomalies(
            store=store,
            start_date=start_date,
            end_date=end_date,
            current_rows=refreshed_rows,
            external_rows=external_rows,
            employee_rows=employee_rows,
            demand_by_day_hour=demand_by_day_hour,
            bad_relations=bad_relations,
            target_slots=target_slots,
            include_local_repair_reason=True,
        )

    return ScheduleRepairResponse(
        success=True,
        message="Repaired schedule anomalies inside local windows",
        store_id=request.store_id,
        week_start=request.week_start,
        affected_dates=sorted(repaired_date_keys),
        requested_slots=len(target_slots),
        assignments_removed=0,
        assignments_added=len(repaired_entries),
        unresolved_slots=unresolved_slots,
        unresolved_details=unresolved_details,
    )


@app.get("/api/employees", response_model=List[EmployeeResponse])
def list_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if is_staff_role(current_user.role.code):
        raise HTTPException(status_code=403, detail="员工角色无权查看员工列表")
    employees = get_employee_query_in_scope(db, current_user).order_by(DBEmployee.id.asc()).all()
    for employee in employees:
        normalize_employee_state(db, employee)
    db.commit()
    for employee in employees:
        db.refresh(employee)
    return [employee_to_response(employee) for employee in employees]


@app.post("/api/employees", response_model=EmployeeResponse)
def create_employee(
    request: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_employee(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有新增员工权限")

    phone_country_code, phone_number = normalize_employee_phone(
        request.phone_country_code,
        request.phone_number,
    )
    employee = DBEmployee(
        name=request.name.strip(),
        phone_country_code=phone_country_code,
        phone_number=phone_number,
        employment_status=request.employment_status,
        employment_type=request.employment_type,
        preferred_shift=(request.preferred_shift or "no_preference").strip() or "no_preference",
        nationality_status=request.nationality_status,
        work_skill_score=score_in_range(request.work_skill_score, "work_skill_score"),
        management_skill_score=score_in_range(request.management_skill_score, "management_skill_score"),
    )
    ensure_employee_month_hours(employee)
    db.add(employee)
    db.flush()

    if request.store_settings is not None:
        sync_employee_store_settings(db, employee, request.store_settings)
    else:
        sync_employee_store_links(db, employee, request.store_ids)
    sync_employee_skills(db, employee, request.skills)
    if has_non_empty_availability(request.availabilities):
        sync_employee_availabilities(db, employee, request.availabilities)

    db.commit()
    db.refresh(employee)
    return employee_to_response(employee)


@app.put("/api/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    request: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_code = current_user.role.code
    can_manage_core_fields = can_edit_employee_profile(role_code)
    can_manage_admin_fields = can_edit_employee_admin_fields(role_code)
    can_manage_availability = can_edit_employee_availability(role_code)
    can_manage_name = can_edit_employee_name(role_code)
    if not can_manage_core_fields and not can_manage_admin_fields and not can_manage_availability:
        raise HTTPException(status_code=403, detail="No permission to update employee")

    if request.name is not None and not can_manage_name:
        raise HTTPException(status_code=403, detail="No permission to edit employee name")

    employee = db.query(DBEmployee).filter(DBEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee not found: {employee_id}")
    if not manager_can_access_employee(db, current_user, employee_id):
        raise HTTPException(status_code=403, detail="No permission for this employee")

    normalize_employee_state(db, employee)

    if not can_manage_core_fields and not can_manage_admin_fields and (
        request.name is not None
        or request.phone_country_code is not None
        or request.phone_number is not None
        or request.employment_status is not None
        or request.employment_type is not None
        or request.preferred_shift is not None
        or request.nationality_status is not None
        or request.work_skill_score is not None
        or request.management_skill_score is not None
        or request.store_ids is not None
        or request.store_settings is not None
        or request.skills is not None
    ):
        raise HTTPException(status_code=403, detail="?????????????")

    if can_manage_admin_fields and not can_manage_core_fields and (
        request.name is not None
        or request.phone_country_code is not None
        or request.phone_number is not None
        or request.preferred_shift is not None
        or request.nationality_status is not None
        or request.work_skill_score is not None
        or request.management_skill_score is not None
        or request.store_ids is not None
        or request.store_settings is not None
        or request.skills is not None
        or request.availabilities is not None
    ):
        raise HTTPException(status_code=403, detail="??????????????????")

    if request.availabilities is not None:
        if not can_manage_availability:
            raise HTTPException(status_code=403, detail="No permission to edit availability")
        sync_employee_availabilities(db, employee, request.availabilities)

    if can_manage_core_fields:
        employment_type_changed = (
            request.employment_type is not None
            and request.employment_type != employee.employment_type
        )
        if request.name is not None:
            employee.name = request.name.strip()
        if request.phone_country_code is not None or request.phone_number is not None:
            phone_country_code, phone_number = normalize_employee_phone(
                request.phone_country_code,
                request.phone_number,
            )
            employee.phone_country_code = phone_country_code
            employee.phone_number = phone_number
        if request.employment_status is not None:
            employee.employment_status = request.employment_status
        if request.employment_type is not None:
            employee.employment_type = request.employment_type
            if employment_type_changed and request.availabilities is None and not employee.availability_customized:
                reset_employee_default_availabilities(db, employee)
        if request.preferred_shift is not None:
            employee.preferred_shift = (request.preferred_shift or "no_preference").strip() or "no_preference"
        if request.nationality_status is not None:
            employee.nationality_status = request.nationality_status
        if request.work_skill_score is not None:
            employee.work_skill_score = score_in_range(request.work_skill_score, "work_skill_score")
        if request.management_skill_score is not None:
            employee.management_skill_score = score_in_range(
                request.management_skill_score, "management_skill_score"
            )
        if request.store_settings is not None:
            sync_employee_store_settings(db, employee, request.store_settings)
        elif request.store_ids is not None:
            sync_employee_store_links(db, employee, request.store_ids)
        if request.skills is not None:
            sync_employee_skills(db, employee, request.skills)
    elif can_manage_admin_fields:
        if request.employment_status is not None:
            employee.employment_status = request.employment_status
        if request.employment_type is not None:
            employee.employment_type = request.employment_type

    db.commit()
    db.refresh(employee)
    return employee_to_response(employee)


@app.post("/api/employees/{employee_id}/monthly-hours", response_model=EmployeeResponse)
def add_employee_month_hours(
    employee_id: int,
    request: EmployeeMonthHoursUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_employee_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有调整员工工时权限")
    employee = db.query(DBEmployee).filter(DBEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"员工不存在: {employee_id}")
    if not manager_can_access_employee(db, current_user, employee_id):
        raise HTTPException(status_code=403, detail="当前角色无权操作该员工")

    normalize_employee_state(db, employee)
    employee.monthly_worked_hours = max(0.0, employee.monthly_worked_hours + request.hours_delta)

    db.commit()
    db.refresh(employee)
    return employee_to_response(employee)


@app.delete("/api/employees/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_employee(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有删除员工权限")

    employee = db.query(DBEmployee).filter(DBEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"员工不存在: {employee_id}")

    linked_users = db.query(User).filter(User.employee_id == employee_id).all()
    for user in linked_users:
        db.delete(user)
    db.delete(employee)
    db.commit()
    return {"success": True, "message": f"员工已删除: {employee.name}"}

@app.get("/api/employees/relations", response_model=List[EmployeeRelationResponse])
def list_employee_relations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_employee_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="No permission to view relations")
    rows = db.query(EmployeeRelation).order_by(EmployeeRelation.id.asc()).all()
    return [
        EmployeeRelationResponse(
            id=row.id,
            employee_id_a=row.employee_id_a,
            employee_id_b=row.employee_id_b,
            relation_type=row.relation_type,
            severity=float(row.severity),
        )
        for row in rows
    ]


@app.post("/api/employees/relations", response_model=EmployeeRelationResponse)
def upsert_employee_relation(
    request: EmployeeRelationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_employee_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="No permission to edit relations")
    validate_relation_payload(request)
    a, b = relation_to_ordered_pair(request.employee_id_a, request.employee_id_b)
    found_count = db.query(func.count(DBEmployee.id)).filter(DBEmployee.id.in_([a, b])).scalar() or 0
    if found_count != 2:
        raise HTTPException(status_code=400, detail="Employee not found in relation payload")

    row = (
        db.query(EmployeeRelation)
        .filter(EmployeeRelation.employee_id_a == a, EmployeeRelation.employee_id_b == b)
        .first()
    )
    if row is None:
        row = EmployeeRelation(employee_id_a=a, employee_id_b=b)
        db.add(row)
    row.relation_type = request.relation_type.strip()
    row.severity = request.severity
    db.commit()
    db.refresh(row)
    return EmployeeRelationResponse(
        id=row.id,
        employee_id_a=row.employee_id_a,
        employee_id_b=row.employee_id_b,
        relation_type=row.relation_type,
        severity=float(row.severity),
    )


@app.delete("/api/employees/relations")
def delete_employee_relation(
    employee_id_a: int,
    employee_id_b: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_employee_profile(current_user.role.code):
        raise HTTPException(status_code=403, detail="No permission to delete relations")
    a, b = relation_to_ordered_pair(employee_id_a, employee_id_b)
    row = (
        db.query(EmployeeRelation)
        .filter(EmployeeRelation.employee_id_a == a, EmployeeRelation.employee_id_b == b)
        .first()
    )
    if row is None:
        return {"success": True, "deleted": False}
    db.delete(row)
    db.commit()
    return {"success": True, "deleted": True}


@app.get("/api/stores/{store_id}/rule-config", response_model=StoreRuleConfigResponse)
def get_store_rule_config(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission for this store")
    config = db.query(StoreScheduleRuleConfig).filter(StoreScheduleRuleConfig.store_id == store_id).first()
    return store_rule_config_to_response(config, store_id)


@app.put("/api/stores/{store_id}/rule-config", response_model=StoreRuleConfigResponse)
def upsert_store_rule_config(
    store_id: int,
    request: StoreRuleConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_store_rules(current_user.role.code):
        raise HTTPException(status_code=403, detail="No permission to edit store rule config")
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission for this store")
    if request.store_id != store_id:
        raise HTTPException(status_code=400, detail="store_id mismatch")
    allowed_archetypes = {
        "auto",
        "peak_dual_core",
        "light_single_core",
        "standard_dual_shift",
        "flex_grid",
        "midweight_dual_role",
        "weekend_peak",
    }
    if request.schedule_archetype not in allowed_archetypes:
        raise HTTPException(status_code=400, detail="schedule_archetype is invalid")
    if request.weekday_total_hours_limit <= 0 or request.weekend_total_hours_limit <= 0:
        raise HTTPException(status_code=400, detail="daily total hours limits must be > 0")
    if request.sg_part_time_min_hours < 0 or request.sg_part_time_target_hours < request.sg_part_time_min_hours:
        raise HTTPException(status_code=400, detail="SG part-time hour targets are invalid")
    if request.target_160_last_week_days < 1 or request.target_160_last_week_days > 14:
        raise HTTPException(status_code=400, detail="target_160_last_week_days must be in [1, 14]")
    if request.min_backroom_per_hour < 0:
        raise HTTPException(status_code=400, detail="min_backroom_per_hour must be >= 0")
    if request.min_opening_keyholders < 0 or request.min_closing_keyholders < 0:
        raise HTTPException(status_code=400, detail="keyholder minima must be >= 0")
    if request.store_key_count < 0:
        raise HTTPException(status_code=400, detail="store_key_count must be >= 0")

    config = db.query(StoreScheduleRuleConfig).filter(StoreScheduleRuleConfig.store_id == store_id).first()
    if config is None:
        config = StoreScheduleRuleConfig(store_id=store_id)
        db.add(config)
    config.schedule_archetype = request.schedule_archetype
    config.weekday_total_hours_limit = request.weekday_total_hours_limit
    config.weekend_total_hours_limit = request.weekend_total_hours_limit
    config.sg_part_time_min_hours = request.sg_part_time_min_hours
    config.sg_part_time_target_hours = request.sg_part_time_target_hours
    config.target_160_last_week_days = request.target_160_last_week_days
    config.min_backroom_per_hour = request.min_backroom_per_hour
    config.require_opening_dual_skill = request.require_opening_dual_skill
    config.min_opening_keyholders = request.min_opening_keyholders
    config.min_closing_keyholders = request.min_closing_keyholders
    config.store_key_count = request.store_key_count
    db.commit()
    db.refresh(config)
    return store_rule_config_to_response(config, store_id)


@app.get("/api/stores/{store_id}/staffing-demand", response_model=StoreStaffingDemandResponse)
def get_store_staffing_demand(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission for this store")
    rows = (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store_id)
        .order_by(StoreStaffingDemand.day_of_week.asc(), StoreStaffingDemand.hour.asc())
        .all()
    )
    return staffing_demands_to_response(store_id, rows)


@app.put("/api/stores/{store_id}/staffing-demand", response_model=StoreStaffingDemandResponse)
def replace_store_staffing_demand(
    store_id: int,
    request: StoreStaffingDemandUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_edit_staffing_demand(current_user.role.code):
        raise HTTPException(status_code=403, detail="No permission to edit staffing demand")
    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission for this store")
    if request.store_id != store_id:
        raise HTTPException(status_code=400, detail="store_id mismatch")

    store = db.query(Store).filter(Store.id == store_id).first()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    min_hour, max_hour = hour_bounds_for_store(store)

    expanded_items: List[StoreStaffingDemandItem] = []
    if request.profiles:
        for profile in request.profiles:
            day_type = (profile.day_type or "").strip().lower()
            if day_type not in {"weekday", "weekend"}:
                raise HTTPException(status_code=400, detail=f"invalid day_type: {profile.day_type}")
            target_days = [0, 1, 2, 3, 4] if day_type == "weekday" else [5, 6]
            for day in target_days:
                expanded_items.append(
                    StoreStaffingDemandItem(
                        day_of_week=day,
                        day_type=day_type,
                        hour=profile.hour,
                        min_staff=profile.min_staff,
                    )
                )
    else:
        for item in request.items:
            if item.day_of_week is not None:
                expanded_items.append(item)
                continue
            day_type = (item.day_type or "").strip().lower()
            if day_type not in {"weekday", "weekend"}:
                raise HTTPException(status_code=400, detail="each item must provide day_of_week or valid day_type")
            target_days = [0, 1, 2, 3, 4] if day_type == "weekday" else [5, 6]
            for day in target_days:
                expanded_items.append(
                    StoreStaffingDemandItem(
                        day_of_week=day,
                        day_type=day_type,
                        hour=item.hour,
                        min_staff=item.min_staff,
                    )
                )

    seen_keys = set()
    for item in expanded_items:
        if item.day_of_week is None or item.day_of_week < 0 or item.day_of_week > 6:
            raise HTTPException(status_code=400, detail="day_of_week must be in [0, 6]")
        if item.hour < min_hour or item.hour > max_hour:
            raise HTTPException(
                status_code=400,
                detail=f"hour out of store business range({min_hour}-{max_hour}): {item.hour}",
            )
        if item.min_staff < 0:
            raise HTTPException(status_code=400, detail="min_staff must be >= 0")
        key = (item.day_of_week, item.hour)
        if key in seen_keys:
            raise HTTPException(status_code=400, detail=f"duplicate demand row: day={item.day_of_week}, hour={item.hour}")
        seen_keys.add(key)

    (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store_id)
        .delete(synchronize_session=False)
    )
    for item in expanded_items:
        db.add(
            StoreStaffingDemand(
                store_id=store_id,
                day_of_week=item.day_of_week,
                hour=item.hour,
                min_staff=item.min_staff,
            )
        )
    db.commit()
    rows = (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store_id)
        .order_by(StoreStaffingDemand.day_of_week.asc(), StoreStaffingDemand.hour.asc())
        .all()
    )
    return staffing_demands_to_response(store_id, rows)


@app.post("/api/generate-and-save-all-schedules", response_model=GenerateAllSchedulesResponse)
def generate_and_save_all_schedules(
    request: GenerateAllSchedulesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date = parse_date_str(request.week_start)
    if not can_generate_schedule(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有生成排班权限")
    if start_date.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start must be Monday")
    cycle_days = max(1, min(int(request.cycle_days or 7), 14))
    end_date = start_date + timedelta(days=cycle_days - 1)

    authorized_store_ids = sorted(get_authorized_store_ids(db, current_user))
    if not authorized_store_ids:
        return GenerateAllSchedulesResponse(
            success=True,
            message="No authorized stores",
            week_start=request.week_start,
            results=[],
        )

    algorithm_module = load_algorithm(request.algorithm)

    relation_rows = db.query(EmployeeRelation).all()
    bad_relations = [
        {
            "employee_id_a": row.employee_id_a,
            "employee_id_b": row.employee_id_b,
            "relation_type": row.relation_type,
            "severity": float(row.severity),
        }
        for row in relation_rows
        if row.relation_type == "bad"
    ]

    external_rows = (
        db.query(ScheduleEntry)
        .filter(
            ~ScheduleEntry.store_id.in_(authorized_store_ids),
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .all()
    )
    occupied_slots, external_store_days, external_daily_hours = build_external_schedule_context(external_rows)

    stores = (
        db.query(Store)
        .filter(Store.id.in_(authorized_store_ids))
        .order_by(Store.id.asc())
        .all()
    )
    if not stores:
        return GenerateAllSchedulesResponse(
            success=True,
            message="No stores found",
            week_start=request.week_start,
            results=[],
        )

    def store_generation_priority(store: Store) -> tuple[float, int]:
        eligible_count = (
            db.query(DBEmployee.id)
            .join(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
            .filter(
                EmployeeStoreAccess.store_id == store.id,
                DBEmployee.employment_status == EmploymentStatus.ACTIVE,
            )
            .distinct()
            .count()
        )
        open_start, open_end = hour_bounds_for_store(store)
        open_hours = max(1, open_end - open_start + 1)
        return (eligible_count / open_hours, store.id)

    stores = sorted(stores, key=store_generation_priority)

    pending_entries: List[ScheduleEntry] = []
    results: List[StoreGenerationResult] = []
    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)
    month_days = (next_month_start - month_start).days
    days_left_in_month = (next_month_start - today).days

    for store in stores:
        min_hour, max_hour = hour_bounds_for_store(store)
        config = (
            db.query(StoreScheduleRuleConfig)
            .filter(StoreScheduleRuleConfig.store_id == store.id)
            .first()
        )
        config_response = store_rule_config_to_response(config, store.id)
        store_links = (
            db.query(EmployeeStoreAccess)
            .filter(EmployeeStoreAccess.store_id == store.id)
            .all()
        )
        demand_rows = (
            db.query(StoreStaffingDemand)
            .filter(StoreStaffingDemand.store_id == store.id)
            .all()
        )
        demand_by_day_hour = {}
        for row in demand_rows:
            day_key = str(int(row.day_of_week))
            if day_key not in demand_by_day_hour:
                demand_by_day_hour[day_key] = {}
            demand_by_day_hour[day_key][str(int(row.hour))] = int(row.min_staff)

        employee_rows = (
            db.query(DBEmployee)
            .join(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
            .filter(
                EmployeeStoreAccess.store_id == store.id,
                DBEmployee.employment_status == EmploymentStatus.ACTIVE,
            )
            .distinct()
            .all()
        )
        for employee in employee_rows:
            normalize_employee_state(db, employee)

        employees_dict = []
        for employee in employee_rows:
            is_sg_pt = (
                employee.employment_type == EmploymentType.PART_TIME
                and employee.nationality_status in {NationalityStatus.SG_CITIZEN, NationalityStatus.SG_PR}
            )
            remaining_to_160 = max(
                0.0, config_response.sg_part_time_target_hours - float(employee.monthly_worked_hours)
            )
            availability_rows = get_effective_employee_availability_rows(employee)
            remaining_capacity_hours = 0.0
            for row in availability_rows:
                remaining_capacity_hours += max(
                    0.0,
                    (row.end_time.hour + row.end_time.minute / 60)
                    - (row.start_time.hour + row.start_time.minute / 60),
                )
            can_push_to_160 = True
            if (
                days_left_in_month <= config_response.target_160_last_week_days
                and remaining_to_160 > remaining_capacity_hours
            ):
                can_push_to_160 = False

            blocked_slots = [
                f"{slot_date.strftime('%Y-%m-%d')}|{slot_hour}"
                for (slot_emp, slot_date, slot_hour) in occupied_slots
                if slot_emp == employee.id
            ]
            employee_external_store_days = sorted(external_store_days.get(employee.id, set()))
            employee_external_daily_hours = dict(external_daily_hours.get(employee.id, {}))
            backroom_skill = next(
                (skill for skill in employee.skills if skill.skill_code == "backroom"),
                None,
            )
            skill_levels = {
                str(skill.skill_code): str(skill.level.value)
                for skill in employee.skills
            }
            employees_dict.append(
                {
                    "id": str(employee.id),
                    "name": employee.name,
                    "department": "",
                    "preferences": {
                        "preferred_shift": str(employee.preferred_shift or "no_preference"),
                    },
                    "meta": {
                        "employment_type": employee.employment_type.value,
                        "preferred_shift": str(employee.preferred_shift or "no_preference"),
                        "nationality_status": employee.nationality_status.value,
                        "monthly_worked_hours": float(employee.monthly_worked_hours),
                        "work_skill_score": int(employee.work_skill_score),
                        "management_skill_score": int(employee.management_skill_score),
                        "is_sg_part_time": is_sg_pt,
                        "sg_priority_to_80": bool(
                            is_sg_pt and employee.monthly_worked_hours < config_response.sg_part_time_min_hours
                        ),
                        "sg_priority_to_160": bool(
                            is_sg_pt
                            and can_push_to_160
                            and employee.monthly_worked_hours < config_response.sg_part_time_target_hours
                        ),
                        "days_left_in_month": days_left_in_month,
                        "month_days": month_days,
                        "availability_anchor_monday": employee.availability_anchor_monday.strftime("%Y-%m-%d"),
                        "availability_windows": [
                            {
                                "week_offset": row.week_offset,
                                "day_of_week": row.day_of_week,
                                "start_time": row.start_time.strftime("%H:%M"),
                                "end_time": row.end_time.strftime("%H:%M"),
                            }
                            for row in availability_rows
                        ],
                        "backroom_level": (
                            backroom_skill.level.value if backroom_skill is not None else SkillLevel.NONE.value
                        ),
                        "skill_levels": skill_levels,
                        "blocked_slots": blocked_slots,
                        "external_store_days": employee_external_store_days,
                        "external_daily_hours": employee_external_daily_hours,
                    },
                }
            )

        store_rules = {
            "algorithm": request.algorithm,
            "store_id": store.id,
            "store_archetype": config_response.schedule_archetype,
            "cycle_days": cycle_days,
            "start_date": request.week_start,
            "weekday_total_hours_limit": config_response.weekday_total_hours_limit,
            "weekend_total_hours_limit": config_response.weekend_total_hours_limit,
            "sg_part_time_min_hours": config_response.sg_part_time_min_hours,
            "sg_part_time_target_hours": config_response.sg_part_time_target_hours,
            "target_160_last_week_days": config_response.target_160_last_week_days,
            "min_backroom_per_hour": config_response.min_backroom_per_hour,
            "require_opening_dual_skill": config_response.require_opening_dual_skill,
            "min_opening_keyholders": config_response.min_opening_keyholders,
            "min_closing_keyholders": config_response.min_closing_keyholders,
            "store_key_count": config_response.store_key_count,
            "store_hour_start": min_hour,
            "store_hour_end": max_hour,
            "store_key_holder_employee_ids": [link.employee_id for link in store_links if bool(link.has_key)],
            "store_employee_priority": {
                str(link.employee_id): link.priority
                for link in store_links
                if link.priority is not None
            },
            "bad_relations": bad_relations,
            "demand_by_day_hour": demand_by_day_hour,
        }
        schedule_result = algorithm_module.generate_schedule(employees_dict, store_rules)
        employee_id_set = {employee.id for employee in employee_rows}
        store_assignments = 0
        skipped_conflicts = 0

        for date_text, assignments in (schedule_result or {}).items():
            if not isinstance(assignments, list):
                continue
            work_date = parse_date_str(date_text)
            if work_date < start_date or work_date > end_date:
                continue
            for assignment in assignments:
                try:
                    employee_id = int(assignment.get("employee_id"))
                except Exception:
                    continue
                if employee_id not in employee_id_set:
                    continue
                hour = resolve_hour_from_assignment(assignment, min_hour)
                if hour < min_hour or hour > max_hour:
                    continue
                slot_key = (employee_id, work_date, hour)
                if slot_key in occupied_slots:
                    skipped_conflicts += 1
                    continue
                occupied_slots.add(slot_key)
                date_key = work_date.strftime("%Y-%m-%d")
                external_store_days.setdefault(employee_id, set()).add(date_key)
                external_daily_hours.setdefault(employee_id, {})
                external_daily_hours[employee_id][date_key] = external_daily_hours[employee_id].get(date_key, 0) + 1
                pending_entries.append(
                    ScheduleEntry(
                        store_id=store.id,
                        employee_id=employee_id,
                        work_date=work_date,
                        hour=hour,
                    )
                )
                store_assignments += 1

        results.append(
            StoreGenerationResult(
                store_id=store.id,
                store_name=store.name,
                employees_considered=len(employee_rows),
                assignments_saved=store_assignments,
                assignments_skipped_conflict=skipped_conflicts,
            )
        )

    pending_entries, removed_short_entries = prune_short_store_blocks(
        pending_entries,
        minimum_block_hours=3,
    )

    (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id.in_(authorized_store_ids),
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .delete(synchronize_session=False)
    )
    for entry in pending_entries:
        db.add(entry)
    db.flush()
    removed_short_entries += prune_short_schedule_entries_in_db(
        db,
        store_ids=authorized_store_ids,
        start_date=start_date,
        end_date=end_date,
        minimum_block_hours=3,
    )
    db.commit()

    return GenerateAllSchedulesResponse(
        success=True,
        message=(
            "Generated and saved schedules for all authorized stores"
            + (f"; pruned {removed_short_entries} short-hour assignments" if removed_short_entries else "")
        ),
        week_start=request.week_start,
        results=results,
    )


@app.post("/api/generate-and-save-store-schedule", response_model=GenerateStoreScheduleResponse)
def generate_and_save_store_schedule(
    request: GenerateStoreScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date = parse_date_str(request.week_start)
    if not can_generate_schedule(current_user.role.code):
        raise HTTPException(status_code=403, detail="当前角色没有生成排班权限")
    if start_date.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start must be Monday")
    cycle_days = max(1, min(int(request.cycle_days or 7), 14))
    end_date = start_date + timedelta(days=cycle_days - 1)

    authorized_store_ids = get_authorized_store_ids(db, current_user)
    if request.store_id not in authorized_store_ids:
        raise HTTPException(status_code=403, detail="No permission for the selected store")

    store = (
        db.query(Store)
        .filter(Store.id == request.store_id)
        .first()
    )
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    algorithm_module = load_algorithm(request.algorithm)

    relation_rows = db.query(EmployeeRelation).all()
    bad_relations = [
        {
            "employee_id_a": row.employee_id_a,
            "employee_id_b": row.employee_id_b,
            "relation_type": row.relation_type,
            "severity": float(row.severity),
        }
        for row in relation_rows
        if row.relation_type == "bad"
    ]

    external_rows = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id != store.id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .all()
    )
    occupied_slots, external_store_days, external_daily_hours = build_external_schedule_context(external_rows)

    min_hour, max_hour = hour_bounds_for_store(store)
    config = (
        db.query(StoreScheduleRuleConfig)
        .filter(StoreScheduleRuleConfig.store_id == store.id)
        .first()
    )
    config_response = store_rule_config_to_response(config, store.id)
    store_links = (
        db.query(EmployeeStoreAccess)
        .filter(EmployeeStoreAccess.store_id == store.id)
        .all()
    )
    demand_rows = (
        db.query(StoreStaffingDemand)
        .filter(StoreStaffingDemand.store_id == store.id)
        .all()
    )
    demand_by_day_hour = {}
    for row in demand_rows:
        day_key = str(int(row.day_of_week))
        if day_key not in demand_by_day_hour:
            demand_by_day_hour[day_key] = {}
        demand_by_day_hour[day_key][str(int(row.hour))] = int(row.min_staff)

    employee_rows = (
        db.query(DBEmployee)
        .join(EmployeeStoreAccess, EmployeeStoreAccess.employee_id == DBEmployee.id)
        .filter(
            EmployeeStoreAccess.store_id == store.id,
            DBEmployee.employment_status == EmploymentStatus.ACTIVE,
        )
        .distinct()
        .all()
    )
    for employee in employee_rows:
        normalize_employee_state(db, employee)

    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)
    month_days = (next_month_start - month_start).days
    days_left_in_month = (next_month_start - today).days

    employees_dict = []
    for employee in employee_rows:
        is_sg_pt = (
            employee.employment_type == EmploymentType.PART_TIME
            and employee.nationality_status in {NationalityStatus.SG_CITIZEN, NationalityStatus.SG_PR}
        )
        remaining_to_160 = max(
            0.0, config_response.sg_part_time_target_hours - float(employee.monthly_worked_hours)
        )
        availability_rows = get_effective_employee_availability_rows(employee)
        remaining_capacity_hours = 0.0
        for row in availability_rows:
            remaining_capacity_hours += max(
                0.0,
                (row.end_time.hour + row.end_time.minute / 60)
                - (row.start_time.hour + row.start_time.minute / 60),
            )
        can_push_to_160 = True
        if (
            days_left_in_month <= config_response.target_160_last_week_days
            and remaining_to_160 > remaining_capacity_hours
        ):
            can_push_to_160 = False

        blocked_slots = [
            f"{slot_date.strftime('%Y-%m-%d')}|{slot_hour}"
            for (slot_emp, slot_date, slot_hour) in occupied_slots
            if slot_emp == employee.id
        ]
        employee_external_store_days = sorted(external_store_days.get(employee.id, set()))
        employee_external_daily_hours = dict(external_daily_hours.get(employee.id, {}))
        backroom_skill = next(
            (skill for skill in employee.skills if skill.skill_code == "backroom"),
            None,
        )
        skill_levels = {
            str(skill.skill_code): str(skill.level.value)
            for skill in employee.skills
        }
        employees_dict.append(
            {
                "id": str(employee.id),
                "name": employee.name,
                "department": "",
                "preferences": {
                    "preferred_shift": str(employee.preferred_shift or "no_preference"),
                },
                "meta": {
                    "employment_type": employee.employment_type.value,
                    "preferred_shift": str(employee.preferred_shift or "no_preference"),
                    "nationality_status": employee.nationality_status.value,
                    "monthly_worked_hours": float(employee.monthly_worked_hours),
                    "work_skill_score": int(employee.work_skill_score),
                    "management_skill_score": int(employee.management_skill_score),
                    "is_sg_part_time": is_sg_pt,
                    "sg_priority_to_80": bool(
                        is_sg_pt and employee.monthly_worked_hours < config_response.sg_part_time_min_hours
                    ),
                    "sg_priority_to_160": bool(
                        is_sg_pt
                        and can_push_to_160
                        and employee.monthly_worked_hours < config_response.sg_part_time_target_hours
                    ),
                    "days_left_in_month": days_left_in_month,
                    "month_days": month_days,
                    "availability_anchor_monday": employee.availability_anchor_monday.strftime("%Y-%m-%d"),
                    "availability_windows": [
                        {
                            "week_offset": row.week_offset,
                            "day_of_week": row.day_of_week,
                            "start_time": row.start_time.strftime("%H:%M"),
                            "end_time": row.end_time.strftime("%H:%M"),
                        }
                        for row in availability_rows
                    ],
                    "backroom_level": (
                        backroom_skill.level.value if backroom_skill is not None else SkillLevel.NONE.value
                    ),
                    "skill_levels": skill_levels,
                    "blocked_slots": blocked_slots,
                    "external_store_days": employee_external_store_days,
                    "external_daily_hours": employee_external_daily_hours,
                },
            }
        )

    store_rules = {
        "algorithm": request.algorithm,
        "store_id": store.id,
        "store_archetype": config_response.schedule_archetype,
        "cycle_days": cycle_days,
        "start_date": request.week_start,
        "weekday_total_hours_limit": config_response.weekday_total_hours_limit,
        "weekend_total_hours_limit": config_response.weekend_total_hours_limit,
        "sg_part_time_min_hours": config_response.sg_part_time_min_hours,
        "sg_part_time_target_hours": config_response.sg_part_time_target_hours,
        "target_160_last_week_days": config_response.target_160_last_week_days,
        "min_backroom_per_hour": config_response.min_backroom_per_hour,
        "require_opening_dual_skill": config_response.require_opening_dual_skill,
        "min_opening_keyholders": config_response.min_opening_keyholders,
        "min_closing_keyholders": config_response.min_closing_keyholders,
        "store_key_count": config_response.store_key_count,
        "store_hour_start": min_hour,
        "store_hour_end": max_hour,
        "store_key_holder_employee_ids": [link.employee_id for link in store_links if bool(link.has_key)],
        "store_employee_priority": {
            str(link.employee_id): link.priority
            for link in store_links
            if link.priority is not None
        },
        "bad_relations": bad_relations,
        "demand_by_day_hour": demand_by_day_hour,
    }

    schedule_result = algorithm_module.generate_schedule(employees_dict, store_rules)
    employee_id_set = {employee.id for employee in employee_rows}
    pending_entries: List[ScheduleEntry] = []
    store_assignments = 0
    skipped_conflicts = 0

    for date_text, assignments in (schedule_result or {}).items():
        if not isinstance(assignments, list):
            continue
        work_date = parse_date_str(date_text)
        if work_date < start_date or work_date > end_date:
            continue
        for assignment in assignments:
            try:
                employee_id = int(assignment.get("employee_id"))
            except Exception:
                continue
            if employee_id not in employee_id_set:
                continue
            hour = resolve_hour_from_assignment(assignment, min_hour)
            if hour < min_hour or hour > max_hour:
                continue
            slot_key = (employee_id, work_date, hour)
            if slot_key in occupied_slots:
                skipped_conflicts += 1
                continue
            occupied_slots.add(slot_key)
            pending_entries.append(
                ScheduleEntry(
                    store_id=store.id,
                    employee_id=employee_id,
                    work_date=work_date,
                    hour=hour,
                )
            )
            store_assignments += 1

    pending_entries, removed_short_entries = prune_short_store_blocks(
        pending_entries,
        minimum_block_hours=3,
    )

    (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.store_id == store.id,
            ScheduleEntry.work_date >= start_date,
            ScheduleEntry.work_date <= end_date,
        )
        .delete(synchronize_session=False)
    )
    for entry in pending_entries:
        db.add(entry)
    db.flush()
    removed_short_entries += prune_short_schedule_entries_in_db(
        db,
        store_ids=[store.id],
        start_date=start_date,
        end_date=end_date,
        minimum_block_hours=3,
    )
    db.commit()

    result = StoreGenerationResult(
        store_id=store.id,
        store_name=store.name,
        employees_considered=len(employee_rows),
        assignments_saved=store_assignments,
        assignments_skipped_conflict=skipped_conflicts,
    )
    return GenerateStoreScheduleResponse(
        success=True,
        message=(
            f"Generated and saved schedule for store {store.name}"
            + (f"; pruned {removed_short_entries} short-hour assignments" if removed_short_entries else "")
        ),
        week_start=request.week_start,
        result=result,
    )


@app.get("/api/algorithms")
def list_algorithms():
    """列出所有可用算法。"""
    algorithms = []
    for file in os.listdir(ALGORITHMS_DIR):
        if file.endswith(".py") and not file.startswith("__"):
            algorithms.append(file[:-3])
    return {"algorithms": algorithms}

@app.post("/api/generate-schedule", response_model=AlgorithmResponse)
def generate_schedule(
    request: ScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate schedule with v1 rule config enrichment."""
    try:
        if not can_generate_schedule(current_user.role.code):
            raise HTTPException(status_code=403, detail="当前角色没有生成排班权限")
        algorithm_name = request.rules.get("algorithm", "default_schedule")
        algorithm_module = load_algorithm(algorithm_name)

        rules = dict(request.rules or {})
        store_id = rules.get("store_id")
        store = None
        if store_id is not None:
            store = db.query(Store).filter(Store.id == int(store_id)).first()
            authorized_store_ids = get_authorized_store_ids(db, current_user)
            if store is None:
                raise HTTPException(status_code=404, detail="Store not found")
            if int(store_id) not in authorized_store_ids:
                raise HTTPException(status_code=403, detail="当前角色无权生成该店铺排班")
        config = None
        if store is not None:
            config = (
                db.query(StoreScheduleRuleConfig)
                .filter(StoreScheduleRuleConfig.store_id == store.id)
                .first()
            )

        config_response = store_rule_config_to_response(config, int(store_id or 0))
        rules["weekday_total_hours_limit"] = config_response.weekday_total_hours_limit
        rules["weekend_total_hours_limit"] = config_response.weekend_total_hours_limit
        rules["store_archetype"] = config_response.schedule_archetype
        rules["sg_part_time_min_hours"] = config_response.sg_part_time_min_hours
        rules["sg_part_time_target_hours"] = config_response.sg_part_time_target_hours
        rules["target_160_last_week_days"] = config_response.target_160_last_week_days
        rules["min_backroom_per_hour"] = config_response.min_backroom_per_hour
        rules["require_opening_dual_skill"] = config_response.require_opening_dual_skill
        rules["min_opening_keyholders"] = config_response.min_opening_keyholders
        rules["min_closing_keyholders"] = config_response.min_closing_keyholders
        rules["store_key_count"] = config_response.store_key_count

        if store is not None:
            start_hour, end_hour = hour_bounds_for_store(store)
            rules["store_hour_start"] = start_hour
            rules["store_hour_end"] = end_hour
            store_links = (
                db.query(EmployeeStoreAccess)
                .filter(EmployeeStoreAccess.store_id == store.id)
                .all()
            )
            rules["store_key_holder_employee_ids"] = [
                link.employee_id for link in store_links if bool(link.has_key)
            ]
            rules["store_employee_priority"] = {
                str(link.employee_id): link.priority
                for link in store_links
                if link.priority is not None
            }
            demand_rows = (
                db.query(StoreStaffingDemand)
                .filter(StoreStaffingDemand.store_id == store.id)
                .all()
            )
            demand_by_day_hour = {}
            for row in demand_rows:
                day_key = str(int(row.day_of_week))
                if day_key not in demand_by_day_hour:
                    demand_by_day_hour[day_key] = {}
                demand_by_day_hour[day_key][str(int(row.hour))] = int(row.min_staff)
            rules["demand_by_day_hour"] = demand_by_day_hour

        relation_rows = db.query(EmployeeRelation).all()
        rules["bad_relations"] = [
            {
                "employee_id_a": row.employee_id_a,
                "employee_id_b": row.employee_id_b,
                "relation_type": row.relation_type,
                "severity": float(row.severity),
            }
            for row in relation_rows
            if row.relation_type == "bad"
        ]

        employees_dict = [emp.dict() for emp in request.employees]
        employee_ids = []
        for item in employees_dict:
            try:
                employee_ids.append(int(item.get("id")))
            except Exception:
                continue
        db_employees = {}
        if employee_ids:
            rows = db.query(DBEmployee).filter(DBEmployee.id.in_(employee_ids)).all()
            db_employees = {row.id: row for row in rows}

        preview_occupied_slots: set[tuple[int, date, int]] = set()
        preview_external_store_days: dict[int, set[str]] = {}
        preview_external_daily_hours: dict[int, dict[str, int]] = {}
        if store is not None and employee_ids:
            preview_start_date = parse_date_str(str(rules.get("start_date", date.today().strftime("%Y-%m-%d"))))
            preview_cycle_days = max(1, min(int(rules.get("cycle_days", 7)), 14))
            preview_end_date = preview_start_date + timedelta(days=preview_cycle_days - 1)
            existing_rows = (
                db.query(ScheduleEntry)
                .filter(
                    ScheduleEntry.employee_id.in_(employee_ids),
                    ScheduleEntry.work_date >= preview_start_date,
                    ScheduleEntry.work_date <= preview_end_date,
                )
                .all()
            )
            preview_occupied_slots, preview_external_store_days, preview_external_daily_hours = build_external_schedule_context(
                existing_rows,
                exclude_store_id=store.id,
            )

        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        month_days = (next_month_start - month_start).days
        days_left_in_month = (next_month_start - today).days

        for item in employees_dict:
            db_emp = None
            try:
                db_emp = db_employees.get(int(item.get("id")))
            except Exception:
                db_emp = None
            if db_emp is None:
                continue

            is_sg_pt = (
                db_emp.employment_type == EmploymentType.PART_TIME
                and db_emp.nationality_status in {NationalityStatus.SG_CITIZEN, NationalityStatus.SG_PR}
            )
            remaining_to_160 = max(0.0, config_response.sg_part_time_target_hours - float(db_emp.monthly_worked_hours))
            availability_rows = get_effective_employee_availability_rows(db_emp)
            remaining_capacity_hours = 0.0
            for row in availability_rows:
                remaining_capacity_hours += max(0.0, (row.end_time.hour + row.end_time.minute / 60) - (row.start_time.hour + row.start_time.minute / 60))

            can_push_to_160 = True
            if days_left_in_month <= config_response.target_160_last_week_days and remaining_to_160 > remaining_capacity_hours:
                can_push_to_160 = False

            item["meta"] = {
                "employment_type": db_emp.employment_type.value,
                "preferred_shift": str(db_emp.preferred_shift or "no_preference"),
                "nationality_status": db_emp.nationality_status.value,
                "monthly_worked_hours": float(db_emp.monthly_worked_hours),
                "work_skill_score": int(db_emp.work_skill_score),
                "management_skill_score": int(db_emp.management_skill_score),
                "is_sg_part_time": is_sg_pt,
                "sg_priority_to_80": bool(is_sg_pt and db_emp.monthly_worked_hours < config_response.sg_part_time_min_hours),
                "sg_priority_to_160": bool(is_sg_pt and can_push_to_160 and db_emp.monthly_worked_hours < config_response.sg_part_time_target_hours),
                "days_left_in_month": days_left_in_month,
                "month_days": month_days,
                "availability_anchor_monday": db_emp.availability_anchor_monday.strftime("%Y-%m-%d"),
            }
            item["preferences"] = {
                "preferred_shift": str(db_emp.preferred_shift or "no_preference"),
            }
            item["meta"]["availability_windows"] = [
                {
                    "week_offset": row.week_offset,
                    "day_of_week": row.day_of_week,
                    "start_time": row.start_time.strftime("%H:%M"),
                    "end_time": row.end_time.strftime("%H:%M"),
                }
                for row in get_effective_employee_availability_rows(db_emp)
            ]
            item["meta"]["blocked_slots"] = [
                f"{slot_date.strftime('%Y-%m-%d')}|{slot_hour}"
                for (slot_emp, slot_date, slot_hour) in preview_occupied_slots
                if slot_emp == db_emp.id
            ]
            item["meta"]["external_store_days"] = sorted(preview_external_store_days.get(db_emp.id, set()))
            item["meta"]["external_daily_hours"] = dict(preview_external_daily_hours.get(db_emp.id, {}))
            backroom_skill = next(
                (skill for skill in db_emp.skills if skill.skill_code == "backroom"),
                None,
            )
            item["meta"]["skill_levels"] = {
                str(skill.skill_code): str(skill.level.value)
                for skill in db_emp.skills
            }
            item["meta"]["backroom_level"] = (
                backroom_skill.level.value if backroom_skill is not None else SkillLevel.NONE.value
            )

        schedule_result = algorithm_module.generate_schedule(employees_dict, rules)

        return AlgorithmResponse(
            success=True,
            message="Schedule generated",
            schedule=schedule_result,
        )

    except FileNotFoundError as e:
        return AlgorithmResponse(
            success=False,
            message="Algorithm not found",
            error=str(e),
        )
    except Exception as e:
        return AlgorithmResponse(
            success=False,
            message="Algorithm execution error",
            error=str(e),
        )

# Create fallback algorithm files when they do not exist.
if not os.path.exists(os.path.join(ALGORITHMS_DIR, "default_schedule.py")):
    with open(os.path.join(ALGORITHMS_DIR, "default_schedule.py"), "w", encoding="utf-8") as f:
        f.write(
            "# Default scheduling algorithm\n\n"
            "def generate_schedule(employees: list, rules: dict) -> dict:\n"
            "    # A tiny fallback scheduler used only when the real file is missing.\n"
            "    import datetime\n\n"
            "    cycle_days = rules.get(\"cycle_days\", 7)\n"
            "    start_date = rules.get(\"start_date\", \"2026-01-20\")\n"
            "    current_date = datetime.datetime.strptime(start_date, \"%Y-%m-%d\")\n\n"
            "    schedule = {}\n"
            "    employee_count = len(employees)\n"
            "    if employee_count == 0:\n"
            "        return {}\n\n"
            "    for day in range(cycle_days):\n"
            "        date_str = (current_date + datetime.timedelta(days=day)).strftime(\"%Y-%m-%d\")\n"
            "        employee_index = day % employee_count\n"
            "        schedule[date_str] = [{\n"
            "            \"employee_id\": employees[employee_index][\"id\"],\n"
            "            \"employee_name\": employees[employee_index][\"name\"],\n"
            "            \"shift\": \"morning\" if day % 3 == 0 else \"afternoon\" if day % 3 == 1 else \"evening\"\n"
            "        }]\n\n"
            "    return schedule\n"
        )

if not os.path.exists(os.path.join(ALGORITHMS_DIR, "custom_schedule.py")):
    with open(os.path.join(ALGORITHMS_DIR, "custom_schedule.py"), "w", encoding="utf-8") as f:
        f.write(
            "# Custom scheduling algorithm\n\n"
            "def generate_schedule(employees: list, rules: dict) -> dict:\n"
            "    # A simple fallback custom scheduler used only when the real file is missing.\n"
            "    import datetime\n"
            "    from collections import defaultdict\n\n"
            "    cycle_days = rules.get(\"cycle_days\", 7)\n"
            "    start_date = rules.get(\"start_date\", \"2026-01-20\")\n"
            "    max_shifts_per_employee = rules.get(\"max_shifts_per_employee\", 5)\n"
            "    required_shifts_per_day = rules.get(\"required_shifts_per_day\", 1)\n\n"
            "    try:\n"
            "        current_date = datetime.datetime.strptime(start_date, \"%Y-%m-%d\")\n"
            "    except ValueError:\n"
            "        current_date = datetime.datetime(2026, 1, 20)\n\n"
            "    if not employees:\n"
            "        return {}\n\n"
            "    schedule = defaultdict(list)\n"
            "    employee_shift_count = {emp[\"id\"]: 0 for emp in employees}\n"
            "    shifts = [\"morning\", \"afternoon\", \"evening\"]\n\n"
            "    for day in range(cycle_days):\n"
            "        date_str = (current_date + datetime.timedelta(days=day)).strftime(\"%Y-%m-%d\")\n"
            "        assigned = 0\n"
            "        for employee in employees:\n"
            "            if employee_shift_count[employee[\"id\"]] >= max_shifts_per_employee:\n"
            "                continue\n"
            "            schedule[date_str].append({\n"
            "                \"employee_id\": employee[\"id\"],\n"
            "                \"employee_name\": employee[\"name\"],\n"
            "                \"shift\": shifts[(day + assigned) % len(shifts)]\n"
            "            })\n"
            "            employee_shift_count[employee[\"id\"]] += 1\n"
            "            assigned += 1\n"
            "            if assigned >= required_shifts_per_day:\n"
            "                break\n\n"
            "    return dict(schedule)\n"
        )






