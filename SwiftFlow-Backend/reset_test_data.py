from database import (
    Area,
    SessionLocal,
    Employee,
    EmployeeAvailability,
    EmployeeStoreAccess,
    ScheduleEntry,
    Store,
    UserAreaAccess,
    UserStoreAccess,
    init_db_and_seed,
)
from seed_test_data import main as seed_main


def clear_business_data():
    db = SessionLocal()
    try:
        db.query(ScheduleEntry).delete(synchronize_session=False)
        db.query(UserAreaAccess).delete(synchronize_session=False)
        db.query(EmployeeAvailability).delete(synchronize_session=False)
        db.query(EmployeeStoreAccess).delete(synchronize_session=False)
        db.query(UserStoreAccess).delete(synchronize_session=False)
        db.query(Employee).delete(synchronize_session=False)
        db.query(Store).delete(synchronize_session=False)
        db.query(Area).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def main():
    init_db_and_seed()
    clear_business_data()
    seed_main()
    print("Reset and seed completed.")


if __name__ == "__main__":
    main()
