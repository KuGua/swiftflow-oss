# SwiftFlow 角色与权限矩阵

更新时间：2026-04-06

## 目标

将现有偏技术命名的角色体系：

- `super_admin`
- `admin`
- `store_manager`

重构为更符合业务语义、且能支持多区域多门店管理的权限体系。

本方案优先解决：

- 角色命名与业务职责不一致
- 区域经理缺失
- 员工角色权限不足够明确
- 页面与接口权限范围不统一

## 建议角色

### 1. `admin`

系统管理员，主要用于老板或总部负责人。

职责定位：

- 负责人和角色管理员
- 管用户、管门店主数据
- 不直接参与排班执行

### 2. `area_manager`

区域经理，负责一个区域内多个门店的运营执行。

职责定位：

- 管区域内门店
- 管区域内员工
- 管区域内排班
- 可在本区域内指派店长

### 3. `store_manager`

店长，只负责自己所属门店。

职责定位：

- 管本店排班
- 管本店员工资料
- 管本店规则与人力需求
- 不改门店基础主数据

### 4. `staff`

普通员工，新用户默认角色。

职责定位：

- 看自己的排班
- 看自己本周参与门店的整周排班
- 维护自己的时间相关信息

### 5. `developer`

开发/维护角色，建议作为独立技术角色或附加权限维度。

职责定位：

- 调试
- 排查问题
- 查看诊断信息
- 技术维护工具

建议不要让 `developer` 直接替代 `admin` 的业务管理职责。

## 角色矩阵

| 能力 | admin | area_manager | store_manager | staff | developer |
|---|---|---|---|---|---|
| 查看全部门店 | 是 | 否，仅区域内 | 否，仅本店 | 否 | 视调试权限 |
| 查看全部排班 | 是，只读 | 否，仅区域内 | 否，仅本店 | 否 | 视调试权限 |
| 编辑排班 | 否 | 是，区域内 | 是，本店 | 否 | 不建议默认开放 |
| 生成排班 | 否 | 是，区域内 | 是，本店 | 否 | 不建议默认开放 |
| 编辑门店基础信息 | 是 | 是，区域内 | 否 | 否 | 不建议默认开放 |
| 编辑门店规则 | 否 | 建议允许，区域内 | 是，本店 | 否 | 不建议默认开放 |
| 编辑每小时人力需求 | 否 | 建议允许，区域内 | 是，本店 | 否 | 不建议默认开放 |
| 编辑员工资料 | 否 | 是，区域内 | 是，本店 | 否，仅本人有限字段 | 不建议默认开放 |
| 编辑员工可用时间 | 否 | 否 | 否 | 是，仅本人 | 可用于调试，不建议默认开放 |
| 管理用户角色 | 是 | 否 | 否 | 否 | 否 |
| 指派/调整店长 | 否 | 是，仅区域内 | 否 | 否 | 否 |
| 查看个人参与门店整周排班 | 是 | 是 | 是 | 是 | 视调试权限 |
| 访问工作台 | 是 | 是 | 是 | 否 | 可单独提供开发工作台 |
| 访问员工管理 | 是 | 是 | 是，本店范围 | 否 | 视调试权限 |
| 访问店铺管理 | 是 | 是，区域内 | 是，本店范围 | 否 | 视调试权限 |

## 数据范围

权限判断不能只看角色，还要看作用域。

### `admin`

- 作用域：全平台

### `area_manager`

- 作用域：所属区域内的门店、员工、排班
- 可指派区域内门店的店长
- 不可跨区域操作

### `store_manager`

- 作用域：所属门店
- 不可跨店查看或编辑非授权门店数据

### `staff`

- 作用域：本人
- 排班查看扩展为：
  - 可查看本人排班
  - 可查看本周被安排参与的所有门店
  - 可查看这些门店对应的整周排班
- 不可查看未参与门店的排班

## 建议新增的数据模型

### 1. 角色枚举扩展

当前：

- `super_admin`
- `admin`
- `store_manager`

建议迁移为：

- `admin`
- `area_manager`
- `store_manager`
- `staff`
- `developer`

兼容迁移建议：

- 现有 `super_admin` 迁移为 `admin`
- 现有 `admin` 视业务需要迁移为 `area_manager` 或保留为 `admin`
- 现有 `store_manager` 保留

### 2. 区域实体

建议新增：

- `areas`
  - `id`
  - `name`

### 3. 门店归属区域

在 `stores` 上增加：

- `area_id`

### 4. 用户区域权限

建议新增：

- `user_area_access`
  - `user_id`
  - `area_id`

用于表达区域经理可以管理哪些区域。

### 5. 店长指派关系

如果一个门店未来可能有多个店长候选，建议不要只靠 `users.role_id` 表达。

建议新增：

- `store_manager_assignments`
  - `user_id`
  - `store_id`
  - `is_primary`

如果保持“一人一个全局角色 + 通过门店授权判断”，也可以先复用现有 `user_store_access`，但长期看推荐拆开。

## 页面权限建议

### 工作台

- `admin`：可看全局总览
- `area_manager`：看区域总览
- `store_manager`：看本店总览
- `staff`：不显示工作台，直接进入个人排班页

### 排班中心

- `admin`：只读
- `area_manager`：区域内可编辑、可生成
- `store_manager`：本店可编辑、可生成
- `staff`：只看本人相关排班入口，不进入运营版排班中心

### 员工管理

- `admin`：只读或关闭编辑入口
- `area_manager`：区域内员工资料可编辑，不可改员工可用时间
- `store_manager`：本店员工资料可编辑，不可改员工可用时间
- `staff`：仅个人资料页，且只允许维护本人时间相关字段

### 店铺管理

- `admin`：可改门店基础信息；规则和需求建议只读
- `area_manager`：区域内门店可编辑
- `store_manager`：本店仅可改规则和人力需求，不可改门店基础信息
- `staff`：不可访问

## 接口权限建议

### 当前后端中已明显受影响的接口

见 [app.py](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Backend\app.py)：

- `/api/users`
- `/api/me`
- `/api/stores`
- `/api/stores/{store_id}/hours`
- `/api/users/{user_id}/store-access`
- `/api/home-summary`
- `/api/schedules`
- `/api/schedules/repair`
- `/api/employees`
- `/api/employees/{employee_id}`
- `/api/employees/relations`
- `/api/stores/{store_id}/rule-config`
- `/api/stores/{store_id}/staffing-demand`
- `/api/generate-and-save-all-schedules`
- `/api/generate-and-save-store-schedule`

### 当前后端权限函数需要重构

当前：

- `can_manage_store`
- `can_update_store_hours`
- `can_manage_employee`
- `can_edit_employee_availability`
- `is_admin_role`

建议重构为更细粒度能力函数，例如：

- `can_view_store(user, store_id)`
- `can_edit_store_profile(user, store_id)`
- `can_edit_store_rules(user, store_id)`
- `can_edit_staffing_demand(user, store_id)`
- `can_view_schedule(user, store_id, week_start)`
- `can_edit_schedule(user, store_id)`
- `can_generate_schedule(user, store_id)`
- `can_view_employee(user, employee_id)`
- `can_edit_employee_profile(user, employee_id)`
- `can_edit_employee_availability(user, employee_id)`
- `can_assign_store_manager(user, store_id)`
- `can_manage_user_role(user, target_user_id)`

## 前端受影响位置

### 角色文案与菜单

见：

- [App.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\App.vue)
- [HomeView.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\views\HomeView.vue)
- [LoginView.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\views\LoginView.vue)

### 页面内权限判断

见：

- [EmployeeManagement.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\views\EmployeeManagement.vue)
- [StoreManagement.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\views\StoreManagement.vue)
- [ShiftSchedule.vue](c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Frontend\src\views\ShiftSchedule.vue)

当前这些页面里多数还是直接用：

- `super_admin`
- `admin`
- `store_manager`

做硬编码判断，需要改成：

- 新角色枚举
- 作用域判断结果
- 前端菜单显隐

## 推荐实施顺序

### 第一阶段：角色模型与数据库

- 扩展/替换 `RoleCode`
- 增加区域模型与关系表
- 增加区域经理与门店店长的作用域绑定

### 第二阶段：后端权限函数

- 重构权限判断函数
- 将接口从“按角色”改为“按角色 + 作用域”

### 第三阶段：前端菜单与页面显隐

- 工作台、排班中心、员工管理、店铺管理按新权限显示
- `staff` 单独提供“个人排班/个人资料”入口

### 第四阶段：角色管理后台

- `admin` 可设置区域经理
- `area_manager` 可指派本区域门店店长

## 关于 `developer`

建议不要直接混入业务层级。

更稳的做法：

- 业务角色：`admin / area_manager / store_manager / staff`
- 技术附加权限：`developer_capability`

这样可以避免：

- 技术人员天然拿到业务最高权限
- 业务管理员天然拿到系统调试能力

## 当前结论

建议正式采用以下业务角色体系：

- `admin`
- `area_manager`
- `store_manager`
- `staff`

并把 `developer` 作为技术维护权限单独设计。
