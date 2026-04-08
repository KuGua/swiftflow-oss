from database import init_db_and_seed


def main():
    init_db_and_seed()
    print("Migration v1 completed: staffing rule schema is ready.")


if __name__ == "__main__":
    main()
