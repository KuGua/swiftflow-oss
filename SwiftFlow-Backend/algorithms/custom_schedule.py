# SwiftFlow-Backend/algorithms/custom_schedule.py
def generate_schedule(employees: list, rules: dict) -> dict:
    """
    自定义排班算法 - 智能分配
    :param employees: 员工列表 [ { "id": "E001", "name": "张三", "department": "销售部" }, ... ]
    :param rules: 排班规则 { 
        "cycle_days": 7, 
        "start_date": "2026-01-20",
        "max_shifts_per_employee": 5,
        "required_shifts_per_day": 2 
    }
    :return: 排班表 { "2026-01-20": [ { "employee_id": "E001", "employee_name": "张三", "shift": "早班" } ], ... }
    """
    import datetime
    from collections import defaultdict
    
    # 默认参数
    cycle_days = rules.get("cycle_days", 7)
    start_date = rules.get("start_date", "2026-01-20")
    max_shifts_per_employee = rules.get("max_shifts_per_employee", 5)
    required_shifts_per_day = rules.get("required_shifts_per_day", 1)
    
    # 解析开始日期
    try:
        current_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        current_date = datetime.datetime(2026, 1, 20)
    
    if not employees:
        return {}
    
    schedule = defaultdict(list)
    employee_shift_count = {emp["id"]: 0 for emp in employees}
    
    # 班次类型
    shifts = ["早班", "中班", "晚班"]
    
    for day in range(cycle_days):
        date_str = (current_date + datetime.timedelta(days=day)).strftime("%Y-%m-%d")
        
        # 为当天分配所需班次数
        available_employees = [
            emp for emp in employees 
            if employee_shift_count[emp["id"]] < max_shifts_per_employee
        ]
        
        if not available_employees:
            # 如果没有可用员工，重置计数（应急处理）
            employee_shift_count = {emp["id"]: 0 for emp in employees}
            available_employees = employees
        
        # 分配班次
        for shift_index in range(required_shifts_per_day):
            if available_employees:
                # 轮询分配（避免总是同一个人）
                emp_index = (day + shift_index) % len(available_employees)
                selected_employee = available_employees[emp_index]
                
                schedule[date_str].append({
                    "employee_id": selected_employee["id"],
                    "employee_name": selected_employee["name"],
                    "shift": shifts[(day + shift_index) % len(shifts)]
                })
                
                employee_shift_count[selected_employee["id"]] += 1
    
    return dict(schedule)