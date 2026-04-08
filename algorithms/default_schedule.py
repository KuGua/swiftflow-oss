# 默认排班算法
def generate_schedule(employees: list, rules: dict) -> dict:
    """
    默认排班算法 - 简单轮班
    :param employees: 员工列表
    :param rules: 排班规则
    :return: 排班表
    """
    import datetime
    
    cycle_days = rules.get("cycle_days", 7)
    start_date = rules.get("start_date", "2026-01-20")
    
    # 解析开始日期
    current_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    
    schedule = {}
    employee_count = len(employees)
    
    if employee_count == 0:
        return {}
    
    # 简单轮班：每天分配一个员工
    for day in range(cycle_days):
        date_str = (current_date + datetime.timedelta(days=day)).strftime("%Y-%m-%d")
        employee_index = day % employee_count
        schedule[date_str] = [{
            "employee_id": employees[employee_index]["id"],
            "employee_name": employees[employee_index]["name"],
            "shift": "早班" if day % 3 == 0 else "中班" if day % 3 == 1 else "晚班"
        }]
    
    return schedule
