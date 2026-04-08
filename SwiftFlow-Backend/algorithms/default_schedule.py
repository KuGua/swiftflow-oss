from __future__ import annotations

from datetime import datetime, timedelta
from itertools import combinations, permutations


def _parse_hour(time_text: str) -> int:
    try:
        hours, minutes = str(time_text).split(":", 1)
        hour = int(hours)
        minute = int(minutes)
        if minute > 0:
            return hour + 1
        return hour
    except Exception:
        return 0


def _week_offset_and_day(employee: dict, start_date: datetime, target_date: datetime) -> tuple[int, int]:
    anchor_text = str(employee.get("meta", {}).get("availability_anchor_monday", "")).strip()
    day_delta = (target_date.date() - start_date.date()).days
    if anchor_text:
        try:
            anchor_date = datetime.strptime(anchor_text, "%Y-%m-%d").date()
            day_delta = (target_date.date() - anchor_date).days
        except Exception:
            pass
    if day_delta < 0:
        week_offset = -1
    elif day_delta < 7:
        week_offset = 0
    else:
        week_offset = 1
    day_of_week = target_date.weekday()
    return week_offset, day_of_week


def _required_daily_hours(employee: dict) -> int:
    employment_type = str(employee.get("meta", {}).get("employment_type", "")).lower()
    if "part" in employment_type:
        return 4
    return 10


def _minimum_shift_block_hours(employee: dict, *, repair_mode: bool = False) -> int:
    if repair_mode:
        return 3
    return _required_daily_hours(employee)


def _is_part_time(employee: dict) -> bool:
    employment_type = str(employee.get("meta", {}).get("employment_type", "")).lower()
    return "part" in employment_type


def _is_full_time(employee: dict) -> bool:
    return not _is_part_time(employee)


def _preferred_max_daily_hours(employee: dict) -> int:
    if _is_part_time(employee):
        meta = employee.get("meta", {})
        preferred = str(meta.get("preferred_shift", employee.get("preferences", {}).get("preferred_shift", "no_preference")) or "no_preference").lower()
        if preferred == "closing":
            return 8
        if preferred == "midday":
            return 7
        return 8
    return 10


def _absolute_max_daily_hours(employee: dict) -> int:
    return 12


def _preferred_hours_penalty(
    employee: dict,
    *,
    external_daily_hours: int,
    proposed_total_hours: int,
    closing_sensitive: bool = False,
) -> float:
    preferred_max = _preferred_max_daily_hours(employee)
    overtime_hours = max(0, int(external_daily_hours) + int(proposed_total_hours) - int(preferred_max))
    if overtime_hours <= 0:
        return 0.0

    if _is_full_time(employee):
        base_penalty = 1200.0
        per_hour_penalty = 320.0
        if closing_sensitive:
            base_penalty += 700.0
            per_hour_penalty += 180.0
    else:
        base_penalty = 900.0
        per_hour_penalty = 220.0
        if closing_sensitive:
            base_penalty += 180.0
            per_hour_penalty += 60.0

    return -(base_penalty + float(max(0, overtime_hours - 1)) * per_hour_penalty)


def _availability_row(employee: dict, start_date: datetime, target_date: datetime) -> dict | None:
    meta = employee.get("meta", {})
    windows = meta.get("availability_windows", [])
    week_offset, day_of_week = _week_offset_and_day(employee, start_date, target_date)
    if week_offset not in {0, 1}:
        return None
    for row in windows:
        if row.get("week_offset") != week_offset:
            continue
        if row.get("day_of_week") != day_of_week:
            continue
        return row
    return None


def _is_available(employee: dict, start_date: datetime, target_date: datetime, hour: int) -> bool:
    row = _availability_row(employee, start_date, target_date)
    if row is None:
        return False
    start_h = _parse_hour(row.get("start_time", "00:00"))
    end_h = _parse_hour(row.get("end_time", "00:00"))
    return start_h <= hour < end_h


def _continuous_hours_available(
    employee: dict,
    start_date: datetime,
    target_date: datetime,
    start_hour: int,
    hour_end: int,
) -> int:
    meta = employee.get("meta", {})
    blocked = set(meta.get("blocked_slots", []))
    row = _availability_row(employee, start_date, target_date)
    if row is None:
        return 0

    start_h = _parse_hour(row.get("start_time", "00:00"))
    end_h = _parse_hour(row.get("end_time", "00:00"))
    date_key = target_date.strftime("%Y-%m-%d")
    contiguous = 0

    for hour in range(start_hour, hour_end + 1):
        if not (start_h <= hour < end_h):
            break
        if f"{date_key}|{hour}" in blocked:
            break
        contiguous += 1

    return contiguous


def _shift_name(hour: int) -> str:
    if hour < 13:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _hour_target(
    demand_by_day_hour: dict,
    date_obj: datetime,
    hour: int,
    required_per_hour: int,
    *,
    allow_zero_demand: bool = False,
) -> int:
    day_demands = demand_by_day_hour.get(str(date_obj.weekday()), {})
    has_explicit_hour = str(hour) in day_demands or hour in day_demands
    target_staff = int(day_demands.get(str(hour), day_demands.get(hour, required_per_hour)))
    if allow_zero_demand and has_explicit_hour:
        return max(0, target_staff)
    return max(1, target_staff)


def _find_cover_block_start(
    employee: dict,
    start_date: datetime,
    target_date: datetime,
    target_hour: int,
    required_hours: int,
    hour_start: int,
    hour_end: int,
) -> int | None:
    row = _availability_row(employee, start_date, target_date)
    if row is None:
        return None

    window_start = max(hour_start, _parse_hour(row.get("start_time", "00:00")))
    window_end = min(hour_end + 1, _parse_hour(row.get("end_time", "00:00")))
    if window_end - window_start < required_hours:
        return None

    latest_start = min(target_hour, window_end - required_hours)
    earliest_start = max(window_start, target_hour - required_hours + 1)
    if earliest_start > latest_start:
        return None

    best_start = None
    for block_start in range(latest_start, earliest_start - 1, -1):
        block_end = block_start + required_hours
        if block_end > window_end:
            continue
        if not all(
            _is_available(employee, start_date, target_date, hour)
            for hour in range(block_start, block_end)
        ):
            continue
        best_start = block_start
        break

    return best_start


def _find_cover_block_for_range(
    employee: dict,
    start_date: datetime,
    target_date: datetime,
    cover_start: int,
    cover_end: int,
    block_hours: int,
    hour_start: int,
    hour_end: int,
) -> int | None:
    row = _availability_row(employee, start_date, target_date)
    if row is None:
        return None

    window_start = max(hour_start, _parse_hour(row.get("start_time", "00:00")))
    window_end = min(hour_end + 1, _parse_hour(row.get("end_time", "00:00")))
    if window_end - window_start < block_hours:
        return None

    earliest_start = max(window_start, cover_end - block_hours + 1)
    latest_start = min(cover_start, window_end - block_hours)
    if earliest_start > latest_start:
        return None

    for block_start in range(latest_start, earliest_start - 1, -1):
        block_end = block_start + block_hours - 1
        if block_end < cover_end:
            continue
        if not all(
            _is_available(employee, start_date, target_date, hour)
            for hour in range(block_start, block_end + 1)
        ):
            continue
        return block_start

    return None


def _find_extension_hours(
    employee: dict,
    start_date: datetime,
    target_date: datetime,
    current_end: int,
    target_hour: int,
    max_additional_hours: int,
) -> list[int]:
    if current_end >= target_hour or max_additional_hours <= 0:
        return []

    extension = []
    for hour in range(current_end + 1, target_hour + 1):
        if len(extension) >= max_additional_hours:
            break
        if not _is_available(employee, start_date, target_date, hour):
            break
        extension.append(hour)

    if extension and extension[-1] == target_hour:
        return extension
    return []


def _can_cover_extension_without_overtime(
    employee: dict,
    *,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    extension_hours: list[int],
    daily_blocks: dict,
    relation_map: dict,
    hour_index: dict,
    closing_hour: int,
) -> bool:
    if not extension_hours:
        return False

    emp_id = str(employee.get("id"))
    block = daily_blocks.get((date_key, emp_id))
    if block is None:
        return False

    current_start = int(block.get("start", extension_hours[0]))
    current_end = int(block.get("end", extension_hours[0] - 1))
    if current_end + 1 != extension_hours[0]:
        return False

    meta = employee.get("meta", {})
    external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
    current_block_hours = current_end - current_start + 1
    preferred_max_daily_hours = _preferred_max_daily_hours(employee)
    absolute_max_daily_hours = _absolute_max_daily_hours(employee)
    if external_daily_hours + current_block_hours + len(extension_hours) > preferred_max_daily_hours:
        return False
    if external_daily_hours + current_block_hours + len(extension_hours) > absolute_max_daily_hours:
        return False

    if _has_severe_relation_conflict(relation_map, hour_index, emp_id, extension_hours):
        return False

    for hour in extension_hours:
        if not _is_available(employee, start_date, target_date, hour):
            return False

    reaches_closing = extension_hours[-1] >= closing_hour
    if reaches_closing and not (_closing_task_skill_count(employee) > 0 or _has_backroom_skill(employee)):
        return False

    return True


def _has_non_overtime_alternative_for_extension(
    *,
    employees: list,
    source_employee_id: str,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    extension_hours: list[int],
    daily_blocks: dict,
    relation_map: dict,
    hour_index: dict,
    closing_hour: int,
) -> bool:
    if not extension_hours:
        return False

    for employee in employees:
        emp_id = str(employee.get("id"))
        if emp_id == source_employee_id:
            continue
        if not _is_part_time(employee):
            continue
        if _can_cover_extension_without_overtime(
            employee,
            start_date=start_date,
            target_date=target_date,
            date_key=date_key,
            extension_hours=extension_hours,
            daily_blocks=daily_blocks,
            relation_map=relation_map,
            hour_index=hour_index,
            closing_hour=closing_hour,
        ):
            return True
    return False


def _has_non_overtime_part_time_hour_cover(
    *,
    employees: list,
    candidate_employee_id: str,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    target_hour: int,
    daily_blocks: dict,
    relation_map: dict,
    schedule_assignments: list[dict],
    closing_hour: int,
) -> bool:
    hour_index = _build_hour_index(schedule_assignments)

    for employee in employees:
        emp_id = str(employee.get("id"))
        if emp_id == candidate_employee_id or not _is_part_time(employee):
            continue
        if not _is_available(employee, start_date, target_date, target_hour):
            continue

        block = daily_blocks.get((date_key, emp_id))
        meta = employee.get("meta", {})
        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        preferred_max_daily_hours = _preferred_max_daily_hours(employee)
        absolute_max_daily_hours = _absolute_max_daily_hours(employee)

        if block is not None:
            current_start = int(block.get("start", target_hour))
            current_end = int(block.get("end", target_hour))
            if current_end + 1 != target_hour and current_start - 1 != target_hour:
                continue
            current_hours = current_end - current_start + 1
            proposed_total_hours = current_hours + 1
            if external_daily_hours + proposed_total_hours > preferred_max_daily_hours:
                continue
            if external_daily_hours + proposed_total_hours > absolute_max_daily_hours:
                continue
            if _has_severe_relation_conflict(relation_map, hour_index, emp_id, [target_hour]):
                continue
        else:
            required_hours = _minimum_shift_block_hours(employee)
            if target_hour >= closing_hour - 1:
                required_hours = min(required_hours, 4)
            if absolute_max_daily_hours - external_daily_hours < required_hours:
                continue
            block_start = _find_cover_block_start(
                employee,
                start_date,
                target_date,
                target_hour,
                required_hours,
                target_hour,
                closing_hour,
            )
            if block_start is None:
                continue
            proposed_hours = list(range(block_start, block_start + required_hours))
            if target_hour not in proposed_hours:
                continue
            if external_daily_hours + required_hours > preferred_max_daily_hours:
                continue
            if _has_severe_relation_conflict(relation_map, hour_index, emp_id, proposed_hours):
                continue

        if target_hour >= closing_hour - 1 and not (_closing_task_skill_count(employee) > 0 or _has_backroom_skill(employee)):
            continue
        return True

    return False


def _has_preferred_part_time_extension_candidate(
    *,
    employees: list,
    candidate_employee_id: str | None,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    target_hour: int,
    daily_blocks: dict,
    relation_map: dict,
    schedule_assignments: list[dict],
) -> bool:
    hour_index = _build_hour_index(schedule_assignments)
    for employee in employees:
        emp_id = str(employee.get("id"))
        if candidate_employee_id is not None and emp_id == candidate_employee_id:
            continue
        if not _is_part_time(employee):
            continue

        block = daily_blocks.get((date_key, emp_id))
        if block is None:
            continue
        current_start = int(block.get("start", target_hour))
        current_end = int(block.get("end", target_hour))
        if current_end + 1 != target_hour and current_start - 1 != target_hour:
            continue
        if not _is_available(employee, start_date, target_date, target_hour):
            continue
        if _has_severe_relation_conflict(relation_map, hour_index, emp_id, [target_hour]):
            continue

        meta = employee.get("meta", {})
        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        current_hours = current_end - current_start + 1
        preferred_max = _preferred_max_daily_hours(employee)
        absolute_max = _absolute_max_daily_hours(employee)
        if external_daily_hours + current_hours + 1 > preferred_max:
            continue
        if external_daily_hours + current_hours + 1 > absolute_max:
            continue
        return True

    return False


def _reassign_full_time_overtime_tail_hours(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    closing_hour: int,
) -> None:
    employee_map = {str(emp.get("id")): emp for emp in employees}
    changed = True
    while changed:
        changed = False
        hour_index = _build_hour_index(schedule_assignments)

        for emp in employees:
            emp_id = str(emp.get("id"))
            if not _is_full_time(emp):
                continue
            block = daily_blocks.get((date_key, emp_id))
            if block is None:
                continue

            current_start = int(block.get("start", closing_hour))
            current_end = int(block.get("end", closing_hour))
            current_hours = current_end - current_start + 1
            preferred_max_daily_hours = _preferred_max_daily_hours(emp)
            if current_hours <= preferred_max_daily_hours:
                continue

            target_hour = current_end
            if target_hour < closing_hour - 1:
                continue

            replacement_candidates = []
            for candidate in employees:
                candidate_id = str(candidate.get("id"))
                if candidate_id == emp_id or not _is_part_time(candidate):
                    continue

                candidate_block = daily_blocks.get((date_key, candidate_id))
                if candidate_block is None:
                    continue

                block_start = int(candidate_block.get("start", target_hour))
                block_end = int(candidate_block.get("end", target_hour))
                if block_end + 1 != target_hour and block_start - 1 != target_hour:
                    continue
                if not _is_available(candidate, start_date, date_obj, target_hour):
                    continue
                if _has_severe_relation_conflict(relation_map, hour_index, candidate_id, [target_hour], ignored_employee_ids={emp_id}):
                    continue

                meta = candidate.get("meta", {})
                external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
                candidate_hours = block_end - block_start + 1
                preferred_candidate_hours = _preferred_max_daily_hours(candidate)
                absolute_candidate_hours = _absolute_max_daily_hours(candidate)
                if external_daily_hours + candidate_hours + 1 > preferred_candidate_hours:
                    continue
                if external_daily_hours + candidate_hours + 1 > absolute_candidate_hours:
                    continue
                if target_hour >= closing_hour - 1 and not (_closing_task_skill_count(candidate) > 0 or _has_backroom_skill(candidate)):
                    continue

                score = 200.0
                score += max(0.0, 24.0 - float(store_priority.get(candidate_id, 99)) * 3.0)
                score += _closing_task_skill_count(candidate) * 40.0
                score += _nationality_priority_bonus(candidate)
                score -= assigned_hours.get(candidate_id, 0) * 3.0
                replacement_candidates.append((score, candidate))

            if not replacement_candidates:
                continue

            replacement = max(replacement_candidates, key=lambda item: item[0])[1]
            replacement_id = str(replacement.get("id"))

            removed = False
            for index, item in enumerate(schedule_assignments):
                if str(item.get("employee_id")) == emp_id and int(item.get("hour", 0)) == target_hour:
                    schedule_assignments.pop(index)
                    removed = True
                    break
            if not removed:
                continue

            schedule_assignments.append(
                {
                    "employee_id": replacement.get("id"),
                    "employee_name": replacement.get("name", "Unknown"),
                    "shift": _shift_name(target_hour),
                    "hour": target_hour,
                }
            )

            assigned_hours[emp_id] = max(0, assigned_hours.get(emp_id, 0) - 1)
            assigned_hours[replacement_id] = assigned_hours.get(replacement_id, 0) + 1

            if current_end == target_hour:
                block["end"] = target_hour - 1
            elif current_start == target_hour:
                block["start"] = target_hour + 1

            replacement_block = daily_blocks.get((date_key, replacement_id))
            if replacement_block is not None:
                if int(replacement_block.get("end", target_hour)) + 1 == target_hour:
                    replacement_block["end"] = target_hour
                    replacement_block["max_end"] = max(int(replacement_block.get("max_end", target_hour)), target_hour)
                elif int(replacement_block.get("start", target_hour)) - 1 == target_hour:
                    replacement_block["start"] = target_hour

            changed = True
            break


def _prune_redundant_overtime_tail_hours(
    *,
    employees: list,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    demand_by_day_hour: dict,
    required_per_hour: int,
    key_holder_ids: set[str],
    min_closing_keyholders: int,
    min_backroom_per_hour: int,
    closing_hour: int,
) -> None:
    employee_map = {str(emp.get("id")): emp for emp in employees}
    changed = True
    while changed:
        changed = False
        assignments_by_hour: dict[int, list[dict]] = {}
        for item in schedule_assignments:
            assignments_by_hour.setdefault(int(item.get("hour", 0)), []).append(item)

        overtime_candidates = []
        for (block_date, emp_id), block in list(daily_blocks.items()):
            if block_date != date_key:
                continue
            employee = employee_map.get(emp_id)
            if employee is None:
                continue
            current_start = int(block.get("start", closing_hour))
            current_end = int(block.get("end", closing_hour))
            current_hours = current_end - current_start + 1
            preferred_max = _preferred_max_daily_hours(employee)
            if current_hours <= preferred_max:
                continue
            overtime_candidates.append((current_end, current_start, emp_id, employee))

        overtime_candidates.sort(reverse=True)

        for current_end, current_start, emp_id, employee in overtime_candidates:
            target_hour = current_end
            if target_hour < closing_hour - 1:
                continue

            current_staff = assignments_by_hour.get(target_hour, [])
            target_staff = _hour_target(
                demand_by_day_hour,
                date_obj,
                target_hour,
                required_per_hour,
                allow_zero_demand=False,
            )
            if len(current_staff) <= target_staff:
                continue

            remaining_staff = [item for item in current_staff if str(item.get("employee_id")) != emp_id]
            if len(remaining_staff) < target_staff:
                continue

            remaining_keyholders = sum(1 for item in remaining_staff if str(item.get("employee_id")) in key_holder_ids)
            if target_hour >= closing_hour - 1 and remaining_keyholders < min_closing_keyholders:
                continue

            remaining_backroom = sum(
                1
                for item in remaining_staff
                if _has_backroom_skill(employee_map.get(str(item.get("employee_id")), {}))
            )
            if remaining_backroom < min_backroom_per_hour:
                continue

            removed = False
            for index, item in enumerate(schedule_assignments):
                if str(item.get("employee_id")) == emp_id and int(item.get("hour", 0)) == target_hour:
                    schedule_assignments.pop(index)
                    removed = True
                    break
            if not removed:
                continue

            assigned_hours_to_remove = 1
            block = daily_blocks.get((date_key, emp_id))
            if block is not None:
                if int(block.get("end", target_hour)) == target_hour:
                    block["end"] = target_hour - 1
                elif int(block.get("start", target_hour)) == target_hour:
                    block["start"] = target_hour + 1
                if int(block.get("start", target_hour + 1)) > int(block.get("end", target_hour - 1)):
                    daily_blocks.pop((date_key, emp_id), None)

            changed = True
            break


def _merge_redundant_part_time_tail_blocks(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    demand_by_day_hour: dict,
    required_per_hour: int,
) -> None:
    employee_map = {str(emp.get("id")): emp for emp in employees}
    changed = True
    while changed:
        changed = False
        assignments_by_hour: dict[int, list[dict]] = {}
        for item in schedule_assignments:
            assignments_by_hour.setdefault(int(item.get("hour", 0)), []).append(item)

        removable_blocks = []
        for (block_date, emp_id), block in list(daily_blocks.items()):
            if block_date != date_key:
                continue
            employee = employee_map.get(emp_id)
            if employee is None or not _is_part_time(employee):
                continue
            priority = float(store_priority.get(emp_id, 99))
            start_hour = int(block.get("start", 0))
            end_hour = int(block.get("end", -1))
            block_hours = end_hour - start_hour + 1
            if block_hours <= 0:
                continue
            if start_hour < 17:
                continue
            removable_blocks.append((priority, start_hour, end_hour, emp_id, employee))

        removable_blocks.sort(reverse=True)

        for _, remove_start, remove_end, remove_emp_id, remove_emp in removable_blocks:
            remove_hours = list(range(remove_start, remove_end + 1))
            donor_options = []

            for (block_date, donor_id), donor_block in list(daily_blocks.items()):
                if block_date != date_key or donor_id == remove_emp_id:
                    continue
                donor = employee_map.get(donor_id)
                if donor is None or not _is_part_time(donor):
                    continue
                donor_priority = float(store_priority.get(donor_id, 99))
                remove_priority = float(store_priority.get(remove_emp_id, 99))
                if donor_priority > remove_priority:
                    continue

                donor_start = int(donor_block.get("start", 0))
                donor_end = int(donor_block.get("end", -1))
                donor_current_hours = donor_end - donor_start + 1
                if donor_end >= remove_end:
                    continue
                if donor_end < remove_start - 1:
                    continue
                if donor_start >= remove_start:
                    continue

                extension_hours = list(range(max(donor_end + 1, remove_start), remove_end + 1))
                if not extension_hours:
                    continue
                if not all(_is_available(donor, start_date, date_obj, hour) for hour in extension_hours):
                    continue

                meta = donor.get("meta", {})
                external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
                preferred_max = _preferred_max_daily_hours(donor)
                absolute_max = _absolute_max_daily_hours(donor)
                if external_daily_hours + donor_current_hours + len(extension_hours) > preferred_max:
                    continue
                if external_daily_hours + donor_current_hours + len(extension_hours) > absolute_max:
                    continue

                hour_index = _build_hour_index(schedule_assignments)
                if _has_severe_relation_conflict(
                    relation_map,
                    hour_index,
                    donor_id,
                    extension_hours,
                    ignored_employee_ids={remove_emp_id},
                ):
                    continue

                can_replace = True
                for hour in remove_hours:
                    current_staff = assignments_by_hour.get(hour, [])
                    remaining_staff = [item for item in current_staff if str(item.get("employee_id")) != remove_emp_id]
                    if hour in extension_hours:
                        remaining_staff = remaining_staff + [{
                            "employee_id": donor.get("id"),
                            "employee_name": donor.get("name", "Unknown"),
                            "shift": _shift_name(hour),
                            "hour": hour,
                        }]
                    target_staff = _hour_target(
                        demand_by_day_hour,
                        date_obj,
                        hour,
                        required_per_hour,
                        allow_zero_demand=False,
                    )
                    if len(remaining_staff) < target_staff:
                        can_replace = False
                        break
                if not can_replace:
                    continue

                score = 200.0 - len(extension_hours) * 20.0
                score += _closing_task_skill_count(donor) * 30.0
                donor_options.append((score, donor, extension_hours))

            if not donor_options:
                continue

            _, donor, extension_hours = max(donor_options, key=lambda item: item[0])
            donor_id = str(donor.get("id"))

            schedule_assignments[:] = [
                item
                for item in schedule_assignments
                if str(item.get("employee_id")) != remove_emp_id
            ]
            daily_blocks.pop((date_key, remove_emp_id), None)
            assigned_hours[remove_emp_id] = 0

            for hour in extension_hours:
                schedule_assignments.append(
                    {
                        "employee_id": donor.get("id"),
                        "employee_name": donor.get("name", "Unknown"),
                        "shift": _shift_name(hour),
                        "hour": hour,
                    }
                )

            donor_block = daily_blocks.get((date_key, donor_id))
            if donor_block is not None:
                donor_block["end"] = max(int(donor_block.get("end", remove_end)), remove_end)
                donor_block["max_end"] = max(int(donor_block.get("max_end", remove_end)), remove_end)
            assigned_hours[donor_id] = assigned_hours.get(donor_id, 0) + len(extension_hours)

            changed = True
            break


def _availability_bounds(employee: dict, start_date: datetime, target_date: datetime) -> tuple[int, int] | None:
    row = _availability_row(employee, start_date, target_date)
    if row is None:
        return None
    start_h = _parse_hour(row.get("start_time", "00:00"))
    end_h = _parse_hour(row.get("end_time", "00:00"))
    return start_h, end_h


def _daily_required_headcount(
    demand_by_day_hour: dict,
    date_obj: datetime,
    hour_start: int,
    hour_end: int,
    required_per_hour: int,
    *,
    allow_zero_demand: bool = False,
) -> int:
    total = 0
    for hour in range(hour_start, hour_end + 1):
        total += _hour_target(
            demand_by_day_hour,
            date_obj,
            hour,
            required_per_hour,
            allow_zero_demand=allow_zero_demand,
        )
    return total


def _plan_full_time_rest_days(
    employees: list,
    *,
    start_date: datetime,
    cycle_days: int,
    hour_start: int,
    hour_end: int,
    demand_by_day_hour: dict,
    required_per_hour: int,
    allow_zero_demand_hours: bool,
    key_holder_ids: set[str],
    store_priority: dict,
) -> dict[str, str]:
    rest_days: dict[str, str] = {}
    rest_load_by_day: dict[str, int] = {}

    full_time_employees = [employee for employee in employees if _is_full_time(employee)]

    def _rest_sort_key(employee: dict) -> tuple[float, float]:
        strength = _employee_core_strength(
            employee,
            key_holder_ids=key_holder_ids,
            store_priority=store_priority,
        )
        preferred = _preferred_shift(employee)
        if preferred == "closing":
            return (1.0, -strength)
        if preferred == "opening":
            return (0.0, strength)
        return (0.5, strength)

    full_time_employees.sort(key=_rest_sort_key)

    for employee in full_time_employees:

        candidates: list[tuple[float, str]] = []
        for day_index in range(cycle_days):
            date_obj = start_date + timedelta(days=day_index)
            bounds = _availability_bounds(employee, start_date, date_obj)
            if bounds is None:
                continue

            available_start, available_end = bounds
            window_start = max(hour_start, available_start)
            window_end = min(hour_end + 1, available_end)
            if window_end - window_start <= 0:
                continue

            date_key = date_obj.strftime("%Y-%m-%d")
            demand_total = _daily_required_headcount(
                demand_by_day_hour,
                date_obj,
                hour_start,
                hour_end,
                required_per_hour,
                allow_zero_demand=allow_zero_demand_hours,
            )
            weekday = date_obj.weekday()
            weekday_penalty = 0.0 if weekday < 5 else 10000.0
            balancing_penalty = float(rest_load_by_day.get(date_key, 0)) * 1200.0
            preferred = _preferred_shift(employee)
            shift_bias = 0.0
            if preferred == "opening":
                shift_bias = weekday * 45.0
            elif preferred == "closing":
                shift_bias = max(0, 4 - weekday) * 45.0
            score = weekday_penalty + float(demand_total) + balancing_penalty + shift_bias + day_index * 0.1
            candidates.append((score, date_key))

        if candidates:
            candidates.sort()
            selected_day = candidates[0][1]
            rest_days[str(employee.get("id"))] = selected_day
            rest_load_by_day[selected_day] = rest_load_by_day.get(selected_day, 0) + 1

    return rest_days


def _full_time_can_start_new_day(
    employee: dict,
    *,
    date_key: str,
    full_time_rest_days: dict[str, str],
    full_time_work_days: dict[str, set[str]],
) -> bool:
    if not _is_full_time(employee):
        return True

    emp_id = str(employee.get("id"))
    if date_key == full_time_rest_days.get(emp_id):
        return False

    worked_days = full_time_work_days.get(emp_id, set())
    if date_key in worked_days:
        return True

    return len(worked_days) < 6


def _mark_employee_day_worked(
    employee_id: str,
    date_key: str,
    full_time_work_days: dict[str, set[str]],
) -> None:
    full_time_work_days.setdefault(str(employee_id), set()).add(date_key)


def _employee_core_strength(
    employee: dict,
    *,
    key_holder_ids: set[str],
    store_priority: dict,
) -> float:
    emp_id = str(employee.get("id"))
    meta = employee.get("meta", {})
    score = float(meta.get("work_skill_score", 50)) * 1.2
    score += float(meta.get("management_skill_score", 50)) * 1.0
    if emp_id in key_holder_ids:
        score += 40.0
    prio = store_priority.get(emp_id)
    if prio is not None:
        score += max(0.0, 18.0 - float(prio) * 2.5)
    preferred = _preferred_shift(employee)
    if preferred == "opening":
        score += 10.0
    elif preferred == "closing":
        score += 10.0
    return score


def _store_priority_bonus(employee: dict, store_priority: dict) -> float:
    emp_id = str(employee.get("id"))
    prio = store_priority.get(emp_id)
    if prio is None:
        return 0.0
    if _is_part_time(employee):
        return 68.0 - float(prio) * 22.0
    return 42.0 - float(prio) * 7.0


def _store_priority_value(employee: dict, store_priority: dict) -> float:
    emp_id = str(employee.get("id"))
    prio = store_priority.get(emp_id)
    if prio is None:
        return 99.0
    return float(prio)


def _filter_candidates_by_priority_band(candidates: list[tuple], store_priority: dict, *, employee_index: int = 1) -> list[tuple]:
    if len(candidates) <= 1:
        return candidates

    priority_pairs = []
    for item in candidates:
        if len(item) <= employee_index:
            continue
        employee = item[employee_index]
        priority_pairs.append((item, _store_priority_value(employee, store_priority)))

    if not priority_pairs:
        return candidates

    best_priority = min(priority for _, priority in priority_pairs)
    band = [item for item, priority in priority_pairs if priority <= best_priority + 1.0]
    return band or candidates


def _monthly_hours_bonus(employee: dict) -> float:
    monthly_hours = float(employee.get("meta", {}).get("monthly_worked_hours", 0.0) or 0.0)
    if _is_part_time(employee):
        return max(-40.0, 72.0 - monthly_hours * 0.9)
    return max(-20.0, 20.0 - max(0.0, monthly_hours - 120.0) * 0.15)


def _availability_scarcity_bonus(employee: dict) -> float:
    if not _is_part_time(employee):
        return 0.0

    windows = employee.get("meta", {}).get("availability_windows", []) or []
    weekly_windows = [row for row in windows if int(row.get("week_offset", 0)) == 0]
    if not weekly_windows:
        return 0.0

    available_days = set()
    total_hours = 0
    for row in weekly_windows:
        day_of_week = int(row.get("day_of_week", -1))
        start_h = _parse_hour(row.get("start_time", "00:00"))
        end_h = _parse_hour(row.get("end_time", "00:00"))
        if end_h <= start_h:
            continue
        available_days.add(day_of_week)
        total_hours += end_h - start_h

    day_bonus = max(0.0, 7.0 - float(len(available_days))) * 12.0
    hour_bonus = max(0.0, 42.0 - float(total_hours)) * 1.2
    return min(90.0, day_bonus + hour_bonus)


def _availability_fit_bonus(
    employee: dict,
    *,
    start_date: datetime,
    target_date: datetime,
    block_start: int,
    block_end: int,
    hour_start: int,
    hour_end: int,
    template_kind: str,
) -> float:
    bounds = _availability_bounds(employee, start_date, target_date)
    if bounds is None:
        return -1000.0

    available_start, available_end = bounds
    window_start = max(hour_start, available_start)
    window_end = min(hour_end + 1, available_end)
    block_end_exclusive = block_end + 1
    if block_start < window_start or block_end_exclusive > window_end:
        return -1000.0

    prefix_slack = max(0, block_start - window_start)
    suffix_slack = max(0, window_end - block_end_exclusive)
    total_slack = prefix_slack + suffix_slack
    bonus = 0.0

    if _is_part_time(employee):
        bonus -= float(total_slack) * 7.0
        if template_kind in {"close_peak_part_time", "peak_part_time", "weekend_peak_part_time"}:
            if block_end >= hour_end - 1:
                bonus += 34.0
                bonus -= abs(window_end - (hour_end + 1)) * 5.0
                if window_start >= max(hour_start, block_start - 2):
                    bonus += 18.0
                if template_kind == "close_peak_part_time":
                    bonus -= max(0, prefix_slack - 2) * 8.0
        elif template_kind == "lunch_peak_part_time":
            bonus += 12.0
            bonus -= abs(window_start - block_start) * 4.0
        else:
            bonus -= abs(window_start - block_start) * 2.0
    else:
        bonus -= float(total_slack) * 2.0
        if template_kind in {"opening_core", "full_day_core"} and window_start <= hour_start:
            bonus += 20.0
        if template_kind in {"closing_core", "mid_close_core", "full_day_core"} and window_end >= hour_end + 1:
            bonus += 20.0

    preferred = _preferred_shift(employee)
    if preferred == "closing" and block_end >= hour_end - 1:
        bonus += 18.0
    elif preferred == "opening" and block_start <= hour_start + 1:
        bonus += 18.0
    elif preferred == "midday" and hour_start + 2 <= block_start <= hour_end - 4:
        bonus += 12.0

    return bonus


def _block_role_bucket(
    employee: dict,
    *,
    block_start: int,
    block_end: int,
    opening_hour: int,
    closing_hour: int,
) -> str:
    span = block_end - block_start + 1
    if _is_part_time(employee) and span <= 6:
        if block_end >= closing_hour - 1:
            return "part_time_closing"
        if block_start <= opening_hour + 1:
            return "part_time_opening"
        return "part_time_mid"

    if block_start <= opening_hour and block_end >= closing_hour - 2:
        return "full_day"
    if block_start <= opening_hour + 1:
        return "opening"
    if block_end >= closing_hour - 1:
        return "closing"
    return "mid"


def _role_balance_bonus(
    employee: dict,
    *,
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
    role_counts_by_employee: dict[str, dict[str, int]],
) -> float:
    emp_id = str(employee.get("id"))
    counts = role_counts_by_employee.get(emp_id, {})
    current_role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )
    bonus = 0.0
    if current_role == "opening":
        bonus -= float(counts.get("opening", 0)) * 32.0
    elif current_role == "closing":
        bonus -= float(counts.get("closing", 0)) * 28.0
    elif current_role == "full_day":
        bonus -= float(counts.get("opening", 0) + counts.get("closing", 0)) * 12.0
    elif current_role == "part_time_closing":
        bonus -= float(counts.get("part_time_closing", 0)) * 18.0
    return bonus


def _build_full_time_role_targets(
    employees: list,
    *,
    start_date: datetime,
    cycle_days: int,
    hour_start: int,
    hour_end: int,
) -> dict[str, dict[str, float]]:
    full_time_employees = [employee for employee in employees if _is_full_time(employee)]
    targets: dict[str, dict[str, float]] = {
        str(emp.get("id")): {"opening": 0.0, "closing": 0.0} for emp in full_time_employees
    }

    for employee in full_time_employees:
        emp_id = str(employee.get("id"))
        open_days = 0
        close_days = 0
        available_days = 0
        for day_index in range(cycle_days):
            date_obj = start_date + timedelta(days=day_index)
            bounds = _availability_bounds(employee, start_date, date_obj)
            if bounds is None:
                continue
            available_start, available_end = bounds
            can_open = available_start <= hour_start
            can_close = available_end >= hour_end
            if can_open or can_close:
                available_days += 1
            if can_open:
                open_days += 1
            if can_close:
                close_days += 1

        target_work_days = float(min(6, max(open_days, close_days, available_days)))
        if target_work_days <= 0:
            continue

        open_ratio = 0.5
        preferred = _preferred_shift(employee)
        if preferred == "opening":
            open_ratio = 0.54
        elif preferred == "closing":
            open_ratio = 0.46
        elif preferred == "midday":
            open_ratio = 0.49

        if open_days <= 0:
            open_ratio = 0.0
        elif close_days <= 0:
            open_ratio = 1.0

        opening_target = target_work_days * open_ratio
        closing_target = target_work_days * (1.0 - open_ratio)

        if open_days > 0:
            opening_target = min(opening_target, float(open_days))
        else:
            opening_target = 0.0
        if close_days > 0:
            closing_target = min(closing_target, float(close_days))
        else:
            closing_target = 0.0

        remaining = target_work_days - (opening_target + closing_target)
        if remaining > 0:
            if close_days - closing_target > open_days - opening_target:
                closing_target += remaining
            else:
                opening_target += remaining

        targets[emp_id]["opening"] = opening_target
        targets[emp_id]["closing"] = closing_target

    return targets


def _build_full_time_daily_role_plan(
    employees: list,
    *,
    start_date: datetime,
    cycle_days: int,
    hour_start: int,
    hour_end: int,
    full_time_rest_days: dict[str, str],
    role_targets_by_employee: dict[str, dict[str, float]],
) -> dict[str, dict[str, str]]:
    plan: dict[str, dict[str, str]] = {}
    full_time_employees = [employee for employee in employees if _is_full_time(employee)]
    previous_role_by_employee: dict[str, str | None] = {str(employee.get("id")): None for employee in full_time_employees}
    remaining_targets: dict[str, dict[str, int]] = {
        str(employee.get("id")): {
            "opening": max(0, int(round(float(role_targets_by_employee.get(str(employee.get("id")), {}).get("opening", 0.0))))),
            "closing": max(0, int(round(float(role_targets_by_employee.get(str(employee.get("id")), {}).get("closing", 0.0))))),
        }
        for employee in full_time_employees
    }
    for employee in full_time_employees:
        plan[str(employee.get("id"))] = {}

    for day_index in range(cycle_days):
        date_obj = start_date + timedelta(days=day_index)
        date_key = date_obj.strftime("%Y-%m-%d")
        day_candidates = []
        for employee in full_time_employees:
            emp_id = str(employee.get("id"))
            if full_time_rest_days.get(emp_id) == date_key:
                plan[emp_id][date_key] = "rest"
                previous_role_by_employee[emp_id] = "rest"
                continue
            bounds = _availability_bounds(employee, start_date, date_obj)
            if bounds is None:
                plan[emp_id][date_key] = "off"
                previous_role_by_employee[emp_id] = "off"
                continue
            available_start, available_end = bounds
            can_open = available_start <= hour_start
            can_close = available_end >= hour_end
            if not can_open and not can_close:
                plan[emp_id][date_key] = "off"
                previous_role_by_employee[emp_id] = "off"
                continue
            day_candidates.append((employee, can_open, can_close))

        working_count = len(day_candidates)
        opening_slots = 1 if working_count >= 1 else 0
        closing_slots = 2 if working_count >= 3 else (1 if working_count >= 1 else 0)

        opening_rank = []
        closing_rank = []
        for employee, can_open, can_close in day_candidates:
            emp_id = str(employee.get("id"))
            prev_role = previous_role_by_employee.get(emp_id)
            open_need = remaining_targets[emp_id]["opening"]
            close_need = remaining_targets[emp_id]["closing"]
            preferred = _preferred_shift(employee)
            core_strength = _employee_core_strength(
                employee,
                key_holder_ids=set(),
                store_priority={},
            )
            if can_open:
                score = open_need * 40.0
                if preferred == "opening":
                    score += 10.0
                if prev_role == "closing":
                    score += 18.0
                if prev_role == "opening":
                    score -= 28.0
                if day_index == cycle_days - 1:
                    if preferred == "opening":
                        score += 28.0
                    elif preferred == "closing":
                        score -= 8.0
                tie_strength = core_strength if preferred == "opening" else -core_strength
                opening_rank.append((score, tie_strength, emp_id))
            if can_close:
                score = close_need * 34.0
                if preferred == "closing":
                    score += 10.0
                if prev_role == "opening":
                    score += 18.0
                if prev_role == "closing":
                    score -= 22.0
                closing_rank.append((score, emp_id))

        opening_rank.sort(reverse=True)
        closing_rank.sort(reverse=True)
        selected_opening = {emp_id for _, _, emp_id in opening_rank[:opening_slots]}
        selected_closing = []
        for _, emp_id in closing_rank:
            if emp_id in selected_opening and working_count > 2:
                continue
            selected_closing.append(emp_id)
            if len(selected_closing) >= closing_slots:
                break
        selected_closing_set = set(selected_closing)

        for employee, can_open, can_close in day_candidates:
            emp_id = str(employee.get("id"))
            role = "flex"
            if emp_id in selected_opening:
                role = "opening"
                remaining_targets[emp_id]["opening"] = max(0, remaining_targets[emp_id]["opening"] - 1)
            elif emp_id in selected_closing_set:
                role = "closing"
                remaining_targets[emp_id]["closing"] = max(0, remaining_targets[emp_id]["closing"] - 1)
            elif can_close and not can_open:
                role = "closing"
            elif can_open and not can_close:
                role = "opening"
            plan[emp_id][date_key] = role
            previous_role_by_employee[emp_id] = role

    return plan


def _daily_role_plan_bonus(
    employee: dict,
    *,
    date_key: str,
    full_time_daily_role_plan: dict[str, dict[str, str]],
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
) -> float:
    if not _is_full_time(employee):
        return 0.0

    emp_id = str(employee.get("id"))
    target_role = full_time_daily_role_plan.get(emp_id, {}).get(date_key)
    if not target_role or target_role in {"rest", "off"}:
        return 0.0

    current_role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )
    if target_role == "opening":
        if current_role == "opening":
            return 42.0
        if current_role in {"closing", "part_time_closing"}:
            return -28.0
    elif target_role == "closing":
        if current_role == "closing":
            return 42.0
        if current_role == "opening":
            return -28.0
    elif target_role == "flex":
        if current_role in {"mid", "full_day"}:
            return 16.0
    return 0.0


def _role_plan_matches_template(
    target_role: str | None,
    template_kind: str,
) -> bool:
    if not target_role or target_role in {"flex", "rest", "off"}:
        return True
    if target_role == "opening":
        return template_kind in {"opening_core", "full_day_core", "swing_core"}
    if target_role == "closing":
        return template_kind in {"closing_core", "mid_close_core", "full_day_core", "swing_core"}
    return True


def _sole_keyholder_shift_bonus(
    employee: dict,
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    full_time_rest_days: dict[str, str],
    key_holder_ids: set[str],
    template_kind: str,
    hour_start: int,
    hour_end: int,
) -> float:
    emp_id = str(employee.get("id"))
    if emp_id not in key_holder_ids:
        return 0.0
    if template_kind not in {"opening_core", "closing_core", "mid_close_core", "full_day_core"}:
        return 0.0

    available_keyholders = 0
    for candidate in employees:
        candidate_id = str(candidate.get("id"))
        if candidate_id not in key_holder_ids:
            continue
        if full_time_rest_days.get(candidate_id) == date_key:
            continue
        bounds = _availability_bounds(candidate, start_date, date_obj)
        if bounds is None:
            continue
        available_start, available_end = bounds
        if available_end >= hour_end:
            available_keyholders += 1

    if available_keyholders != 1:
        return 0.0
    if template_kind in {"closing_core", "mid_close_core", "full_day_core"}:
        return 42.0
    if template_kind == "opening_core":
        return -36.0
    return 0.0


def _role_target_bonus(
    employee: dict,
    *,
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
    role_counts_by_employee: dict[str, dict[str, int]],
    role_targets_by_employee: dict[str, dict[str, float]],
) -> float:
    emp_id = str(employee.get("id"))
    current_role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )
    targets = role_targets_by_employee.get(emp_id, {})
    counts = role_counts_by_employee.get(emp_id, {})
    if current_role == "opening":
        opening_gap = float(targets.get("opening", 0.0)) - float(counts.get("opening", 0))
        return opening_gap * (82.0 if opening_gap >= 0 else 138.0)
    if current_role == "closing":
        closing_gap = float(targets.get("closing", 0.0)) - float(counts.get("closing", 0))
        return closing_gap * (74.0 if closing_gap >= 0 else 128.0)
    if current_role == "full_day":
        opening_gap = float(targets.get("opening", 0.0)) - float(counts.get("opening", 0))
        closing_gap = float(targets.get("closing", 0.0)) - float(counts.get("closing", 0))
        return opening_gap * 18.0 + closing_gap * 18.0
    return 0.0


def _role_rotation_bonus(
    employee: dict,
    *,
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
    role_counts_by_employee: dict[str, dict[str, int]],
    employees: list,
) -> float:
    emp_id = str(employee.get("id"))
    current_role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )

    if current_role not in {"opening", "closing", "full_day", "part_time_closing"}:
        return 0.0

    if _is_full_time(employee):
        peer_ids = [str(item.get("id")) for item in employees if _is_full_time(item)]
    else:
        peer_ids = [str(item.get("id")) for item in employees if _is_part_time(item)]

    if not peer_ids:
        return 0.0

    if current_role == "full_day":
        peer_values = [
            int(role_counts_by_employee.get(peer_id, {}).get("opening", 0))
            + int(role_counts_by_employee.get(peer_id, {}).get("closing", 0))
            for peer_id in peer_ids
        ]
        own_value = (
            int(role_counts_by_employee.get(emp_id, {}).get("opening", 0))
            + int(role_counts_by_employee.get(emp_id, {}).get("closing", 0))
        )
        gap = min(peer_values) - own_value if peer_values else 0
        return float(gap) * 26.0

    peer_values = [
        int(role_counts_by_employee.get(peer_id, {}).get(current_role, 0))
        for peer_id in peer_ids
    ]
    own_value = int(role_counts_by_employee.get(emp_id, {}).get(current_role, 0))
    gap = min(peer_values) - own_value if peer_values else 0
    if current_role == "opening":
        return float(gap) * 42.0
    if current_role == "closing":
        return float(gap) * 38.0
    return float(gap) * 24.0


def _rest_rebound_bonus(
    employee: dict,
    *,
    date_obj: datetime,
    full_time_rest_days: dict[str, str],
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
) -> float:
    if not _is_full_time(employee):
        return 0.0

    emp_id = str(employee.get("id"))
    previous_date_key = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
    if full_time_rest_days.get(emp_id) != previous_date_key:
        return 0.0

    role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )
    if role == "opening":
        return -70.0
    if role in {"closing", "mid", "full_day"}:
        return 24.0
    return 8.0


def _role_continuity_bonus(
    employee: dict,
    *,
    proposed_start: int,
    proposed_end: int,
    opening_hour: int,
    closing_hour: int,
    previous_role: str | None,
) -> float:
    current_role = _block_role_bucket(
        employee,
        block_start=proposed_start,
        block_end=proposed_end,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
    )
    bonus = 0.0
    if previous_role and current_role == previous_role:
        if _is_full_time(employee):
            if current_role in {"opening", "closing", "full_day"}:
                bonus -= 48.0
            else:
                bonus += 4.0
        else:
            bonus += 10.0

    preferred = _preferred_shift(employee)
    if preferred == "opening" and current_role in {"opening", "full_day"}:
        bonus += 58.0
    elif preferred == "closing" and current_role in {"closing", "full_day", "part_time_closing"}:
        bonus += 58.0
    elif preferred == "midday" and current_role in {"mid", "part_time_mid"}:
        bonus += 42.0
    elif preferred not in {"", "no_preference", "flex", "flexible"}:
        bonus -= 8.0

    if _is_full_time(employee) and current_role in {"opening", "closing", "full_day"}:
        bonus += 28.0
    if _is_part_time(employee) and current_role in {"part_time_opening", "part_time_mid", "part_time_closing"}:
        bonus += 16.0
    return bonus


def _nationality_priority_bonus(employee: dict) -> float:
    nationality = str(employee.get("meta", {}).get("nationality_status", "")).lower()
    if nationality == "sg_citizen":
        return 42.0
    if nationality == "sg_pr":
        return 28.0
    return 0.0


def _skill_level_value(level: str) -> float:
    normalized = str(level or "").strip().lower()
    if normalized == "proficient":
        return 1.0
    if normalized == "basic":
        return 0.55
    return 0.0


def _employee_skill_levels(employee: dict) -> dict[str, str]:
    meta = employee.get("meta", {})
    skill_levels = dict(meta.get("skill_levels", {}) or {})
    if "backroom" not in skill_levels and meta.get("backroom_level"):
        skill_levels["backroom"] = str(meta.get("backroom_level"))
    return {str(code).lower(): str(level).lower() for code, level in skill_levels.items()}


FRONT_SKILL_CODES = {"front_service", "cashier", "floor", "customer_service"}
BACKROOM_SKILL_CODES = {"backroom", "inventory"}
CLOSING_TASK_SKILL_CODES = {
    "close_backroom_clean",
    "close_machine_clean",
    "close_settlement",
}


def _has_any_skill(employee: dict, skill_codes: set[str]) -> bool:
    skill_levels = _employee_skill_levels(employee)
    return any(_skill_level_value(skill_levels.get(code, "none")) > 0 for code in skill_codes)


def _has_all_skills(employee: dict, skill_codes: set[str]) -> bool:
    skill_levels = _employee_skill_levels(employee)
    return all(_skill_level_value(skill_levels.get(code, "none")) > 0 for code in skill_codes)


def _has_front_skill(employee: dict) -> bool:
    return _has_any_skill(employee, FRONT_SKILL_CODES)


def _has_backroom_skill(employee: dict) -> bool:
    return _has_any_skill(employee, BACKROOM_SKILL_CODES)


def _is_opening_qualified(employee: dict) -> bool:
    return _has_front_skill(employee) and _has_backroom_skill(employee)


def _closing_task_skill_count(employee: dict) -> int:
    skill_levels = _employee_skill_levels(employee)
    return sum(1 for code in CLOSING_TASK_SKILL_CODES if _skill_level_value(skill_levels.get(code, "none")) > 0)


def _closing_support_skill_score(employee: dict) -> float:
    skill_levels = _employee_skill_levels(employee)
    weighted = 0.0

    closing_task_weights = {
        "close_backroom_clean": 1.2,
        "close_machine_clean": 1.0,
        "close_settlement": 1.0,
    }
    for skill_code, weight in closing_task_weights.items():
        weighted += _skill_level_value(skill_levels.get(skill_code, "none")) * weight

    weighted += _skill_level_value(skill_levels.get("backroom", "none")) * 0.9
    weighted += _skill_level_value(skill_levels.get("inventory", "none")) * 0.45
    weighted += _skill_level_value(skill_levels.get("floor", "none")) * 0.55
    weighted += _skill_level_value(skill_levels.get("cashier", "none")) * 0.35
    weighted += _skill_level_value(skill_levels.get("front_service", "none")) * 0.25
    return weighted


def _late_close_part_time_bonus(employee: dict, store_priority: dict) -> float:
    if not _is_part_time(employee):
        return 0.0

    prio = _store_priority_value(employee, store_priority)
    closing_task_count = _closing_task_skill_count(employee)
    support_skill_score = _closing_support_skill_score(employee)

    score = support_skill_score * 48.0 + closing_task_count * 42.0
    if prio <= 2.0:
        score += 70.0
    elif prio >= 4.0:
        score -= 150.0
    else:
        score -= max(0.0, prio - 2.0) * 35.0

    if closing_task_count == 0:
        score -= 55.0
    if not _has_backroom_skill(employee) and closing_task_count == 0:
        score -= 40.0

    return score

def _preferred_shift(employee: dict) -> str:
    preferences = employee.get("preferences", {}) or {}
    preferred = preferences.get("preferred_shift")
    if not preferred:
        preferred = employee.get("meta", {}).get("preferred_shift", "no_preference")
    return str(preferred or "no_preference").strip().lower()


def _preferred_shift_bonus(employee: dict, template_kind: str, shift_role: str) -> float:
    preferred = _preferred_shift(employee)
    if preferred in {"", "no_preference", "flex", "flexible"}:
        return 0.0

    match_map = {
        "opening": {"opening_core", "full_day_core", "opening_core"},
        "midday": {"swing_core", "full_day_core"},
        "closing": {"closing_core", "swing_core", "full_day_core"},
    }
    mismatch_map = {
        "opening": {"closing_core"},
        "midday": {"opening_core", "closing_core"},
        "closing": {"opening_core"},
    }

    target_tags = match_map.get(preferred, set())
    mismatch_tags = mismatch_map.get(preferred, set())
    tags = {template_kind, shift_role}
    if tags & target_tags:
        return 52.0
    if tags & mismatch_tags:
        return -24.0
    return 0.0


def _template_skill_score(employee: dict, template_kind: str) -> float:
    skill_levels = _employee_skill_levels(employee)
    preferred_skills_map = {
        "full_day_core": ("cashier", "backroom", "floor"),
        "opening_core": ("backroom", "inventory", "cashier"),
        "closing_core": ("cashier", "customer_service", "inventory"),
        "swing_core": ("cashier", "floor", "customer_service"),
        "mid_close_core": ("cashier", "customer_service", "inventory"),
        "lunch_peak_part_time": ("floor", "customer_service", "cashier"),
        "peak_part_time": ("cashier", "floor", "customer_service"),
        "close_peak_part_time": ("close_backroom_clean", "close_machine_clean", "close_settlement", "backroom", "floor"),
        "weekend_peak_part_time": ("floor", "cashier", "customer_service"),
    }
    preferred_skills = preferred_skills_map.get(str(template_kind), ("cashier", "floor"))
    weighted = 0.0
    for index, skill_code in enumerate(preferred_skills):
        level_value = _skill_level_value(skill_levels.get(skill_code, "none"))
        weighted += level_value * max(0.3, 1.0 - index * 0.2)

    if weighted > 0:
        return weighted * 90.0

    work_score = int(employee.get("meta", {}).get("work_skill_score", 50))
    return work_score * 0.35


def _analyze_store_day_profile(
    date_obj: datetime,
    hour_start: int,
    hour_end: int,
    demand_by_day_hour: dict,
    required_per_hour: int,
    *,
    allow_zero_demand: bool = False,
) -> dict:
    hourly_targets = {
        hour: _hour_target(
            demand_by_day_hour,
            date_obj,
            hour,
            required_per_hour,
            allow_zero_demand=allow_zero_demand,
        )
        for hour in range(hour_start, hour_end + 1)
    }
    open_hours = max(1, hour_end - hour_start + 1)
    total_demand_hours = sum(hourly_targets.values())
    overall_peak = max(hourly_targets.values(), default=required_per_hour)
    opening_target = hourly_targets.get(hour_start, required_per_hour)
    closing_target = hourly_targets.get(hour_end, required_per_hour)
    midday_anchor = max(hour_start, min(hour_end, hour_start + open_hours // 2))
    midday_peak = max(
        (hourly_targets.get(hour, 0) for hour in range(max(hour_start, midday_anchor - 1), min(hour_end, midday_anchor + 2) + 1)),
        default=0,
    )
    late_anchor = max(hour_start, min(hour_end, hour_end - 2))
    late_peak = max(
        (hourly_targets.get(hour, 0) for hour in range(max(hour_start, late_anchor - 1), hour_end + 1)),
        default=0,
    )
    avg_target = total_demand_hours / float(open_hours)

    return {
        "hourly_targets": hourly_targets,
        "open_hours": open_hours,
        "total_demand_hours": total_demand_hours,
        "overall_peak": overall_peak,
        "opening_target": opening_target,
        "closing_target": closing_target,
        "midday_peak": midday_peak,
        "late_peak": late_peak,
        "avg_target": avg_target,
        "is_weekend": date_obj.weekday() >= 5,
    }


def _resolve_min_closing_staff(
    *,
    store_archetype: str | None,
    rules: dict,
    profile: dict,
) -> int:
    explicit_override = rules.get("min_closing_staff")
    if explicit_override is not None:
        try:
            return max(1, int(explicit_override))
        except Exception:
            pass

    archetype = str(store_archetype or "auto").strip().lower()
    if archetype == "peak_dual_core":
        return 3
    if archetype == "light_single_core":
        return 1

    open_hours = int(profile.get("open_hours", 0))
    late_peak = int(profile.get("late_peak", 1))
    closing_target = int(profile.get("closing_target", 1))
    overall_peak = int(profile.get("overall_peak", 1))

    if open_hours >= 13 and (late_peak >= 3 or closing_target >= 3 or overall_peak >= 4):
        return 3
    if open_hours >= 11 and (late_peak >= 2 or closing_target >= 2):
        return 2
    return 1


def _select_store_mode(profile: dict, store_archetype: str | None = None) -> str:
    archetype = str(store_archetype or "auto").strip().lower()
    if archetype == "peak_dual_core":
        return "high_intensity_multi_support"
    if archetype == "light_single_core":
        return "light_single_core"

    open_hours = int(profile["open_hours"])
    total_demand_hours = int(profile["total_demand_hours"])
    overall_peak = int(profile["overall_peak"])
    avg_target = float(profile["avg_target"])
    closing_target = int(profile["closing_target"])
    midday_peak = int(profile["midday_peak"])
    late_peak = int(profile["late_peak"])

    if (
        overall_peak <= 2
        and avg_target <= 1.7
        and total_demand_hours <= max(22, open_hours * 2)
    ):
        return "light_single_core"

    if (
        overall_peak >= 4
        or avg_target >= 2.6
        or total_demand_hours >= open_hours * 3
        or (closing_target >= 3 and late_peak >= 3)
        or (midday_peak >= 3 and late_peak >= 3)
    ):
        return "high_intensity_multi_support"

    return "standard_dual_core"


def _infer_shift_role(
    employee: dict,
    *,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    hour_start: int,
    hour_end: int,
    key_holder_ids: set[str],
) -> str:
    emp_id = str(employee.get("id"))
    meta = employee.get("meta", {})
    bounds = _availability_bounds(employee, start_date, target_date)
    if bounds is None:
        return "unavailable"

    available_start, available_end = bounds
    if date_key in set(meta.get("external_store_days", [])):
        return "external"

    can_open = available_start <= hour_start
    can_close = available_end >= hour_end
    if _is_full_time(employee) and can_open and can_close:
        return "full_time_flex"
    if emp_id in key_holder_ids and can_close:
        return "closing_core"
    if _is_full_time(employee) and can_open:
        return "opening_core"
    if _is_full_time(employee) and can_close and available_start <= hour_start + 4:
        return "mid_close_core"
    if _is_full_time(employee) and can_close:
        return "closing_core"
    if _is_full_time(employee) and available_start <= 12 and available_end >= hour_end - 1:
        return "swing_core"
    if _is_part_time(employee) and available_start <= 12 and available_end >= 16:
        return "lunch_peak"
    if _is_part_time(employee) and available_start <= 15 and available_end >= 19:
        return "mid_peak"
    if _is_part_time(employee) and available_end >= hour_end and available_start <= 19:
        return "close_peak"
    return "flex"


def _can_assign_block(
    employee: dict,
    start_date: datetime,
    target_date: datetime,
    date_key: str,
    block_start: int,
    block_hours: int,
    daily_blocks: dict,
) -> bool:
    if block_hours <= 0:
        return False

    emp_id = str(employee.get("id"))
    meta = employee.get("meta", {})
    external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
    absolute_max_daily_hours = _absolute_max_daily_hours(employee)
    existing_block = daily_blocks.get((date_key, emp_id))
    if existing_block is not None:
        return False
    if external_daily_hours + block_hours > absolute_max_daily_hours:
        return False

    blocked_slots = set(meta.get("blocked_slots", []))
    for hour in range(block_start, block_start + block_hours):
        if not _is_available(employee, start_date, target_date, hour):
            return False
        if f"{date_key}|{hour}" in blocked_slots:
            return False

    return True


def _apply_block(
    schedule_assignments: list[dict],
    employee: dict,
    date_key: str,
    block_start: int,
    block_hours: int,
    daily_blocks: dict,
    assigned_hours: dict,
    daily_assigned_hours: dict,
    block_kind: str | None = None,
    block_max_end: int | None = None,
) -> None:
    emp_id = str(employee.get("id"))
    for hour in range(block_start, block_start + block_hours):
        schedule_assignments.append(
            {
                "employee_id": employee.get("id"),
                "employee_name": employee.get("name", "Unknown"),
                "shift": _shift_name(hour),
                "hour": hour,
            }
        )

    assigned_hours[emp_id] = assigned_hours.get(emp_id, 0) + block_hours
    daily_assigned_hours[date_key] = daily_assigned_hours.get(date_key, 0.0) + float(block_hours)
    daily_blocks[(date_key, emp_id)] = {
        "start": block_start,
        "end": block_start + block_hours - 1,
        "kind": block_kind,
        "max_end": block_max_end if block_max_end is not None else block_start + block_hours - 1,
    }


def _template_candidate_score(
    employee: dict,
    *,
    template_kind: str,
    assigned_hours: dict,
    store_priority: dict,
    key_holder_ids: set[str],
    date_key: str,
    shift_role: str,
) -> float:
    emp_id = str(employee.get("id"))
    meta = employee.get("meta", {})
    score = 100.0 - assigned_hours.get(emp_id, 0) * 4.0
    score += _store_priority_bonus(employee, store_priority)
    score += _monthly_hours_bonus(employee)
    score += int(meta.get("work_skill_score", 50)) * 0.35
    score += int(meta.get("management_skill_score", 50)) * 0.2
    score += _nationality_priority_bonus(employee)
    score += _availability_scarcity_bonus(employee)
    score += _template_skill_score(employee, template_kind) * 0.9

    if meta.get("sg_priority_to_80"):
        score += 60.0
    if meta.get("sg_priority_to_160"):
        score += 20.0

    if template_kind == "full_day_core":
        if _is_full_time(employee):
            score += 260.0
        if emp_id in key_holder_ids:
            score += 120.0
        if _is_opening_qualified(employee):
            score += 120.0
        else:
            score -= 950.0
        score += 160.0
    elif template_kind == "opening_core":
        if _is_full_time(employee):
            score += 250.0
        if _is_opening_qualified(employee):
            score += 140.0
        else:
            score -= 950.0
        if emp_id in key_holder_ids:
            score += 140.0
        score += 150.0
    elif template_kind == "closing_core":
        if _is_full_time(employee):
            score += 255.0
        if emp_id in key_holder_ids:
            score += 210.0
        score += _closing_task_skill_count(employee) * 42.0
        score += 170.0
    elif template_kind == "swing_core":
        if _is_full_time(employee):
            score += 225.0
        score += 135.0
    elif template_kind == "mid_close_core":
        if _is_full_time(employee):
            score += 240.0
        if emp_id in key_holder_ids:
            score += 90.0
        score += _closing_task_skill_count(employee) * 38.0
        score += 160.0
    else:
        if _is_part_time(employee):
            score += 180.0
            if template_kind in {"close_peak_part_time", "weekend_peak_part_time", "peak_part_time"}:
                score += _closing_task_skill_count(employee) * 46.0
                score += _late_close_part_time_bonus(employee, store_priority) * 0.35
            if template_kind in {"lunch_peak_part_time", "peak_part_time", "weekend_peak_part_time"} and _has_backroom_skill(employee):
                score += 36.0
        else:
            score -= 40.0

    role_bonus_map = {
        ("full_day_core", "full_time_flex"): 260.0,
        ("full_day_core", "full_day_core"): 320.0,
        ("full_day_core", "opening_core"): 160.0,
        ("full_day_core", "closing_core"): 160.0,
        ("opening_core", "full_time_flex"): 240.0,
        ("opening_core", "opening_core"): 260.0,
        ("closing_core", "full_time_flex"): 300.0,
        ("closing_core", "closing_core"): 300.0,
        ("swing_core", "full_time_flex"): 240.0,
        ("swing_core", "swing_core"): 260.0,
        ("swing_core", "opening_core"): 120.0,
        ("swing_core", "closing_core"): 120.0,
        ("mid_close_core", "full_time_flex"): 260.0,
        ("mid_close_core", "closing_core"): 260.0,
        ("mid_close_core", "swing_core"): 220.0,
        ("lunch_peak_part_time", "lunch_peak"): 220.0,
        ("peak_part_time", "mid_peak"): 220.0,
        ("close_peak_part_time", "close_peak"): 260.0,
        ("weekend_peak_part_time", "mid_peak"): 180.0,
        ("weekend_peak_part_time", "close_peak"): 180.0,
    }
    score += role_bonus_map.get((template_kind, shift_role), 0.0)
    if shift_role == "flex":
        score += 20.0
    if shift_role == "full_time_flex":
        score += 60.0
    score += _preferred_shift_bonus(employee, template_kind, shift_role)

    if date_key in set(meta.get("external_store_days", [])):
        score -= 500.0

    return score


def _build_realistic_template_specs(
    date_obj: datetime,
    hour_start: int,
    hour_end: int,
    demand_by_day_hour: dict,
    required_per_hour: int,
    rules: dict | None = None,
    store_archetype: str | None = None,
    *,
    allow_zero_demand: bool = False,
) -> tuple[str, list[dict]]:
    profile = _analyze_store_day_profile(
        date_obj,
        hour_start,
        hour_end,
        demand_by_day_hour,
        required_per_hour,
        allow_zero_demand=allow_zero_demand,
    )
    archetype = str(store_archetype or "auto").strip().lower()
    mode = _select_store_mode(profile, archetype)
    specs = []
    open_hours = int(profile["open_hours"])
    overall_peak = int(profile["overall_peak"])
    opening_target = int(profile["opening_target"])
    closing_target = _resolve_min_closing_staff(
        store_archetype=archetype,
        rules=rules or {},
        profile=profile,
    )
    midday_peak = int(profile["midday_peak"])
    late_peak = int(profile["late_peak"])
    late_peak = max(late_peak, closing_target)
    overall_peak = max(overall_peak, closing_target)
    opening_full_hours = min(10, open_hours)
    closing_full_hours = min(10, open_hours)
    short_part_hours = 4
    medium_part_hours = min(6, max(4, open_hours - 6))
    long_part_hours = min(8, max(4, open_hours - 4))
    opening_start = hour_start
    closing_start = max(hour_start, hour_end - closing_full_hours + 1)
    swing_start = max(hour_start, min(hour_start + 3, hour_end - opening_full_hours + 1))
    midday_start = max(hour_start, min(hour_start + 3, hour_end - short_part_hours + 1))
    peak_start = max(hour_start, min(hour_start + 5, hour_end - medium_part_hours + 1))
    late_peak_start = max(hour_start, min(hour_start + 5, hour_end - long_part_hours + 1))
    mid_close_start = max(hour_start, min(hour_start + 3, hour_end - closing_full_hours + 1))
    close_peak_start = max(hour_start, min(hour_end - short_part_hours + 1, hour_end - 3))
    full_day_start = max(hour_start, min(hour_start + 2, hour_end - min(12, open_hours) + 1))

    def add_specs(kind: str, start: int, hours: int, preferred_type: str, count: int = 1) -> None:
        for _ in range(max(0, int(count))):
            specs.append(
                {
                    "kind": kind,
                    "start": start,
                    "hours": hours,
                    "preferred_type": preferred_type,
                }
            )

    if archetype == "light_single_core":
        weekday_full_day_start = hour_start
        weekend_open_support_start = hour_start
        add_specs("full_day_core", weekday_full_day_start, min(12, open_hours), "full_time", 1)
        if profile["is_weekend"] or opening_target >= 2:
            add_specs("lunch_peak_part_time", weekend_open_support_start, min(6, max(4, open_hours // 2)), "part_time", 1)
        if late_peak >= 2:
            add_specs("close_peak_part_time", close_peak_start, short_part_hours, "part_time", 1)
    elif archetype == "peak_dual_core":
        peak_mid_start = max(hour_start, min(hour_start + 3, hour_end - opening_full_hours + 1))
        peak_close_start = max(hour_start, min(hour_start + 4, hour_end - closing_full_hours + 1))
        add_specs("opening_core", opening_start, opening_full_hours, "full_time", 1)
        add_specs("mid_close_core", peak_mid_start, closing_full_hours, "full_time", 1)
        add_specs("closing_core", peak_close_start, closing_full_hours, "full_time", 1)
        add_specs("lunch_peak_part_time", midday_start, short_part_hours, "part_time", max(1, midday_peak - 1))
        add_specs("peak_part_time", late_peak_start, long_part_hours, "part_time", max(1, overall_peak - 2))
        if late_peak >= 2:
            add_specs("close_peak_part_time", close_peak_start, short_part_hours, "part_time", 1)
        if profile["is_weekend"]:
            add_specs("weekend_peak_part_time", late_peak_start, long_part_hours, "part_time", 1)
    elif mode == "light_single_core":
        add_specs("full_day_core", hour_start, min(12, open_hours), "full_time", 1)
        if opening_target >= 2 or closing_target >= 2:
            add_specs(
                "peak_part_time",
                peak_start,
                medium_part_hours,
                "part_time",
                max(opening_target, closing_target) - 1,
            )
        if late_peak >= 2 and open_hours >= 10:
            add_specs("close_peak_part_time", close_peak_start, short_part_hours, "part_time", late_peak - 1)
    elif mode == "standard_dual_core":
        add_specs("opening_core", opening_start, opening_full_hours, "full_time", 1)
        add_specs("closing_core", closing_start, closing_full_hours, "full_time", 1)
        if late_peak >= max(2, closing_target):
            add_specs("mid_close_core", mid_close_start, closing_full_hours, "full_time", 1)
        elif max(opening_target, closing_target) >= 2 and overall_peak >= 2:
            add_specs("swing_core", swing_start, opening_full_hours, "full_time", 1)
        if midday_peak >= max(2, opening_target):
            add_specs("lunch_peak_part_time", midday_start, short_part_hours, "part_time", midday_peak - 1)
        if late_peak >= max(2, closing_target):
            add_specs("peak_part_time", peak_start, medium_part_hours, "part_time", late_peak - 1)
        if profile["is_weekend"] and overall_peak >= 3:
            add_specs("weekend_peak_part_time", peak_start, medium_part_hours, "part_time", 1)
    else:
        add_specs("opening_core", opening_start, opening_full_hours, "full_time", 1)
        add_specs("closing_core", closing_start, closing_full_hours, "full_time", 1)
        add_specs("mid_close_core", mid_close_start, closing_full_hours, "full_time", 1)
        if opening_target >= 3:
            add_specs("opening_core", opening_start, opening_full_hours, "full_time", opening_target - 2)
        if closing_target >= 2 and overall_peak >= 4:
            extra_close_start = max(hour_start, min(hour_start + 4, hour_end - closing_full_hours + 1))
            existing_full_time_starts = {
                int(spec["start"])
                for spec in specs
                if str(spec["preferred_type"]) == "full_time"
            }
            if extra_close_start not in existing_full_time_starts:
                add_specs("closing_core", extra_close_start, closing_full_hours, "full_time", max(1, closing_target - 1))
        if midday_peak >= max(2, opening_target):
            add_specs("lunch_peak_part_time", midday_start, short_part_hours, "part_time", midday_peak - 1)
        if overall_peak >= max(3, late_peak):
            add_specs("peak_part_time", late_peak_start, long_part_hours, "part_time", max(1, overall_peak - 2))
        if late_peak >= max(2, closing_target):
            add_specs("close_peak_part_time", close_peak_start, short_part_hours, "part_time", late_peak - 1)
        if profile["is_weekend"] and overall_peak >= 3:
            weekend_extra_start = max(hour_start, min(hour_start + 6, hour_end - long_part_hours + 1))
            add_specs("weekend_peak_part_time", weekend_extra_start, long_part_hours, "part_time", max(1, overall_peak - 2))

    specs = _shape_part_time_template_specs(
        specs,
        store_archetype=archetype,
        profile=profile,
        hour_start=hour_start,
        hour_end=hour_end,
        date_obj=date_obj,
    )

    kind_priority = {
        "opening_core": 0,
        "closing_core": 1,
        "mid_close_core": 2,
        "full_day_core": 3,
        "swing_core": 4,
        "lunch_peak_part_time": 5,
        "peak_part_time": 6,
        "close_peak_part_time": 7,
        "weekend_peak_part_time": 8,
    }
    return mode, sorted(
        specs,
        key=lambda item: (
            0 if str(item["preferred_type"]) == "full_time" else 1,
            kind_priority.get(str(item["kind"]), 99),
            int(item["start"]),
            -int(item["hours"]),
        ),
    )


def _prefill_realistic_templates(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    daily_assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    key_holder_ids: set[str],
    hour_start: int,
    hour_end: int,
    daily_limit: float,
    template_specs: list[dict],
    full_time_rest_days: dict[str, str],
    full_time_work_days: dict[str, set[str]],
    last_role_by_employee: dict[str, str],
    role_counts_by_employee: dict[str, dict[str, int]],
    role_targets_by_employee: dict[str, dict[str, float]],
    full_time_daily_role_plan: dict[str, dict[str, str]],
    all_employees: list,
) -> None:
    for spec in template_specs:
        block_start = int(spec["start"])
        block_hours = int(spec["hours"])
        block_end = block_start + block_hours - 1
        if block_start < hour_start or block_end > hour_end:
            continue
        if daily_assigned_hours.get(date_key, 0.0) + block_hours > daily_limit:
            continue

        candidate_hours = list(range(block_start, block_start + block_hours))
        hour_index = _build_hour_index(schedule_assignments)
        candidates = []

        forced_employee_id = str(spec.get("assigned_employee_id") or "")
        for employee in employees:
            emp_id = str(employee.get("id"))
            preferred_type = spec.get("preferred_type")
            if forced_employee_id and emp_id != forced_employee_id:
                continue
            if preferred_type == "full_time" and not _is_full_time(employee):
                continue
            if preferred_type == "part_time" and not _is_part_time(employee):
                continue
            if not _full_time_can_start_new_day(
                employee,
                date_key=date_key,
                full_time_rest_days=full_time_rest_days,
                full_time_work_days=full_time_work_days,
            ):
                continue
            if not _can_assign_block(employee, start_date, date_obj, date_key, block_start, block_hours, daily_blocks):
                continue
            if _has_severe_relation_conflict(
                relation_map,
                hour_index,
                emp_id,
                candidate_hours,
            ):
                continue

            shift_role = _infer_shift_role(
                employee,
                start_date=start_date,
                target_date=date_obj,
                date_key=date_key,
                hour_start=hour_start,
                hour_end=hour_end,
                key_holder_ids=key_holder_ids,
            )
            if shift_role in {"unavailable", "external"}:
                continue

            score = _template_candidate_score(
                employee,
                template_kind=str(spec["kind"]),
                assigned_hours=assigned_hours,
                store_priority=store_priority,
                key_holder_ids=key_holder_ids,
                date_key=date_key,
                shift_role=shift_role,
            )
            score += _availability_fit_bonus(
                employee,
                start_date=start_date,
                target_date=date_obj,
                block_start=block_start,
                block_end=block_end,
                hour_start=hour_start,
                hour_end=hour_end,
                template_kind=str(spec["kind"]),
            )
            score += _role_continuity_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                previous_role=last_role_by_employee.get(emp_id),
            )
            score += _rest_rebound_bonus(
                employee,
                date_obj=date_obj,
                full_time_rest_days=full_time_rest_days,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
            )
            score += _role_balance_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
            )
            score += _role_rotation_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
                employees=all_employees,
            )
            score += _role_target_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
                role_targets_by_employee=role_targets_by_employee,
            )
            score += _daily_role_plan_bonus(
                employee,
                date_key=date_key,
                full_time_daily_role_plan=full_time_daily_role_plan,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
            )
            candidates.append((score, employee))

        if not candidates:
            continue

        candidates = _filter_candidates_by_priority_band(candidates, store_priority)
        _, selected = max(candidates, key=lambda item: item[0])
        _apply_block(
            schedule_assignments,
            selected,
            date_key,
            block_start,
            block_hours,
            daily_blocks,
            assigned_hours,
            daily_assigned_hours,
            block_kind=str(spec["kind"]),
            block_max_end=block_end,
        )
        _mark_employee_day_worked(str(selected.get("id")), date_key, full_time_work_days)


def _hourly_gap_counts(
    schedule_assignments: list[dict],
    date_obj: datetime,
    hour_start: int,
    hour_end: int,
    demand_by_day_hour: dict,
    required_per_hour: int,
) -> dict[int, int]:
    hour_index = _build_hour_index(schedule_assignments)
    gaps = {}
    for hour in range(hour_start, hour_end + 1):
        target_staff = _hour_target(demand_by_day_hour, date_obj, hour, required_per_hour)
        current_staff = len(hour_index.get(hour, []))
        gaps[hour] = max(0, target_staff - current_staff)
    return gaps




def _upgrade_backup_part_time_blocks(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    hour_start: int,
    hour_end: int,
) -> None:
    employee_map = {str(emp.get("id")): emp for emp in employees}
    hour_index = _build_hour_index(schedule_assignments)

    for (block_date_key, emp_id), block in list(daily_blocks.items()):
        if block_date_key != date_key:
            continue
        backup_employee = employee_map.get(emp_id)
        if backup_employee is None or not _is_part_time(backup_employee):
            continue

        backup_priority = float(store_priority.get(emp_id, 99))
        if backup_priority <= 2:
            continue

        block_start = int(block.get("start", 0))
        block_end = int(block.get("end", -1))
        block_kind = str(block.get("kind", ""))
        block_hours = list(range(block_start, block_end + 1))
        if not block_hours:
            continue

        template_kind = "close_peak_part_time" if block_end >= hour_end - 1 else "peak_part_time"
        replacement_options = []
        for employee in employees:
            candidate_id = str(employee.get("id"))
            if candidate_id == emp_id or not _is_part_time(employee):
                continue
            candidate_priority = float(store_priority.get(candidate_id, 99))
            if candidate_priority > 2 or candidate_priority >= backup_priority:
                continue
            if not _can_assign_block(employee, start_date, date_obj, date_key, block_start, len(block_hours), daily_blocks):
                continue
            if _has_severe_relation_conflict(relation_map, hour_index, candidate_id, block_hours, ignored_employee_ids={emp_id}):
                continue

            score = 0.0
            score += (_store_priority_value(backup_employee, store_priority) - candidate_priority) * 120.0
            score += _template_skill_score(employee, template_kind)
            score += _availability_fit_bonus(
                employee,
                start_date=start_date,
                target_date=date_obj,
                block_start=block_start,
                block_end=block_end,
                hour_start=hour_start,
                hour_end=hour_end,
                template_kind=template_kind,
            )
            if template_kind == "close_peak_part_time":
                score += _late_close_part_time_bonus(employee, store_priority)
            score += _availability_scarcity_bonus(employee) * 0.5
            score += _monthly_hours_bonus(employee) * 0.35
            replacement_options.append((score, employee))

        if not replacement_options:
            continue

        replacement_options.sort(key=lambda item: item[0], reverse=True)
        _, selected = replacement_options[0]
        selected_id = str(selected.get("id"))
        schedule_assignments[:] = [
            item for item in schedule_assignments
            if not (str(item.get("employee_id")) == emp_id and int(item.get("hour", 0)) in block_hours)
        ]
        for block_hour in block_hours:
            schedule_assignments.append(
                {
                    "employee_id": selected.get("id"),
                    "employee_name": selected.get("name", "Unknown"),
                    "shift": _shift_name(block_hour),
                    "hour": block_hour,
                }
            )
        assigned_hours[emp_id] = max(0, assigned_hours.get(emp_id, 0) - len(block_hours))
        assigned_hours[selected_id] = assigned_hours.get(selected_id, 0) + len(block_hours)
        daily_blocks.pop((date_key, emp_id), None)
        daily_blocks[(date_key, selected_id)] = {
            "start": block_start,
            "end": block_end,
            "kind": block_kind or "replacement",
            "max_end": int(block.get("max_end", block_end)),
        }
        hour_index = _build_hour_index(schedule_assignments)

def _prune_redundant_backup_part_time_blocks(
    *,
    schedule_assignments: list[dict],
    date_obj: datetime,
    date_key: str,
    daily_blocks: dict,
    assigned_hours: dict,
    employee_map: dict[str, dict],
    store_priority: dict,
    demand_by_day_hour: dict,
    required_per_hour: int,
) -> None:
    while True:
        hour_index = _build_hour_index(schedule_assignments)
        removable_candidates = []

        for (block_date_key, emp_id), block in daily_blocks.items():
            if block_date_key != date_key:
                continue
            employee = employee_map.get(emp_id)
            if employee is None or not _is_part_time(employee):
                continue

            priority_value = float(store_priority.get(emp_id, 99))
            if priority_value <= 2:
                continue

            block_hours = list(range(int(block.get("start", 0)), int(block.get("end", -1)) + 1))
            if not block_hours:
                continue

            if any(
                len(hour_index.get(hour, [])) - 1 < _hour_target(demand_by_day_hour, date_obj, hour, required_per_hour)
                for hour in block_hours
            ):
                continue

            removable_candidates.append((
                priority_value,
                0 if str(block.get("kind")) == "fallback" else 1,
                len(block_hours),
                emp_id,
                block_hours,
            ))

        if not removable_candidates:
            break

        removable_candidates.sort(reverse=True)
        _, _, _, remove_emp_id, remove_hours = removable_candidates[0]
        remove_hour_set = set(remove_hours)
        schedule_assignments[:] = [
            item
            for item in schedule_assignments
            if not (
                str(item.get("employee_id")) == remove_emp_id
                and int(item.get("hour", 0)) in remove_hour_set
            )
        ]
        assigned_hours[remove_emp_id] = max(0, assigned_hours.get(remove_emp_id, 0) - len(remove_hours))
        daily_blocks.pop((date_key, remove_emp_id), None)


def _build_gap_driven_template_specs(
    *,
    store_mode: str,
    date_obj: datetime,
    hour_start: int,
    hour_end: int,
    demand_by_day_hour: dict,
    required_per_hour: int,
    schedule_assignments: list[dict],
) -> list[dict]:
    gaps = _hourly_gap_counts(
        schedule_assignments,
        date_obj,
        hour_start,
        hour_end,
        demand_by_day_hour,
        required_per_hour,
    )
    profile = _analyze_store_day_profile(
        date_obj,
        hour_start,
        hour_end,
        demand_by_day_hour,
        required_per_hour,
    )

    specs = []
    hours = list(range(hour_start, hour_end + 1))
    cursor = 0
    while cursor < len(hours):
        hour = hours[cursor]
        if gaps.get(hour, 0) <= 0:
            cursor += 1
            continue

        cluster_start = hour
        cluster_peak = gaps.get(hour, 0)
        while cursor + 1 < len(hours) and gaps.get(hours[cursor + 1], 0) > 0:
            cursor += 1
            cluster_peak = max(cluster_peak, gaps.get(hours[cursor], 0))
        cluster_end = hours[cursor]
        cluster_len = cluster_end - cluster_start + 1

        if cluster_start <= hour_start:
            kind = "full_day_core" if store_mode == "light_single_core" else "opening_core"
            block_hours = min(12 if kind == "full_day_core" else 10, hour_end - cluster_start + 1)
            preferred_type = "full_time"
        elif cluster_end >= hour_end:
            kind = "closing_core" if cluster_len >= 5 else "close_peak_part_time"
            block_hours = min(10 if kind == "closing_core" else 4, cluster_end - hour_start + 1)
            preferred_type = "full_time" if kind == "closing_core" else "part_time"
        elif cluster_start <= hour_start + 1 and cluster_len >= 6:
            kind = "full_day_core" if store_mode == "light_single_core" else "opening_core"
            block_hours = min(12 if kind == "full_day_core" else 10, hour_end - cluster_start + 1)
            preferred_type = "full_time"
        elif cluster_end >= hour_end - 1 and cluster_len >= 6:
            kind = "closing_core"
            block_hours = min(10, cluster_end - hour_start + 1)
            preferred_type = "full_time"
        elif store_mode == "high_intensity_multi_support" and cluster_len >= 8 and profile["overall_peak"] >= 3:
            kind = "swing_core"
            block_hours = min(10, hour_end - cluster_start + 1)
            preferred_type = "full_time"
        elif cluster_end >= hour_end - 1:
            kind = "close_peak_part_time"
            block_hours = min(4, cluster_len)
            preferred_type = "part_time"
        elif cluster_len >= 5 or cluster_peak >= 2:
            kind = "peak_part_time"
            block_hours = min(8 if store_mode == "high_intensity_multi_support" else 6, max(4, cluster_len))
            preferred_type = "part_time"
        else:
            kind = "lunch_peak_part_time"
            block_hours = 4
            preferred_type = "part_time"

        if preferred_type == "full_time":
            block_hours = max(min(block_hours, hour_end - cluster_start + 1), 6)
        else:
            block_hours = max(min(block_hours, hour_end - cluster_start + 1), 4)

        block_start = cluster_start
        if kind == "closing_core":
            block_start = max(hour_start, cluster_end - block_hours + 1)
        elif kind == "full_day_core":
            block_start = max(hour_start, min(cluster_start, hour_end - block_hours + 1))
        elif kind == "close_peak_part_time":
            block_start = max(hour_start, min(cluster_end - block_hours + 1, hour_end - block_hours + 1))

        repeat_count = max(1, cluster_peak)
        for _ in range(repeat_count):
            specs.append(
                {
                    "kind": kind,
                    "start": block_start,
                    "hours": block_hours,
                    "preferred_type": preferred_type,
                }
            )
        cursor += 1

    return specs


def _build_hour_index(assignments: list[dict]) -> dict[int, list[dict]]:
    indexed = {}
    for item in assignments:
        hour = int(item.get("hour", 0))
        indexed.setdefault(hour, []).append(item)
    return indexed


def _split_template_specs(template_specs: list[dict]) -> tuple[list[dict], list[dict]]:
    core_kinds = {"full_day_core", "opening_core", "closing_core", "swing_core", "mid_close_core"}
    core_specs = [spec for spec in template_specs if str(spec.get("kind")) in core_kinds]
    support_specs = [spec for spec in template_specs if str(spec.get("kind")) not in core_kinds]
    return core_specs, support_specs


def _part_time_block_preferences(
    *,
    store_archetype: str,
    profile: dict,
    hour_start: int,
    hour_end: int,
) -> dict[str, float]:
    open_hours = int(profile.get("open_hours", max(1, hour_end - hour_start + 1)))
    late_peak = int(profile.get("late_peak", 0))
    midday_peak = int(profile.get("midday_peak", 0))
    overall_peak = int(profile.get("overall_peak", 0))
    is_weekend = bool(profile.get("is_weekend"))

    close_bias = 0.0
    if late_peak >= max(2, midday_peak):
        close_bias += 1.0
    if open_hours >= 12:
        close_bias += 0.5
    if overall_peak >= 4:
        close_bias += 0.5
    if is_weekend:
        close_bias -= 0.5
    if str(store_archetype or "auto").strip().lower() == "peak_dual_core":
        close_bias += 0.75

    close_bias = max(0.0, close_bias)
    late_close_hours = 4
    if is_weekend and close_bias >= 1.25:
        late_close_hours = 5
    mid_close_hours = 6 if open_hours >= 12 else 5
    late_close_start = max(hour_start, hour_end - late_close_hours + 1)
    mid_close_start = max(hour_start, hour_end - mid_close_hours + 1)
    bridge_start = max(hour_start, min(hour_start + 4, hour_end - mid_close_hours + 1))

    return {
        "close_bias": close_bias,
        "late_close_hours": late_close_hours,
        "late_close_start": late_close_start,
        "mid_close_hours": mid_close_hours,
        "mid_close_start": mid_close_start,
        "bridge_start": bridge_start,
    }


def _shape_part_time_template_specs(
    template_specs: list[dict],
    *,
    store_archetype: str,
    profile: dict,
    hour_start: int,
    hour_end: int,
    date_obj: datetime | None = None,
) -> list[dict]:
    if not template_specs:
        return template_specs

    prefs = _part_time_block_preferences(
        store_archetype=store_archetype,
        profile=profile,
        hour_start=hour_start,
        hour_end=hour_end,
    )
    close_bias = float(prefs.get("close_bias", 0.0))
    if close_bias <= 0:
        return template_specs

    shaped = []
    overall_peak = int(profile.get("overall_peak", 0))
    is_weekend = bool(profile.get("is_weekend"))
    is_early_weekday = date_obj is not None and int(date_obj.weekday()) < 4
    for spec in template_specs:
        shaped_spec = dict(spec)
        kind = str(shaped_spec.get("kind", ""))
        if kind == "close_peak_part_time":
            shaped_spec["start"] = int(prefs["late_close_start"])
            shaped_spec["hours"] = int(prefs["late_close_hours"])
        elif (
            kind == "peak_part_time"
            and is_early_weekday
            and not is_weekend
            and close_bias >= 1.5
            and overall_peak <= 4
        ):
            current_start = int(shaped_spec.get("start", hour_start))
            current_hours = int(shaped_spec.get("hours", 0) or 0)
            if current_hours >= 7:
                shaped_spec["start"] = min(current_start + 1, hour_end - 4)
                shaped_spec["hours"] = max(6, current_hours - 1)
        shaped.append(shaped_spec)
    return shaped


def _filter_support_template_specs_by_gap(template_specs: list[dict], gap_counts: dict[int, int]) -> list[dict]:
    filtered_specs = []
    for spec in template_specs:
        block_start = int(spec.get("start", 0))
        block_hours = int(spec.get("hours", 0))
        candidate_hours = list(range(block_start, block_start + block_hours))
        gap_hour_count = sum(1 for hour in candidate_hours if gap_counts.get(hour, 0) > 0)
        gap_unit_count = sum(max(0, gap_counts.get(hour, 0)) for hour in candidate_hours)
        kind = str(spec.get("kind"))

        if gap_unit_count <= 0:
            continue
        if kind in {"lunch_peak_part_time", "peak_part_time", "weekend_peak_part_time"} and gap_hour_count < max(2, block_hours // 2):
            continue

        filtered_specs.append(spec)

    return filtered_specs


def _plan_daily_core_assignments(
    *,
    employees: list,
    template_specs: list[dict],
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    hour_start: int,
    hour_end: int,
    store_priority: dict,
    key_holder_ids: set[str],
    full_time_rest_days: dict[str, str],
    full_time_work_days: dict[str, set[str]],
    last_role_by_employee: dict[str, str],
    role_counts_by_employee: dict[str, dict[str, int]],
    role_targets_by_employee: dict[str, dict[str, float]],
    full_time_daily_role_plan: dict[str, dict[str, str]],
    assigned_hours: dict,
) -> list[dict]:
    if not template_specs:
        return template_specs

    full_time_employees = [employee for employee in employees if _is_full_time(employee)]
    employee_map = {str(employee.get("id")): employee for employee in full_time_employees}
    candidate_rows: list[list[tuple[float, str]]] = []
    planned = [dict(spec) for spec in template_specs]

    for spec_copy in planned:
        if str(spec_copy.get("preferred_type")) != "full_time":
            candidate_rows.append([])
            continue

        block_start = int(spec_copy["start"])
        block_hours = int(spec_copy["hours"])
        block_end = block_start + block_hours - 1
        row_candidates: list[tuple[float, str]] = []
        for employee in full_time_employees:
            emp_id = str(employee.get("id"))
            if not _full_time_can_start_new_day(
                employee,
                date_key=date_key,
                full_time_rest_days=full_time_rest_days,
                full_time_work_days=full_time_work_days,
            ):
                continue
            bounds = _availability_bounds(employee, start_date, date_obj)
            if bounds is None:
                continue
            available_start, available_end = bounds
            if block_start < available_start or block_end >= available_end:
                continue

            shift_role = _infer_shift_role(
                employee,
                start_date=start_date,
                target_date=date_obj,
                date_key=date_key,
                hour_start=hour_start,
                hour_end=hour_end,
                key_holder_ids=key_holder_ids,
            )
            if shift_role in {"unavailable", "external"}:
                continue

            score = _template_candidate_score(
                employee,
                template_kind=str(spec_copy["kind"]),
                assigned_hours=assigned_hours,
                store_priority=store_priority,
                key_holder_ids=key_holder_ids,
                date_key=date_key,
                shift_role=shift_role,
            )
            score += _availability_fit_bonus(
                employee,
                start_date=start_date,
                target_date=date_obj,
                block_start=block_start,
                block_end=block_end,
                hour_start=hour_start,
                hour_end=hour_end,
                template_kind=str(spec_copy["kind"]),
            )
            score += _sole_keyholder_shift_bonus(
                employee,
                employees=full_time_employees,
                start_date=start_date,
                date_obj=date_obj,
                date_key=date_key,
                full_time_rest_days=full_time_rest_days,
                key_holder_ids=key_holder_ids,
                template_kind=str(spec_copy["kind"]),
                hour_start=hour_start,
                hour_end=hour_end,
            )
            score += _role_continuity_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                previous_role=last_role_by_employee.get(emp_id),
            )
            score += _rest_rebound_bonus(
                employee,
                date_obj=date_obj,
                full_time_rest_days=full_time_rest_days,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
            )
            score += _role_balance_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
            )
            score += _role_rotation_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
                employees=employees,
            ) * 1.35
            score += _role_target_bonus(
                employee,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
                role_counts_by_employee=role_counts_by_employee,
                role_targets_by_employee=role_targets_by_employee,
            ) * 1.45
            score += _daily_role_plan_bonus(
                employee,
                date_key=date_key,
                full_time_daily_role_plan=full_time_daily_role_plan,
                proposed_start=block_start,
                proposed_end=block_end,
                opening_hour=hour_start,
                closing_hour=hour_end,
            )
            row_candidates.append((score, emp_id))

        filtered_candidates = row_candidates
        if row_candidates:
            matching_candidates = [
                (score_value, emp_id)
                for score_value, emp_id in row_candidates
                if _role_plan_matches_template(
                    full_time_daily_role_plan.get(emp_id, {}).get(date_key),
                    str(spec_copy.get("kind")),
                )
            ]
            if matching_candidates:
                filtered_candidates = matching_candidates

        filtered_candidates.sort(reverse=True)
        candidate_rows.append(filtered_candidates[:6])

    full_time_indices = [idx for idx, spec in enumerate(planned) if str(spec.get("preferred_type")) == "full_time"]
    if not full_time_indices:
        return planned

    best_assignment: dict[int, str] = {}
    best_score = float("-inf")
    candidate_pool = sorted({emp_id for idx in full_time_indices for _, emp_id in candidate_rows[idx]})

    if len(candidate_pool) >= len(full_time_indices):
        for chosen_ids in combinations(candidate_pool, len(full_time_indices)):
            for ordered_ids in permutations(chosen_ids):
                total = 0.0
                valid = True
                used_roles: dict[str, str] = {}
                for spec_idx, emp_id in zip(full_time_indices, ordered_ids):
                    score_lookup = dict(candidate_rows[spec_idx])
                    if emp_id not in score_lookup:
                        valid = False
                        break
                    spec = planned[spec_idx]
                    total += float(score_lookup[emp_id])
                    current_kind = str(spec.get("kind"))
                    if current_kind == "opening_core" and _preferred_shift(employee_map[emp_id]) == "opening":
                        total += 4.0
                    if current_kind in {"closing_core", "mid_close_core"} and _preferred_shift(employee_map[emp_id]) == "closing":
                        total += 4.0
                    previous_kind = used_roles.get(emp_id)
                    if previous_kind is not None:
                        valid = False
                        break
                    used_roles[emp_id] = current_kind
                if valid and total > best_score:
                    best_score = total
                    best_assignment = {spec_idx: emp_id for spec_idx, emp_id in zip(full_time_indices, ordered_ids)}

    if not best_assignment:
        reserved_employee_ids: set[str] = set()
        for spec_idx in full_time_indices:
            for score, emp_id in candidate_rows[spec_idx]:
                if emp_id in reserved_employee_ids:
                    continue
                best_assignment[spec_idx] = emp_id
                reserved_employee_ids.add(emp_id)
                break

    for spec_idx, emp_id in best_assignment.items():
        planned[spec_idx]["assigned_employee_id"] = emp_id

    return planned


def _has_severe_relation_conflict(
    relation_map: dict,
    hour_index: dict[int, list[dict]],
    candidate_emp_id: str,
    candidate_hours: list[int],
    ignored_employee_ids: set[str] | None = None,
) -> bool:
    ignored_employee_ids = ignored_employee_ids or set()
    for hour in candidate_hours:
        for assigned in hour_index.get(hour, []):
            assigned_emp_id = str(assigned.get("employee_id"))
            if assigned_emp_id in ignored_employee_ids or assigned_emp_id == candidate_emp_id:
                continue
            if relation_map.get((candidate_emp_id, assigned_emp_id), 0.0) >= 0.85:
                return True
    return False


def _find_short_block_replacement(
    *,
    employees: list,
    employee_map: dict,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    cover_hours: list[int],
    short_employee_id: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    key_holder_ids: set[str],
    hour_start: int,
    hour_end: int,
) -> dict | None:
    if not cover_hours:
        return None

    cover_start = min(cover_hours)
    cover_end = max(cover_hours)
    hour_index = _build_hour_index(schedule_assignments)
    replacement_options = []

    for emp in employees:
        emp_id = str(emp.get("id"))
        if emp_id == short_employee_id:
            continue

        meta = emp.get("meta", {})
        required_hours = _required_daily_hours(emp)
        preferred_max_daily_hours = _preferred_max_daily_hours(emp)
        absolute_max_daily_hours = _absolute_max_daily_hours(emp)
        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        max_schedulable_hours = absolute_max_daily_hours - external_daily_hours
        if max_schedulable_hours < required_hours:
            continue

        existing_block = daily_blocks.get((date_key, emp_id))
        block_start = None
        proposed_hours = []

        if existing_block is not None:
            current_start = int(existing_block["start"])
            current_end = int(existing_block["end"])
            current_hours = current_end - current_start + 1
            if current_hours >= max_schedulable_hours:
                continue

            if current_end < cover_start and current_end + 1 == cover_start:
                proposed_hours = list(range(cover_start, cover_end + 1))
                merged_hours = current_hours + len(proposed_hours)
                if merged_hours > max_schedulable_hours:
                    continue
                if not all(_is_available(emp, start_date, date_obj, hour) for hour in proposed_hours):
                    continue
            elif cover_end < current_start and cover_end + 1 == current_start:
                proposed_hours = list(range(cover_start, cover_end + 1))
                merged_hours = current_hours + len(proposed_hours)
                if merged_hours > max_schedulable_hours:
                    continue
                if not all(_is_available(emp, start_date, date_obj, hour) for hour in proposed_hours):
                    continue
            else:
                continue

            if _has_severe_relation_conflict(
                relation_map,
                hour_index,
                emp_id,
                proposed_hours,
                ignored_employee_ids={short_employee_id},
            ):
                continue

            score = 260.0
            if emp_id in key_holder_ids and cover_end >= hour_end:
                score += 120.0
            score += max(0.0, 24.0 - float(store_priority.get(emp_id, 99)) * 3.0)
            score -= assigned_hours.get(emp_id, 0) * 4.0
            score += _nationality_priority_bonus(emp)
            score += _template_skill_score(emp, "closing_core" if cover_end >= hour_end - 1 else "peak_part_time")
            score += _preferred_hours_penalty(
                emp,
                external_daily_hours=external_daily_hours,
                proposed_total_hours=current_hours + len(proposed_hours),
                closing_sensitive=cover_end >= hour_end - 1,
            )

            replacement_options.append(
                {
                    "score": score,
                    "employee": emp,
                    "hours_to_add": proposed_hours,
                    "replace_employee_id": short_employee_id,
                }
            )
            continue

        block_hours = min(required_hours, max_schedulable_hours)
        block_start = _find_cover_block_for_range(
            emp,
            start_date,
            date_obj,
            cover_start,
            cover_end,
            block_hours,
            hour_start,
            hour_end,
        )
        if block_start is None:
            continue

        proposed_hours = list(range(block_start, block_start + block_hours))
        if _has_severe_relation_conflict(
            relation_map,
            hour_index,
            emp_id,
            proposed_hours,
            ignored_employee_ids={short_employee_id},
        ):
            continue

        score = 180.0
        if meta.get("sg_priority_to_80"):
            score += 80.0
        if meta.get("sg_priority_to_160"):
            score += 30.0
        score += max(0.0, 24.0 - float(store_priority.get(emp_id, 99)) * 3.0)
        score -= assigned_hours.get(emp_id, 0) * 5.0
        score += _nationality_priority_bonus(emp)
        score += _template_skill_score(emp, "closing_core" if cover_end >= hour_end - 1 else "peak_part_time")
        if date_key in set(meta.get("external_store_days", [])):
            score -= 600.0
        if emp_id in key_holder_ids and cover_end >= hour_end:
            score += 140.0
        score += _preferred_hours_penalty(
            emp,
            external_daily_hours=external_daily_hours,
            proposed_total_hours=block_hours,
            closing_sensitive=cover_end >= hour_end - 1,
        )

        replacement_options.append(
            {
                "score": score,
                "employee": emp,
                "hours_to_add": proposed_hours,
                "replace_employee_id": short_employee_id,
            }
        )

    if not replacement_options:
        return None

    replacement_options.sort(key=lambda item: item["score"], reverse=True)
    return replacement_options[0]


def _extend_full_time_late_blocks(
    *,
    employees: list,
    employee_map: dict,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    daily_assigned_hours: dict,
    relation_map: dict,
    hour_start: int,
    closing_hour: int,
) -> None:
    if not schedule_assignments:
        return

    latest_reasonable_late_start = max(hour_start + 2, 12)
    hour_index = _build_hour_index(schedule_assignments)

    for (block_date, emp_id), block in list(daily_blocks.items()):
        if block_date != date_key:
            continue
        employee = employee_map.get(emp_id)
        if not employee or not _is_full_time(employee):
            continue

        current_start = int(block.get("start", hour_start))
        current_end = int(block.get("end", hour_start))
        if current_end >= closing_hour:
            continue

        block_kind = str(block.get("kind", ""))
        is_late_shift = current_start >= latest_reasonable_late_start or block_kind in {"closing_core", "swing_core"}
        if not is_late_shift:
            continue

        meta = employee.get("meta", {})
        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        current_block_hours = current_end - current_start + 1
        absolute_max_daily_hours = _absolute_max_daily_hours(employee)
        remaining_capacity = absolute_max_daily_hours - external_daily_hours - current_block_hours
        if remaining_capacity <= 0:
            continue

        extension_hours = _find_extension_hours(
            employee,
            start_date,
            date_obj,
            current_end,
            closing_hour,
            remaining_capacity,
        )
        if not extension_hours or extension_hours[-1] != closing_hour:
            continue

        if _has_non_overtime_alternative_for_extension(
            employees=employees,
            source_employee_id=emp_id,
            start_date=start_date,
            target_date=date_obj,
            date_key=date_key,
            extension_hours=extension_hours,
            daily_blocks=daily_blocks,
            relation_map=relation_map,
            hour_index=hour_index,
            closing_hour=closing_hour,
        ):
            continue

        if _has_severe_relation_conflict(relation_map, hour_index, emp_id, extension_hours):
            continue

        for block_hour in extension_hours:
            schedule_assignments.append(
                {
                    "employee_id": employee.get("id"),
                    "employee_name": employee.get("name", "Unknown"),
                    "shift": _shift_name(block_hour),
                    "hour": block_hour,
                }
            )
            hour_index.setdefault(block_hour, []).append(
                {
                    "employee_id": employee.get("id"),
                    "employee_name": employee.get("name", "Unknown"),
                    "shift": _shift_name(block_hour),
                    "hour": block_hour,
                }
            )

        assigned_hours[emp_id] = assigned_hours.get(emp_id, 0) + len(extension_hours)
        daily_assigned_hours[date_key] += float(len(extension_hours))
        block["end"] = extension_hours[-1]
        block["max_end"] = max(int(block.get("max_end", current_end)), extension_hours[-1])


def _adjacent_extension_candidates(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    target_hour: int,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    store_priority: dict,
    relation_map: dict,
    key_holder_ids: set[str],
    opening_hour: int,
    closing_hour: int,
) -> list[tuple[float, dict, str]]:
    if target_hour < closing_hour - 2:
        return []

    hour_index = _build_hour_index(schedule_assignments)
    candidates = []
    candidate_meta = []

    for emp in employees:
        emp_id = str(emp.get("id"))
        block = daily_blocks.get((date_key, emp_id))
        if block is None:
            continue

        current_start = int(block.get("start", target_hour))
        current_end = int(block.get("end", target_hour))
        direction = None
        if current_end + 1 == target_hour:
            direction = "forward"
        elif current_start - 1 == target_hour:
            direction = "backward"
        else:
            continue

        meta = emp.get("meta", {})
        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        current_block_hours = current_end - current_start + 1
        absolute_max_daily_hours = _absolute_max_daily_hours(emp)
        preferred_max_daily_hours = _preferred_max_daily_hours(emp)
        if external_daily_hours + current_block_hours >= absolute_max_daily_hours:
            continue
        if not _is_available(emp, start_date, date_obj, target_hour):
            continue
        if target_hour > int(block.get("max_end", closing_hour)):
            continue
        if _has_severe_relation_conflict(relation_map, hour_index, emp_id, [target_hour]):
            continue

        score = 210.0
        score += max(0.0, 24.0 - float(store_priority.get(emp_id, 99)) * 3.0)
        score += _nationality_priority_bonus(emp)
        score -= assigned_hours.get(emp_id, 0) * 3.0
        if target_hour <= opening_hour + 1:
            score += _template_skill_score(emp, "opening_core")
        elif target_hour >= closing_hour - 1:
            score += _template_skill_score(emp, "closing_core")
        else:
            score += _template_skill_score(emp, "peak_part_time")
        if target_hour == opening_hour:
            score += 140.0
        if target_hour == closing_hour:
            score += 200.0
        if emp_id in key_holder_ids and target_hour == closing_hour:
            score += 120.0
        score += _preferred_hours_penalty(
            emp,
            external_daily_hours=external_daily_hours,
            proposed_total_hours=current_block_hours + 1,
            closing_sensitive=target_hour >= closing_hour - 1,
        )

        if target_hour >= closing_hour - 1:
            if _is_part_time(emp) and external_daily_hours + current_block_hours + 1 <= preferred_max_daily_hours:
                score += 180.0
            if _is_full_time(emp) and external_daily_hours + current_block_hours + 1 > preferred_max_daily_hours:
                score -= 420.0
            if _is_full_time(emp) and external_daily_hours + current_block_hours + 1 <= preferred_max_daily_hours:
                score -= 40.0

        candidates.append((score, emp, direction))
        candidate_meta.append(
            {
                "candidate": (score, emp, direction),
                "is_part_time": _is_part_time(emp),
                "within_preferred": external_daily_hours + current_block_hours + 1 <= preferred_max_daily_hours,
                "has_closing_cover": _closing_task_skill_count(emp) > 0 or _has_backroom_skill(emp),
            }
        )

    if target_hour >= closing_hour - 1:
        pt_within_preferred = [
            item["candidate"]
            for item in candidate_meta
            if item["is_part_time"] and item["within_preferred"] and item["has_closing_cover"]
        ]
        if pt_within_preferred:
            return pt_within_preferred

        any_within_preferred = [
            item["candidate"]
            for item in candidate_meta
            if item["within_preferred"]
        ]
        if any_within_preferred:
            return any_within_preferred

    return candidates


def _ensure_full_time_daily_assignment(
    *,
    employees: list,
    start_date: datetime,
    date_obj: datetime,
    date_key: str,
    schedule_assignments: list[dict],
    daily_blocks: dict,
    assigned_hours: dict,
    relation_map: dict,
    store_priority: dict,
    key_holder_ids: set[str],
    hour_start: int,
    hour_end: int,
    full_time_rest_days: dict[str, str],
    full_time_work_days: dict[str, set[str]],
    full_time_daily_role_plan: dict[str, dict[str, str]],
) -> None:
    hour_index = _build_hour_index(schedule_assignments)

    for employee in employees:
        emp_id = str(employee.get("id"))
        if not _is_full_time(employee):
            continue
        if daily_blocks.get((date_key, emp_id)) is not None:
            continue
        if not _full_time_can_start_new_day(
            employee,
            date_key=date_key,
            full_time_rest_days=full_time_rest_days,
            full_time_work_days=full_time_work_days,
        ):
            continue

        meta = employee.get("meta", {})
        if date_key in set(meta.get("external_store_days", [])):
            continue

        bounds = _availability_bounds(employee, start_date, date_obj)
        if bounds is None:
            continue

        available_start, available_end = bounds
        window_start = max(hour_start, available_start)
        window_end = min(hour_end + 1, available_end)
        available_span = window_end - window_start
        if available_span <= 0:
            continue

        external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
        absolute_max_daily_hours = _absolute_max_daily_hours(employee)
        max_schedulable = max(0, absolute_max_daily_hours - external_daily_hours)
        if max_schedulable <= 0:
            continue

        required_hours = min(_required_daily_hours(employee), available_span, max_schedulable)
        if required_hours <= 0:
            continue

        preferred = _preferred_shift(employee)
        planned_role = full_time_daily_role_plan.get(emp_id, {}).get(date_key)
        candidate_starts = []
        if planned_role == "closing":
            candidate_starts.extend([
                max(window_start, hour_end - required_hours + 1),
                max(window_start, hour_end - _required_daily_hours(employee) + 1),
                max(window_start, min(hour_start + 3, hour_end - required_hours + 1)),
            ])
        elif planned_role == "opening":
            candidate_starts.extend([
                window_start,
                max(window_start, min(hour_start + 1, hour_end - required_hours + 1)),
            ])
        elif planned_role == "flex":
            candidate_starts.extend([
                max(window_start, min(hour_start + 3, hour_end - required_hours + 1)),
                max(window_start, hour_end - required_hours + 1),
                window_start,
            ])
        elif preferred == "closing":
            candidate_starts.extend([
                max(window_start, hour_end - required_hours + 1),
                max(window_start, hour_end - _required_daily_hours(employee) + 1),
            ])
        elif preferred == "midday":
            candidate_starts.extend([
                max(window_start, min(hour_start + 3, hour_end - required_hours + 1)),
                max(window_start, min(hour_start + 2, hour_end - required_hours + 1)),
            ])
        else:
            candidate_starts.extend([
                window_start,
                max(window_start, hour_end - required_hours + 1) if preferred == "opening" else window_start,
            ])

        candidate_starts.extend(range(window_start, max(window_start, window_end - required_hours) + 1))
        tried = set()
        for block_start in candidate_starts:
            if block_start in tried:
                continue
            tried.add(block_start)
            block_end = block_start + required_hours
            if block_end > window_end:
                continue
            proposed_hours = list(range(block_start, block_end))
            if not all(_is_available(employee, start_date, date_obj, hour) for hour in proposed_hours):
                continue
            if _has_severe_relation_conflict(relation_map, hour_index, emp_id, proposed_hours):
                continue

            for block_hour in proposed_hours:
                item = {
                    "employee_id": employee.get("id"),
                    "employee_name": employee.get("name", "Unknown"),
                    "shift": _shift_name(block_hour),
                    "hour": block_hour,
                }
                schedule_assignments.append(item)
                hour_index.setdefault(block_hour, []).append(item)

            assigned_hours[emp_id] = assigned_hours.get(emp_id, 0) + len(proposed_hours)
            daily_blocks[(date_key, emp_id)] = {
                "start": proposed_hours[0],
                "end": proposed_hours[-1],
                "kind": "full_time_guarantee",
                "max_end": proposed_hours[-1],
            }
            _mark_employee_day_worked(emp_id, date_key, full_time_work_days)
            break


def generate_schedule(employees: list, rules: dict) -> dict:
    cycle_days = int(rules.get("cycle_days", 7))
    start_date = datetime.strptime(rules.get("start_date", "2026-01-20"), "%Y-%m-%d")
    hour_start = int(rules.get("store_hour_start", 9))
    hour_end = int(rules.get("store_hour_end", 23))
    repair_mode = bool(rules.get("repair_mode"))
    allow_zero_demand_hours = bool(rules.get("allow_zero_demand_hours"))
    required_per_hour = int(rules.get("required_shifts_per_day", 2))
    if not repair_mode:
        required_per_hour = max(1, required_per_hour)
    demand_by_day_hour = rules.get("demand_by_day_hour", {}) or {}
    store_archetype = str(rules.get("store_archetype", "auto") or "auto")

    weekday_limit = float(rules.get("weekday_total_hours_limit", 40.0))
    weekend_limit = float(rules.get("weekend_total_hours_limit", 45.0))
    key_holder_ids = {str(x) for x in rules.get("store_key_holder_employee_ids", [])}
    bad_relations = rules.get("bad_relations", [])
    store_priority = rules.get("store_employee_priority", {})
    min_backroom_per_hour = max(0, int(rules.get("min_backroom_per_hour", 1) or 0))
    require_opening_dual_skill = bool(rules.get("require_opening_dual_skill", True))
    min_opening_keyholders = max(0, int(rules.get("min_opening_keyholders", 1) or 0))
    min_closing_keyholders = max(0, int(rules.get("min_closing_keyholders", 1) or 0))
    store_key_count = max(0, int(rules.get("store_key_count", 0) or 0))

    relation_map = {}
    for rel in bad_relations:
        a = str(rel.get("employee_id_a"))
        b = str(rel.get("employee_id_b"))
        sev = float(rel.get("severity", 0.0))
        relation_map[(a, b)] = sev
        relation_map[(b, a)] = sev

    if not employees:
        return {}

    employee_lookup = {str(emp.get("id")): emp for emp in employees}
    if store_key_count > len(key_holder_ids):
        provisional_candidates = sorted(
            [_emp for _emp in employees if _is_full_time(_emp)],
            key=lambda item: (int(item.get("meta", {}).get("management_skill_score", 50)), int(item.get("meta", {}).get("work_skill_score", 50))),
            reverse=True,
        )
        for candidate in provisional_candidates:
            key_holder_ids.add(str(candidate.get("id")))
            if len(key_holder_ids) >= store_key_count:
                break

    global_work_avg = sum(int(e.get("meta", {}).get("work_skill_score", 50)) for e in employees) / len(employees)
    global_mgmt_avg = sum(int(e.get("meta", {}).get("management_skill_score", 50)) for e in employees) / len(employees)

    assigned_hours = {str(emp.get("id")): 0 for emp in employees}
    daily_assigned_hours = {}
    daily_blocks = {}
    schedule = {}
    full_time_rest_days = _plan_full_time_rest_days(
        employees,
        start_date=start_date,
        cycle_days=cycle_days,
        hour_start=hour_start,
        hour_end=hour_end,
        demand_by_day_hour=demand_by_day_hour,
        required_per_hour=required_per_hour,
        allow_zero_demand_hours=allow_zero_demand_hours,
        key_holder_ids=key_holder_ids,
        store_priority=store_priority,
    )
    full_time_work_days: dict[str, set[str]] = {
        str(emp.get("id")): set() for emp in employees if _is_full_time(emp)
    }
    last_role_by_employee: dict[str, str] = {}
    role_counts_by_employee: dict[str, dict[str, int]] = {str(emp.get("id")): {} for emp in employees}
    role_targets_by_employee = _build_full_time_role_targets(
        employees,
        start_date=start_date,
        cycle_days=cycle_days,
        hour_start=hour_start,
        hour_end=hour_end,
    )
    full_time_daily_role_plan = _build_full_time_daily_role_plan(
        employees,
        start_date=start_date,
        cycle_days=cycle_days,
        hour_start=hour_start,
        hour_end=hour_end,
        full_time_rest_days=full_time_rest_days,
        role_targets_by_employee=role_targets_by_employee,
    )

    for day_index in range(cycle_days):
        date_obj = start_date + timedelta(days=day_index)
        date_key = date_obj.strftime("%Y-%m-%d")
        schedule[date_key] = []
        is_weekend = date_obj.weekday() >= 5
        daily_limit = weekend_limit if is_weekend else weekday_limit
        daily_assigned_hours[date_key] = 0.0
        opening_hour = hour_start
        opening_target = _hour_target(
            demand_by_day_hour,
            date_obj,
            opening_hour,
            required_per_hour,
            allow_zero_demand=allow_zero_demand_hours,
        )
        closing_hour = hour_end
        day_profile = _analyze_store_day_profile(
            date_obj,
            hour_start,
            hour_end,
            demand_by_day_hour,
            required_per_hour,
            allow_zero_demand=allow_zero_demand_hours,
        )
        closing_target = _resolve_min_closing_staff(
            store_archetype=store_archetype,
            rules=rules,
            profile=day_profile,
        )
        store_mode, template_specs = _build_realistic_template_specs(
            date_obj,
            hour_start,
            hour_end,
            demand_by_day_hour,
            required_per_hour,
            rules,
            store_archetype,
            allow_zero_demand=allow_zero_demand_hours,
        )
        full_time_start_hours = {
            int(spec["start"])
            for spec in template_specs
            if str(spec.get("preferred_type")) == "full_time"
        }
        part_time_start_hours = {
            int(spec["start"])
            for spec in template_specs
            if str(spec.get("preferred_type")) == "part_time"
        }
        opening_plan_employee_ids = {
            emp_id
            for emp_id, day_map in full_time_daily_role_plan.items()
            if day_map.get(date_key) == "opening"
        }

        if not repair_mode:
            core_template_specs, support_template_specs = _split_template_specs(template_specs)
            if core_template_specs:
                core_template_specs = _plan_daily_core_assignments(
                    employees=employees,
                    template_specs=core_template_specs,
                    start_date=start_date,
                    date_obj=date_obj,
                    date_key=date_key,
                    hour_start=hour_start,
                    hour_end=hour_end,
                    store_priority=store_priority,
                    key_holder_ids=key_holder_ids,
                    full_time_rest_days=full_time_rest_days,
                    full_time_work_days=full_time_work_days,
                    last_role_by_employee=last_role_by_employee,
                    role_counts_by_employee=role_counts_by_employee,
                    role_targets_by_employee=role_targets_by_employee,
                    full_time_daily_role_plan=full_time_daily_role_plan,
                    assigned_hours=assigned_hours,
                )
                _prefill_realistic_templates(
                    employees=employees,
                    start_date=start_date,
                    date_obj=date_obj,
                    date_key=date_key,
                    schedule_assignments=schedule[date_key],
                    daily_blocks=daily_blocks,
                    assigned_hours=assigned_hours,
                    daily_assigned_hours=daily_assigned_hours,
                    relation_map=relation_map,
                    store_priority=store_priority,
                    key_holder_ids=key_holder_ids,
                    hour_start=hour_start,
                    hour_end=hour_end,
                    daily_limit=daily_limit,
                    template_specs=core_template_specs,
                    full_time_rest_days=full_time_rest_days,
                    full_time_work_days=full_time_work_days,
                    last_role_by_employee=last_role_by_employee,
                    role_counts_by_employee=role_counts_by_employee,
                    role_targets_by_employee=role_targets_by_employee,
                    full_time_daily_role_plan=full_time_daily_role_plan,
                    all_employees=employees,
                )

            gap_after_core = _hourly_gap_counts(
                schedule[date_key],
                date_obj,
                hour_start,
                hour_end,
                demand_by_day_hour,
                required_per_hour,
            )
            if support_template_specs and any(gap > 0 for gap in gap_after_core.values()):
                support_template_specs = _filter_support_template_specs_by_gap(
                    support_template_specs,
                    gap_after_core,
                )
                if support_template_specs:
                    _prefill_realistic_templates(
                        employees=employees,
                        start_date=start_date,
                        date_obj=date_obj,
                        date_key=date_key,
                        schedule_assignments=schedule[date_key],
                        daily_blocks=daily_blocks,
                        assigned_hours=assigned_hours,
                        daily_assigned_hours=daily_assigned_hours,
                        relation_map=relation_map,
                        store_priority=store_priority,
                        key_holder_ids=key_holder_ids,
                        hour_start=hour_start,
                        hour_end=hour_end,
                        daily_limit=daily_limit,
                        template_specs=support_template_specs,
                        full_time_rest_days=full_time_rest_days,
                        full_time_work_days=full_time_work_days,
                        last_role_by_employee=last_role_by_employee,
                        role_counts_by_employee=role_counts_by_employee,
                        role_targets_by_employee=role_targets_by_employee,
                        full_time_daily_role_plan=full_time_daily_role_plan,
                        all_employees=employees,
                    )

            dynamic_template_specs = _build_gap_driven_template_specs(
                store_mode=store_mode,
                date_obj=date_obj,
                hour_start=hour_start,
                hour_end=hour_end,
                demand_by_day_hour=demand_by_day_hour,
                required_per_hour=required_per_hour,
                schedule_assignments=schedule[date_key],
            )
            if dynamic_template_specs:
                _prefill_realistic_templates(
                    employees=employees,
                    start_date=start_date,
                    date_obj=date_obj,
                    date_key=date_key,
                    schedule_assignments=schedule[date_key],
                    daily_blocks=daily_blocks,
                    assigned_hours=assigned_hours,
                    daily_assigned_hours=daily_assigned_hours,
                    relation_map=relation_map,
                    store_priority=store_priority,
                    key_holder_ids=key_holder_ids,
                    hour_start=hour_start,
                    hour_end=hour_end,
                    daily_limit=daily_limit,
                    template_specs=dynamic_template_specs,
                    full_time_rest_days=full_time_rest_days,
                    full_time_work_days=full_time_work_days,
                    last_role_by_employee=last_role_by_employee,
                    role_counts_by_employee=role_counts_by_employee,
                    role_targets_by_employee=role_targets_by_employee,
                    full_time_daily_role_plan=full_time_daily_role_plan,
                    all_employees=employees,
                )
                template_specs.extend(dynamic_template_specs)

        for hour in range(hour_start, hour_end + 1):
            hour_assignments = []
            target_staff = _hour_target(
                demand_by_day_hour,
                date_obj,
                hour,
                required_per_hour,
                allow_zero_demand=allow_zero_demand_hours,
            )

            for slot in range(target_staff):
                is_opening_hour = hour == opening_hour
                is_closing_hour = hour == closing_hour
                current_closing_staff = sum(1 for item in schedule[date_key] if int(item.get("hour", 0)) == closing_hour)
                current_opening_staff = sum(1 for item in schedule[date_key] if int(item.get("hour", 0)) == opening_hour)
                opening_gap = max(0, opening_target - current_opening_staff)
                closing_gap = max(0, closing_target - current_closing_staff)
                reserved_hours = (opening_gap + closing_gap) * 4
                if (
                    not is_opening_hour
                    and not is_closing_hour
                    and daily_assigned_hours[date_key] >= max(0.0, daily_limit - reserved_hours)
                ):
                    break
                preferred_candidates = []
                fallback_candidates = []
                preferred_candidate_meta = []
                fallback_candidate_meta = []

                for emp in employees:
                    emp_id = str(emp.get("id"))
                    meta = emp.get("meta", {})
                    blocked_slots = set(meta.get("blocked_slots", []))
                    if f"{date_key}|{hour}" in blocked_slots:
                        continue
                    if any(str(item["employee_id"]) == emp_id for item in hour_assignments):
                        continue
                    if not _is_available(emp, start_date, date_obj, hour):
                        continue

                    block_key = (date_key, emp_id)
                    block = daily_blocks.get(block_key)
                    required_hours = _minimum_shift_block_hours(emp, repair_mode=repair_mode)
                    preferred_max_daily_hours = _preferred_max_daily_hours(emp)
                    absolute_max_daily_hours = _absolute_max_daily_hours(emp)
                    external_daily_hours = int(meta.get("external_daily_hours", {}).get(date_key, 0))
                    current_block_hours = 0 if block is None else block["end"] - block["start"] + 1
                    is_new_block = block is None

                    if block is not None and hour != block["end"] + 1:
                        continue
                    if block is not None and hour > int(block.get("max_end", hour_end)):
                        continue
                    if external_daily_hours + current_block_hours >= absolute_max_daily_hours:
                        continue

                    if (
                        hour >= closing_hour - 1
                        and _is_full_time(emp)
                        and external_daily_hours + current_block_hours + 1 > preferred_max_daily_hours
                        and _has_non_overtime_part_time_hour_cover(
                            employees=employees,
                            candidate_employee_id=emp_id,
                            start_date=start_date,
                            target_date=date_obj,
                            date_key=date_key,
                            target_hour=hour,
                            daily_blocks=daily_blocks,
                            relation_map=relation_map,
                            schedule_assignments=schedule[date_key] + hour_assignments,
                            closing_hour=closing_hour,
                        )
                    ):
                        continue

                    if is_new_block:
                        allow_late_close_part_time_start = False
                        prefer_existing_part_time_extension = False
                        if _is_part_time(emp) and hour >= closing_hour - 1:
                            late_close_block_hours = min(required_hours, 4)
                            late_close_start = _find_cover_block_start(
                                emp,
                                start_date,
                                date_obj,
                                hour,
                                late_close_block_hours,
                                hour_start,
                                hour_end,
                            )
                            if late_close_start is not None and external_daily_hours + late_close_block_hours <= preferred_max_daily_hours:
                                allow_late_close_part_time_start = True
                            prefer_existing_part_time_extension = _has_preferred_part_time_extension_candidate(
                                employees=employees,
                                candidate_employee_id=emp_id,
                                start_date=start_date,
                                target_date=date_obj,
                                date_key=date_key,
                                target_hour=hour,
                                daily_blocks=daily_blocks,
                                relation_map=relation_map,
                                schedule_assignments=schedule[date_key] + hour_assignments,
                            )

                        if not _full_time_can_start_new_day(
                            emp,
                            date_key=date_key,
                            full_time_rest_days=full_time_rest_days,
                            full_time_work_days=full_time_work_days,
                        ):
                            continue
                        if not repair_mode:
                            if _is_full_time(emp) and hour not in full_time_start_hours:
                                continue
                            if _is_part_time(emp) and hour not in part_time_start_hours and not allow_late_close_part_time_start:
                                continue
                            if _is_full_time(emp) and hour == opening_hour and opening_plan_employee_ids:
                                if emp_id not in opening_plan_employee_ids:
                                    continue
                            if require_opening_dual_skill and hour == opening_hour and not _is_opening_qualified(emp):
                                continue
                            if store_mode == "light_single_core" and _is_full_time(emp) and len(full_time_start_hours) == 1:
                                only_start = next(iter(full_time_start_hours))
                                if hour != only_start:
                                    continue
                        if absolute_max_daily_hours - external_daily_hours < required_hours:
                            continue
                        if _continuous_hours_available(emp, start_date, date_obj, hour, hour_end) < required_hours:
                            continue
                        if _is_part_time(emp) and prefer_existing_part_time_extension:
                            continue

                    blocked = False
                    relation_penalty = 0.0
                    for assigned in hour_assignments:
                        sev = relation_map.get((emp_id, str(assigned["employee_id"])), 0.0)
                        if sev >= 0.85:
                            blocked = True
                            break
                        relation_penalty += sev * 100.0
                    if blocked:
                        continue

                    score = 0.0
                    score += 100.0 - assigned_hours.get(emp_id, 0) * 5.0
                    score += _nationality_priority_bonus(emp)
                    score += _availability_scarcity_bonus(emp)
                    if meta.get("sg_priority_to_80"):
                        score += 80.0
                    if meta.get("sg_priority_to_160"):
                        score += 30.0

                    score += _store_priority_bonus(emp, store_priority)
                    score += _monthly_hours_bonus(emp)

                    work_score = int(meta.get("work_skill_score", 50))
                    mgmt_score = int(meta.get("management_skill_score", 50))
                    score -= abs(work_score - global_work_avg) * 0.35
                    score -= abs(mgmt_score - global_mgmt_avg) * 0.35
                    if hour <= opening_hour + 1:
                        score += _template_skill_score(emp, "opening_core")
                    elif hour >= closing_hour - 1:
                        score += _template_skill_score(emp, "closing_core")
                    elif hour < 15:
                        score += _template_skill_score(emp, "lunch_peak_part_time")
                    else:
                        score += _template_skill_score(emp, "peak_part_time")

                    proposed_start = hour if block is None else int(block["start"])
                    proposed_end = hour
                    fit_kind = "peak_part_time"
                    if hour <= opening_hour + 1:
                        fit_kind = "opening_core" if _is_full_time(emp) else "lunch_peak_part_time"
                    elif hour >= closing_hour - 2:
                        fit_kind = "closing_core" if _is_full_time(emp) else "close_peak_part_time"
                    elif hour < 15:
                        fit_kind = "swing_core" if _is_full_time(emp) else "lunch_peak_part_time"
                    score += _availability_fit_bonus(
                        emp,
                        start_date=start_date,
                        target_date=date_obj,
                        block_start=proposed_start,
                        block_end=proposed_end,
                        hour_start=opening_hour,
                        hour_end=closing_hour,
                        template_kind=fit_kind,
                    )

                    current_backroom_cover = sum(
                        1
                        for assigned in hour_assignments
                        if _has_backroom_skill(employee_lookup.get(str(assigned["employee_id"]), {}))
                    )
                    if min_backroom_per_hour > 0 and current_backroom_cover < min_backroom_per_hour:
                        if _has_backroom_skill(emp):
                            score += 260.0 * (min_backroom_per_hour - current_backroom_cover)
                        else:
                            score -= 240.0 * (min_backroom_per_hour - current_backroom_cover)

                    current_open_keyholders = sum(1 for assigned in hour_assignments if str(assigned["employee_id"]) in key_holder_ids)
                    if hour == opening_hour and min_opening_keyholders > 0 and current_open_keyholders < min_opening_keyholders:
                        if emp_id in key_holder_ids:
                            score += 220.0 * (min_opening_keyholders - current_open_keyholders)
                        else:
                            score -= 180.0 * (min_opening_keyholders - current_open_keyholders)
                        if require_opening_dual_skill:
                            if _is_opening_qualified(emp):
                                score += 140.0
                            else:
                                score -= 900.0

                    current_close_keyholders = sum(1 for assigned in hour_assignments if str(assigned["employee_id"]) in key_holder_ids)
                    if hour >= closing_hour - 1 and min_closing_keyholders > 0 and current_close_keyholders < min_closing_keyholders:
                        if emp_id in key_holder_ids:
                            score += 220.0 * (min_closing_keyholders - current_close_keyholders)
                        else:
                            score -= 180.0 * (min_closing_keyholders - current_close_keyholders)

                    if hour >= closing_hour - 2:
                        score += _closing_task_skill_count(emp) * 52.0

                    if hour == opening_hour:
                        score += 180.0
                        if _is_full_time(emp):
                            score += 90.0
                        else:
                            score -= 70.0
                    if hour >= closing_hour - 1:
                        if _is_full_time(emp):
                            score += 85.0
                        else:
                            score -= 60.0
                    if hour == closing_hour and emp_id in key_holder_ids:
                        score += 40.0
                    if hour >= closing_hour - 2 and _continuous_hours_available(
                        emp,
                        start_date,
                        date_obj,
                        hour,
                        closing_hour,
                    ) >= (closing_hour - hour + 1):
                        score += 80.0 + (hour - hour_start) * 2.0
                    if slot == 0 and meta.get("backroom_level") in {"proficient", "basic"}:
                        score += 18.0

                    score += _role_continuity_bonus(
                        emp,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                        previous_role=last_role_by_employee.get(emp_id),
                    )
                    score += _rest_rebound_bonus(
                        emp,
                        date_obj=date_obj,
                        full_time_rest_days=full_time_rest_days,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                    )
                    score += _role_balance_bonus(
                        emp,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                        role_counts_by_employee=role_counts_by_employee,
                    )
                    score += _role_rotation_bonus(
                        emp,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                        role_counts_by_employee=role_counts_by_employee,
                        employees=employees,
                    )
                    score += _role_target_bonus(
                        emp,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                        role_counts_by_employee=role_counts_by_employee,
                        role_targets_by_employee=role_targets_by_employee,
                    )
                    score += _daily_role_plan_bonus(
                        emp,
                        date_key=date_key,
                        full_time_daily_role_plan=full_time_daily_role_plan,
                        proposed_start=proposed_start,
                        proposed_end=proposed_end,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                    )

                    if current_block_hours > 0:
                        # Finish minimum-length blocks before opening new ones.
                        score += 320.0
                        if current_block_hours < required_hours:
                            score += 1800.0
                        else:
                            score -= 260.0 + (current_block_hours - required_hours) * 90.0
                        score += _preferred_hours_penalty(
                            emp,
                            external_daily_hours=external_daily_hours,
                            proposed_total_hours=current_block_hours + 1,
                            closing_sensitive=target_hour >= closing_hour - 1,
                        )
                    else:
                        score -= required_hours * 3.0

                    score -= relation_penalty
                    score -= max(0.0, daily_assigned_hours[date_key] - daily_limit) * 6.0

                    proposed_total_hours = current_block_hours + 1
                    within_preferred_hours = external_daily_hours + proposed_total_hours <= preferred_max_daily_hours
                    can_close_cover = _closing_task_skill_count(emp) > 0 or _has_backroom_skill(emp)
                    candidate_meta = {
                        "score": score,
                        "employee": emp,
                        "within_preferred_hours": within_preferred_hours,
                        "is_part_time": _is_part_time(emp),
                        "can_close_cover": can_close_cover,
                    }

                    external_store_days = set(meta.get("external_store_days", []))
                    if date_key in external_store_days:
                        candidate_meta["score"] = score - 600.0
                        fallback_candidates.append((candidate_meta["score"], emp))
                        fallback_candidate_meta.append(candidate_meta)
                    else:
                        preferred_candidates.append((score, emp))
                        preferred_candidate_meta.append(candidate_meta)

                candidate_pool = preferred_candidates if preferred_candidates else fallback_candidates
                candidate_meta_pool = preferred_candidate_meta if preferred_candidates else fallback_candidate_meta
                if not candidate_pool:
                    continue

                candidate_pool = _filter_candidates_by_priority_band(candidate_pool, store_priority)
                filtered_ids = {str(emp.get("id")) for _, emp in candidate_pool}
                candidate_meta_pool = [item for item in candidate_meta_pool if str(item["employee"].get("id")) in filtered_ids]

                if hour >= closing_hour - 1 and candidate_meta_pool:
                    pt_preferred_pool = [
                        (item["score"], item["employee"])
                        for item in candidate_meta_pool
                        if item["is_part_time"] and item["within_preferred_hours"] and item["can_close_cover"]
                    ]
                    if pt_preferred_pool:
                        candidate_pool = pt_preferred_pool
                    else:
                        within_preferred_pool = [
                            (item["score"], item["employee"])
                            for item in candidate_meta_pool
                            if item["within_preferred_hours"]
                        ]
                        if within_preferred_pool:
                            candidate_pool = within_preferred_pool

                selected = max(candidate_pool, key=lambda x: x[0])[1]
                selected_id = str(selected.get("id"))

                hour_assignments.append(
                    {
                        "employee_id": selected.get("id"),
                        "employee_name": selected.get("name", "Unknown"),
                        "shift": _shift_name(hour),
                        "hour": hour,
                    }
                )
                assigned_hours[selected_id] = assigned_hours.get(selected_id, 0) + 1
                daily_assigned_hours[date_key] += 1.0
                block_key = (date_key, selected_id)
                block = daily_blocks.get(block_key)
                if block is None:
                    daily_blocks[block_key] = {"start": hour, "end": hour}
                    _mark_employee_day_worked(selected_id, date_key, full_time_work_days)
                else:
                    block["end"] = hour

            schedule[date_key].extend(hour_assignments)

        if not repair_mode:
            employee_map = {str(emp.get("id")): emp for emp in employees}
            _extend_full_time_late_blocks(
                employees=employees,
                employee_map=employee_map,
                start_date=start_date,
                date_obj=date_obj,
                date_key=date_key,
                schedule_assignments=schedule[date_key],
                daily_blocks=daily_blocks,
                assigned_hours=assigned_hours,
                daily_assigned_hours=daily_assigned_hours,
                relation_map=relation_map,
                hour_start=hour_start,
                closing_hour=closing_hour,
            )

            fill_hours = [closing_hour]
            if opening_hour != closing_hour:
                fill_hours.append(opening_hour)
            fill_hours.extend(
                hour for hour in range(hour_end, hour_start - 1, -1)
                if hour not in {opening_hour, closing_hour}
            )

            for target_hour in fill_hours:
                if daily_assigned_hours[date_key] >= daily_limit and target_hour not in {opening_hour, closing_hour}:
                    break
                if target_hour == opening_hour:
                    target_staff = opening_target
                elif target_hour == closing_hour:
                    target_staff = closing_target
                else:
                    target_staff = _hour_target(
                        demand_by_day_hour,
                        date_obj,
                        target_hour,
                        required_per_hour,
                        allow_zero_demand=allow_zero_demand_hours,
                    )
                while True:
                    if daily_assigned_hours[date_key] >= daily_limit and target_hour not in {opening_hour, closing_hour}:
                        break
                    current_staff = sum(1 for item in schedule[date_key] if int(item.get("hour", 0)) == target_hour)
                    if current_staff >= target_staff:
                        break

                    extension_candidates = _adjacent_extension_candidates(
                        employees=employees,
                        start_date=start_date,
                        date_obj=date_obj,
                        date_key=date_key,
                        target_hour=target_hour,
                        schedule_assignments=schedule[date_key],
                        daily_blocks=daily_blocks,
                        assigned_hours=assigned_hours,
                        store_priority=store_priority,
                        relation_map=relation_map,
                        key_holder_ids=key_holder_ids,
                        opening_hour=opening_hour,
                        closing_hour=closing_hour,
                    )
                    if extension_candidates:
                        _, selected, direction = max(extension_candidates, key=lambda item: item[0])
                        selected_id = str(selected.get("id"))
                        schedule[date_key].append(
                            {
                                "employee_id": selected.get("id"),
                                "employee_name": selected.get("name", "Unknown"),
                                "shift": _shift_name(target_hour),
                                "hour": target_hour,
                            }
                        )
                        assigned_hours[selected_id] = assigned_hours.get(selected_id, 0) + 1
                        daily_assigned_hours[date_key] += 1.0
                        if direction == "forward":
                            daily_blocks[(date_key, selected_id)]["end"] = target_hour
                            daily_blocks[(date_key, selected_id)]["max_end"] = max(
                                int(daily_blocks[(date_key, selected_id)].get("max_end", target_hour)),
                                target_hour,
                            )
                        else:
                            daily_blocks[(date_key, selected_id)]["start"] = target_hour
                        continue

                    candidate_blocks = []
                    assigned_today = {
                        str(item.get("employee_id"))
                        for item in schedule[date_key]
                    }
                    for emp in employees:
                        emp_id = str(emp.get("id"))
                        if emp_id in assigned_today:
                            continue
                        if not _full_time_can_start_new_day(
                            emp,
                            date_key=date_key,
                            full_time_rest_days=full_time_rest_days,
                            full_time_work_days=full_time_work_days,
                        ):
                            continue
                        required_hours = _minimum_shift_block_hours(emp, repair_mode=repair_mode)
                        preferred_max_daily_hours = _preferred_max_daily_hours(emp)
                        absolute_max_daily_hours = _absolute_max_daily_hours(emp)
                        external_daily_hours = int(emp.get("meta", {}).get("external_daily_hours", {}).get(date_key, 0))
                        if absolute_max_daily_hours - external_daily_hours < required_hours:
                            continue
                        block_start = _find_cover_block_start(
                            emp,
                            start_date,
                            date_obj,
                            target_hour,
                            min(required_hours, absolute_max_daily_hours),
                            hour_start,
                            hour_end,
                        )
                        if block_start is None:
                            continue
                        block_hours = min(required_hours, absolute_max_daily_hours)
                        if target_hour not in {opening_hour, closing_hour} and daily_assigned_hours[date_key] + block_hours > daily_limit:
                            continue

                        score = 100.0 - assigned_hours.get(emp_id, 0) * 5.0
                        prio = store_priority.get(emp_id)
                        if prio is not None:
                            score += max(0.0, 36.0 - float(prio) * 6.0)
                        score += _nationality_priority_bonus(emp)
                        if date_key in set(emp.get("meta", {}).get("external_store_days", [])):
                            score -= 600.0
                        if block_start + required_hours - 1 >= closing_hour:
                            score += 120.0
                            score += _template_skill_score(emp, "closing_core")
                            if _is_part_time(emp):
                                score += _late_close_part_time_bonus(emp, store_priority) * 0.75
                        elif block_start <= opening_hour + 1:
                            score += _template_skill_score(emp, "opening_core")
                        else:
                            score += _template_skill_score(emp, "peak_part_time")
                        if emp_id in key_holder_ids and target_hour == closing_hour:
                            score += 120.0
                        score += _preferred_hours_penalty(
                            emp,
                            external_daily_hours=external_daily_hours,
                            proposed_total_hours=block_hours,
                            closing_sensitive=block_start + required_hours - 1 >= closing_hour,
                        )

                        if target_hour == opening_hour:
                            score += 420.0
                            if _is_full_time(emp):
                                score += 100.0
                            else:
                                score -= 90.0
                        if target_hour == closing_hour:
                            score += 500.0
                            if _is_full_time(emp):
                                score += 100.0
                            else:
                                score += 120.0
                        score += _role_continuity_bonus(
                            emp,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                            previous_role=last_role_by_employee.get(emp_id),
                        )
                        score += _rest_rebound_bonus(
                            emp,
                            date_obj=date_obj,
                            full_time_rest_days=full_time_rest_days,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                        )
                        score += _role_balance_bonus(
                            emp,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                            role_counts_by_employee=role_counts_by_employee,
                        )
                        score += _role_rotation_bonus(
                            emp,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                            role_counts_by_employee=role_counts_by_employee,
                            employees=employees,
                        )
                        score += _role_target_bonus(
                            emp,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                            role_counts_by_employee=role_counts_by_employee,
                            role_targets_by_employee=role_targets_by_employee,
                        )
                        score += _daily_role_plan_bonus(
                            emp,
                            date_key=date_key,
                            full_time_daily_role_plan=full_time_daily_role_plan,
                            proposed_start=block_start,
                            proposed_end=block_start + block_hours - 1,
                            opening_hour=opening_hour,
                            closing_hour=closing_hour,
                        )

                        candidate_blocks.append((score, emp, block_start, block_hours))

                    if not candidate_blocks:
                        break

                    candidate_blocks = _filter_candidates_by_priority_band(candidate_blocks, store_priority, employee_index=1)
                    _, selected, block_start, block_hours = max(candidate_blocks, key=lambda item: item[0])
                    selected_id = str(selected.get("id"))
                    for block_hour in range(block_start, block_start + block_hours):
                        schedule[date_key].append(
                            {
                                "employee_id": selected.get("id"),
                                "employee_name": selected.get("name", "Unknown"),
                                "shift": _shift_name(block_hour),
                                "hour": block_hour,
                            }
                        )
                    assigned_hours[selected_id] = assigned_hours.get(selected_id, 0) + block_hours
                    daily_assigned_hours[date_key] += float(block_hours)
                    daily_blocks[(date_key, selected_id)] = {
                        "start": block_start,
                        "end": block_start + block_hours - 1,
                        "kind": "fallback",
                        "max_end": block_start + block_hours - 1,
                    }
                    _mark_employee_day_worked(selected_id, date_key, full_time_work_days)

    employee_map = {str(emp.get("id")): emp for emp in employees}
    if repair_mode:
        for date_key, assignments in list(schedule.items()):
            assignments.sort(key=lambda item: (int(item.get("hour", 0)), str(item.get("employee_id"))))
            schedule[date_key] = assignments
        return schedule

    for date_key, assignments in list(schedule.items()):
        date_obj = datetime.strptime(date_key, "%Y-%m-%d")
        working_assignments = list(assignments)

        while True:
            hours_by_employee = {}
            for item in working_assignments:
                emp_id = str(item.get("employee_id"))
                hours_by_employee.setdefault(emp_id, []).append(item)

            short_blocks = []
            for emp_id, employee_assignments in hours_by_employee.items():
                employee_assignments.sort(key=lambda item: int(item.get("hour", 0)))
                required_hours = _required_daily_hours(employee_map.get(emp_id, {}))
                if len(employee_assignments) < required_hours:
                    short_blocks.append((emp_id, employee_assignments))

            if not short_blocks:
                break

            replaced_any = False
            short_blocks.sort(key=lambda item: len(item[1]))
            hour_index = _build_hour_index(working_assignments)

            for short_emp_id, short_assignments in short_blocks:
                short_hours = sorted(int(item.get("hour", 0)) for item in short_assignments)
                deficit_hours = []
                for hour in short_hours:
                    current_staff = len(hour_index.get(hour, []))
                    target_staff = _hour_target(demand_by_day_hour, date_obj, hour, required_per_hour)
                    if current_staff - 1 < target_staff:
                        deficit_hours.append(hour)

                if not deficit_hours:
                    removed_hours = len(short_assignments)
                    working_assignments = [
                        item for item in working_assignments if str(item.get("employee_id")) != short_emp_id
                    ]
                    assigned_hours[short_emp_id] = max(0, assigned_hours.get(short_emp_id, 0) - removed_hours)
                    daily_blocks.pop((date_key, short_emp_id), None)
                    replaced_any = True
                    break

                replacement = _find_short_block_replacement(
                    employees=employees,
                    employee_map=employee_map,
                    start_date=start_date,
                    date_obj=date_obj,
                    date_key=date_key,
                    cover_hours=deficit_hours,
                    short_employee_id=short_emp_id,
                    schedule_assignments=working_assignments,
                    daily_blocks=daily_blocks,
                    assigned_hours=assigned_hours,
                    relation_map=relation_map,
                    store_priority=store_priority,
                    key_holder_ids=key_holder_ids,
                    hour_start=hour_start,
                    hour_end=hour_end,
                )
                if replacement is None:
                    continue

                replacement_emp = replacement["employee"]
                replacement_emp_id = str(replacement_emp.get("id"))
                replacement_hours = sorted(set(int(hour) for hour in replacement["hours_to_add"]))
                removed_hours = len(short_assignments)

                working_assignments = [
                    item for item in working_assignments if str(item.get("employee_id")) != short_emp_id
                ]
                assigned_hours[short_emp_id] = max(0, assigned_hours.get(short_emp_id, 0) - removed_hours)
                added_hours = 0
                for hour in replacement_hours:
                    if any(
                        str(item.get("employee_id")) == replacement_emp_id and int(item.get("hour", 0)) == hour
                        for item in working_assignments
                    ):
                        continue
                    added_hours += 1
                    working_assignments.append(
                        {
                            "employee_id": replacement_emp.get("id"),
                            "employee_name": replacement_emp.get("name", "Unknown"),
                            "shift": _shift_name(hour),
                            "hour": hour,
                        }
                    )
                assigned_hours[replacement_emp_id] = assigned_hours.get(replacement_emp_id, 0) + added_hours

                new_hours = sorted(
                    int(item.get("hour", 0))
                    for item in working_assignments
                    if str(item.get("employee_id")) == replacement_emp_id
                )
                if new_hours:
                    daily_blocks[(date_key, replacement_emp_id)] = {
                        "start": new_hours[0],
                        "end": new_hours[-1],
                    }
                daily_blocks.pop((date_key, short_emp_id), None)
                replaced_any = True
                break

            if not replaced_any:
                break

        _ensure_full_time_daily_assignment(
            employees=employees,
            start_date=start_date,
            date_obj=date_obj,
            date_key=date_key,
            schedule_assignments=working_assignments,
            daily_blocks=daily_blocks,
            assigned_hours=assigned_hours,
            relation_map=relation_map,
            store_priority=store_priority,
            key_holder_ids=key_holder_ids,
            hour_start=hour_start,
            hour_end=hour_end,
            full_time_rest_days=full_time_rest_days,
            full_time_work_days=full_time_work_days,
            full_time_daily_role_plan=full_time_daily_role_plan,
        )

        _prune_redundant_backup_part_time_blocks(
            schedule_assignments=working_assignments,
            date_obj=date_obj,
            date_key=date_key,
            daily_blocks=daily_blocks,
            assigned_hours=assigned_hours,
            employee_map=employee_map,
            store_priority=store_priority,
            demand_by_day_hour=demand_by_day_hour,
            required_per_hour=required_per_hour,
        )

        _upgrade_backup_part_time_blocks(
            employees=employees,
            start_date=start_date,
            date_obj=date_obj,
            date_key=date_key,
            schedule_assignments=working_assignments,
            daily_blocks=daily_blocks,
            assigned_hours=assigned_hours,
            relation_map=relation_map,
            store_priority=store_priority,
            hour_start=hour_start,
            hour_end=hour_end,
        )

        _merge_redundant_part_time_tail_blocks(
            employees=employees,
            start_date=start_date,
            date_obj=date_obj,
            date_key=date_key,
            schedule_assignments=working_assignments,
            daily_blocks=daily_blocks,
            assigned_hours=assigned_hours,
            relation_map=relation_map,
            store_priority=store_priority,
            demand_by_day_hour=demand_by_day_hour,
            required_per_hour=required_per_hour,
        )

        _reassign_full_time_overtime_tail_hours(
            employees=employees,
            start_date=start_date,
            date_obj=date_obj,
            date_key=date_key,
            schedule_assignments=working_assignments,
            daily_blocks=daily_blocks,
            assigned_hours=assigned_hours,
            relation_map=relation_map,
            store_priority=store_priority,
            closing_hour=closing_hour,
        )

        _prune_redundant_overtime_tail_hours(
            employees=employees,
            date_obj=date_obj,
            date_key=date_key,
            schedule_assignments=working_assignments,
            daily_blocks=daily_blocks,
            demand_by_day_hour=demand_by_day_hour,
            required_per_hour=required_per_hour,
            key_holder_ids=key_holder_ids,
            min_closing_keyholders=min_closing_keyholders,
            min_backroom_per_hour=min_backroom_per_hour,
            closing_hour=closing_hour,
        )

        working_assignments.sort(key=lambda item: (int(item.get("hour", 0)), str(item.get("employee_id"))))
        schedule[date_key] = working_assignments

        day_hours_by_employee: dict[str, list[int]] = {}
        for item in working_assignments:
            emp_id = str(item.get("employee_id"))
            day_hours_by_employee.setdefault(emp_id, []).append(int(item.get("hour", 0)))
        for emp in employees:
            emp_id = str(emp.get("id"))
            hours = sorted(day_hours_by_employee.get(emp_id, []))
            if not hours:
                continue
            role = _block_role_bucket(
                emp,
                block_start=hours[0],
                block_end=hours[-1],
                opening_hour=opening_hour,
                closing_hour=closing_hour,
            )
            last_role_by_employee[emp_id] = role
            role_counts = role_counts_by_employee.setdefault(emp_id, {})
            role_counts[role] = role_counts.get(role, 0) + 1

    return schedule









