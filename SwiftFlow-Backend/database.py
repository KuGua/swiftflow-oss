import os
from pathlib import Path
from datetime import date, datetime, time, timedelta
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

DEFAULT_SQLITE_DB_PATH = Path(__file__).resolve().parent / "swiftflow.db"


def normalize_database_url(raw_url: str | None) -> str:
    value = (raw_url or "").strip()
    if not value:
        return f"sqlite:///{DEFAULT_SQLITE_DB_PATH.as_posix()}"
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://") and "+" not in value.split("://", 1)[0]:
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
    pool_recycle=1800 if not IS_SQLITE else -1,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)
Base = declarative_base()


def enum_type(enum_cls: type[Enum]) -> SqlEnum:
    return SqlEnum(enum_cls, native_enum=False, validate_strings=True, length=64)


class RoleCode(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    AREA_MANAGER = "area_manager"
    STORE_MANAGER = "store_manager"
    STAFF = "staff"
    DEVELOPER = "developer"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class NationalityStatus(str, Enum):
    SG_CITIZEN = "sg_citizen"
    SG_PR = "sg_pr"
    OTHER = "other"


class SkillLevel(str, Enum):
    NONE = "none"
    BASIC = "basic"
    PROFICIENT = "proficient"


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(enum_type(RoleCode), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)

    users = relationship("User", back_populates="role")


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    stores = relationship("Store", back_populates="area")
    user_links = relationship(
        "UserAreaAccess", back_populates="area", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    password_hash = Column(String(256), nullable=False, default="")
    is_active = Column(Boolean, default=True, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)

    role = relationship("Role", back_populates="users")
    employee = relationship("Employee")
    store_links = relationship(
        "UserStoreAccess", back_populates="user", cascade="all, delete-orphan"
    )
    area_links = relationship(
        "UserAreaAccess", back_populates="user", cascade="all, delete-orphan"
    )


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True, index=True)
    open_time = Column(Time, nullable=False, default=time(9, 0))
    close_time = Column(Time, nullable=False, default=time(23, 0))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    area = relationship("Area", back_populates="stores")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    employment_status = Column(enum_type(EmploymentStatus), nullable=False, default=EmploymentStatus.ACTIVE)
    employment_type = Column(enum_type(EmploymentType), nullable=False)
    nationality_status = Column(enum_type(NationalityStatus), nullable=False, default=NationalityStatus.OTHER)
    work_skill_score = Column(Integer, nullable=False, default=50)
    management_skill_score = Column(Integer, nullable=False, default=50)
    phone_country_code = Column(String(8), nullable=True, default=None)
    phone_number = Column(String(32), nullable=True, default=None, index=True)
    preferred_shift = Column(String(32), nullable=False, default="no_preference")
    monthly_worked_hours = Column(Float, nullable=False, default=0.0)
    hours_month = Column(String(7), nullable=False, default=lambda: datetime.utcnow().strftime("%Y-%m"))
    availability_anchor_monday = Column(Date, nullable=False, default=lambda: current_week_monday())
    availability_customized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    availabilities = relationship(
        "EmployeeAvailability", back_populates="employee", cascade="all, delete-orphan"
    )
    store_links = relationship(
        "EmployeeStoreAccess", back_populates="employee", cascade="all, delete-orphan"
    )
    skills = relationship(
        "EmployeeSkill", cascade="all, delete-orphan"
    )


class EmployeeAvailability(Base):
    __tablename__ = "employee_availabilities"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    week_offset = Column(Integer, nullable=False)  # 0=鏈懆, 1=涓嬪懆
    day_of_week = Column(Integer, nullable=False)  # 0=鍛ㄤ竴 ... 6=鍛ㄦ棩
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    employee = relationship("Employee", back_populates="availabilities")


class EmployeeStoreAccess(Base):
    __tablename__ = "employee_store_access"

    employee_id = Column(Integer, ForeignKey("employees.id"), primary_key=True)
    store_id = Column(Integer, ForeignKey("stores.id"), primary_key=True)
    priority = Column(Integer, nullable=True)
    has_key = Column(Boolean, nullable=False, default=False)

    employee = relationship("Employee", back_populates="store_links")
    store = relationship("Store")


class UserStoreAccess(Base):
    __tablename__ = "user_store_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    store_id = Column(Integer, ForeignKey("stores.id"), primary_key=True)

    user = relationship("User", back_populates="store_links")
    store = relationship("Store")


class UserAreaAccess(Base):
    __tablename__ = "user_area_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    area_id = Column(Integer, ForeignKey("areas.id"), primary_key=True)

    user = relationship("User", back_populates="area_links")
    area = relationship("Area", back_populates="user_links")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (
        UniqueConstraint("employee_id", "skill_code", name="uq_employee_skill"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    skill_code = Column(String(64), nullable=False, index=True)
    level = Column(enum_type(SkillLevel), nullable=False, default=SkillLevel.NONE)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="skills")


class EmployeeRelation(Base):
    __tablename__ = "employee_relations"
    __table_args__ = (
        UniqueConstraint("employee_id_a", "employee_id_b", name="uq_employee_relation_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id_a = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    employee_id_b = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    relation_type = Column(String(32), nullable=False, default="bad")
    severity = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class StoreScheduleRuleConfig(Base):
    __tablename__ = "store_schedule_rule_configs"
    __table_args__ = (
        UniqueConstraint("store_id", name="uq_store_schedule_rule_config_store"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    schedule_archetype = Column(String(64), nullable=False, default="auto")
    weekday_total_hours_limit = Column(Float, nullable=False, default=40.0)
    weekend_total_hours_limit = Column(Float, nullable=False, default=45.0)
    sg_part_time_min_hours = Column(Float, nullable=False, default=80.0)
    sg_part_time_target_hours = Column(Float, nullable=False, default=160.0)
    target_160_last_week_days = Column(Integer, nullable=False, default=7)
    min_backroom_per_hour = Column(Integer, nullable=False, default=1)
    require_opening_dual_skill = Column(Boolean, nullable=False, default=True)
    min_opening_keyholders = Column(Integer, nullable=False, default=1)
    min_closing_keyholders = Column(Integer, nullable=False, default=1)
    store_key_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    store = relationship("Store")


class StoreStaffingDemand(Base):
    __tablename__ = "store_staffing_demands"
    __table_args__ = (
        UniqueConstraint("store_id", "day_of_week", "hour", name="uq_store_staffing_demand"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)  # 0=Mon ... 6=Sun
    hour = Column(Integer, nullable=False, index=True)
    min_staff = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    store = relationship("Store")


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    __table_args__ = (
        UniqueConstraint("store_id", "work_date", "hour", "employee_id", name="uq_schedule_store_date_hour_emp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False)  # 9-22
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_week_monday(today: date | None = None) -> date:
    base = today or date.today()
    return base - timedelta(days=base.weekday())


def current_month_key(today: date | None = None) -> str:
    base = today or date.today()
    return base.strftime("%Y-%m")


def ensure_employee_month_hours(employee: Employee, today: date | None = None) -> None:
    month_key = current_month_key(today)
    if employee.hours_month != month_key:
        employee.hours_month = month_key
        employee.monthly_worked_hours = 0.0


def roll_employee_availability_window(db, employee: Employee, today: date | None = None) -> None:
    target_monday = current_week_monday(today)
    if employee.availability_anchor_monday == target_monday:
        return

    diff_days = (target_monday - employee.availability_anchor_monday).days
    if diff_days <= 0:
        employee.availability_anchor_monday = target_monday
        return

    step_weeks = diff_days // 7
    all_rows = list(employee.availabilities)

    if step_weeks == 1:
        for row in all_rows:
            if row.week_offset == 0:
                db.delete(row)
            elif row.week_offset == 1:
                row.week_offset = 0
    else:
        for row in all_rows:
            db.delete(row)

    employee.availability_anchor_monday = target_monday


def ensure_schema():
    Base.metadata.create_all(bind=engine)
    if IS_SQLITE:
        _ensure_sqlite_area_and_role_columns()
        _ensure_sqlite_employee_status_column()
        _ensure_sqlite_rule_columns_and_tables()
        _ensure_sqlite_employee_contact_columns()


def seed_core_data(db):
    role_map = {
        RoleCode.SUPER_ADMIN: "Super Admin",
        RoleCode.ADMIN: "Admin",
        RoleCode.AREA_MANAGER: "Area Manager",
        RoleCode.STORE_MANAGER: "Store Manager",
        RoleCode.STAFF: "Staff",
        RoleCode.DEVELOPER: "Developer",
    }
    for code, name in role_map.items():
        exists = db.query(Role).filter(Role.code == code).first()
        if not exists:
            db.add(Role(code=code, name=name))
        elif exists.name != name:
            exists.name = name
    db.commit()

    admin_role = db.query(Role).filter(Role.code == RoleCode.ADMIN).first()

    legacy_usernames = set()
    for legacy_user in db.query(User).filter(User.username.in_(legacy_usernames)).all():
        db.delete(legacy_user)
    db.flush()

    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            full_name="Admin",
            role_id=admin_role.id,
            password_hash="admin",
            is_active=True,
        )
        db.add(admin_user)
    else:
        admin_user.full_name = "Admin"
        admin_user.role_id = admin_role.id
        admin_user.password_hash = "admin"
        admin_user.is_active = True
        admin_user.employee_id = None
        for link in list(admin_user.store_links):
            db.delete(link)
        for link in list(admin_user.area_links):
            db.delete(link)
    db.commit()

    default_area = db.query(Area).filter(Area.name == "Default Area").first()
    if default_area:
        db.query(UserAreaAccess).filter(UserAreaAccess.area_id == default_area.id).delete(
            synchronize_session=False
        )
        db.query(Store).filter(Store.area_id == default_area.id).update(
            {Store.area_id: None},
            synchronize_session=False,
        )
        db.delete(default_area)
        db.commit()


def init_db_and_seed():
    ensure_schema()
    db = SessionLocal()
    try:
        seed_core_data(db)
    finally:
        db.close()


def _ensure_sqlite_area_and_role_columns():
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS areas ("
            "id INTEGER PRIMARY KEY, "
            "name VARCHAR(128) NOT NULL UNIQUE, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS user_area_access ("
            "user_id INTEGER NOT NULL, "
            "area_id INTEGER NOT NULL, "
            "PRIMARY KEY (user_id, area_id), "
            "FOREIGN KEY(user_id) REFERENCES users(id), "
            "FOREIGN KEY(area_id) REFERENCES areas(id))"
        )
        cursor.execute("PRAGMA table_info(stores)")
        store_columns = {row[1] for row in cursor.fetchall()}
        if store_columns and "area_id" not in store_columns:
            cursor.execute(
                "ALTER TABLE stores ADD COLUMN area_id INTEGER REFERENCES areas(id)"
            )
        cursor.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in cursor.fetchall()}
        if user_columns and "employee_id" not in user_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN employee_id INTEGER REFERENCES employees(id)"
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_sqlite_employee_status_column():
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [row[1] for row in cursor.fetchall()]
        if columns and "employment_status" not in columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN employment_status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE'"
            )
            conn.commit()
    finally:
        conn.close()


def _ensure_sqlite_rule_columns_and_tables():
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        employee_columns = {row[1] for row in cursor.fetchall()}
        if "nationality_status" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN nationality_status VARCHAR(16) NOT NULL DEFAULT 'OTHER'"
            )
        if "work_skill_score" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN work_skill_score INTEGER NOT NULL DEFAULT 50"
            )
        if "management_skill_score" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN management_skill_score INTEGER NOT NULL DEFAULT 50"
            )
        if "preferred_shift" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN preferred_shift VARCHAR(32) NOT NULL DEFAULT 'no_preference'"
            )

        cursor.execute("PRAGMA table_info(employee_store_access)")
        access_columns = {row[1] for row in cursor.fetchall()}
        if "priority" not in access_columns:
            cursor.execute(
                "ALTER TABLE employee_store_access ADD COLUMN priority INTEGER"
            )
        if "has_key" not in access_columns:
            cursor.execute(
                "ALTER TABLE employee_store_access ADD COLUMN has_key BOOLEAN NOT NULL DEFAULT 0"
            )

        cursor.execute("PRAGMA table_info(store_schedule_rule_configs)")
        rule_columns = {row[1] for row in cursor.fetchall()}
        if rule_columns and "schedule_archetype" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN schedule_archetype VARCHAR(64) NOT NULL DEFAULT 'auto'"
            )
        if rule_columns and "min_backroom_per_hour" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN min_backroom_per_hour INTEGER NOT NULL DEFAULT 1"
            )
        if rule_columns and "require_opening_dual_skill" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN require_opening_dual_skill BOOLEAN NOT NULL DEFAULT 1"
            )
        if rule_columns and "min_opening_keyholders" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN min_opening_keyholders INTEGER NOT NULL DEFAULT 1"
            )
        if rule_columns and "min_closing_keyholders" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN min_closing_keyholders INTEGER NOT NULL DEFAULT 1"
            )
        if rule_columns and "store_key_count" not in rule_columns:
            cursor.execute(
                "ALTER TABLE store_schedule_rule_configs ADD COLUMN store_key_count INTEGER NOT NULL DEFAULT 0"
            )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_skills (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                skill_code VARCHAR(64) NOT NULL,
                level VARCHAR(16) NOT NULL DEFAULT 'NONE',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_skill ON employee_skills(employee_id, skill_code)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_relations (
                id INTEGER PRIMARY KEY,
                employee_id_a INTEGER NOT NULL,
                employee_id_b INTEGER NOT NULL,
                relation_type VARCHAR(32) NOT NULL DEFAULT 'bad',
                severity FLOAT NOT NULL DEFAULT 0.5,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(employee_id_a) REFERENCES employees(id),
                FOREIGN KEY(employee_id_b) REFERENCES employees(id)
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_relation_pair ON employee_relations(employee_id_a, employee_id_b)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS store_schedule_rule_configs (
                id INTEGER PRIMARY KEY,
                store_id INTEGER NOT NULL,
                schedule_archetype VARCHAR(64) NOT NULL DEFAULT 'auto',
                weekday_total_hours_limit FLOAT NOT NULL DEFAULT 40.0,
                weekend_total_hours_limit FLOAT NOT NULL DEFAULT 45.0,
                sg_part_time_min_hours FLOAT NOT NULL DEFAULT 80.0,
                sg_part_time_target_hours FLOAT NOT NULL DEFAULT 160.0,
                target_160_last_week_days INTEGER NOT NULL DEFAULT 7,
                min_backroom_per_hour INTEGER NOT NULL DEFAULT 1,
                require_opening_dual_skill BOOLEAN NOT NULL DEFAULT 1,
                min_opening_keyholders INTEGER NOT NULL DEFAULT 1,
                min_closing_keyholders INTEGER NOT NULL DEFAULT 1,
                store_key_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(store_id) REFERENCES stores(id)
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_store_schedule_rule_config_store ON store_schedule_rule_configs(store_id)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS store_staffing_demands (
                id INTEGER PRIMARY KEY,
                store_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                min_staff INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(store_id) REFERENCES stores(id)
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_store_staffing_demand ON store_staffing_demands(store_id, day_of_week, hour)"
        )

        conn.commit()
    finally:
        conn.close()


def _ensure_sqlite_employee_contact_columns():
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        employee_columns = {row[1] for row in cursor.fetchall()}
        if "availability_customized" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN availability_customized BOOLEAN NOT NULL DEFAULT 0"
            )
        if "phone_country_code" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN phone_country_code VARCHAR(8)"
            )
        if "phone_number" not in employee_columns:
            cursor.execute(
                "ALTER TABLE employees ADD COLUMN phone_number VARCHAR(32)"
            )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_employees_phone_number ON employees(phone_number)"
        )
        conn.commit()
    finally:
        conn.close()

