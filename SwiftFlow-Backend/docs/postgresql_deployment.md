# SwiftFlow PostgreSQL Deployment Notes

## Goal

Move the backend from local SQLite development mode to a production-ready PostgreSQL deployment, such as Huawei Cloud RDS for PostgreSQL.

## What changed

- `database.py` now treats PostgreSQL as a first-class target.
- `DATABASE_URL` is normalized automatically:
  - `postgres://...` -> `postgresql+psycopg://...`
  - `postgresql://...` -> `postgresql+psycopg://...`
- SQLAlchemy sessions now use:
  - `pool_pre_ping=True`
  - `pool_recycle=1800` for non-SQLite databases
  - `expire_on_commit=False`
- Enum columns use `native_enum=False` for more portable schema creation.
- Core schema creation and seed logic are split into:
  - `ensure_schema()`
  - `seed_core_data(db)`
  - `init_db_and_seed()`

## Dependencies

Install backend dependencies:

```bash
pip install -r requirements.txt
```

This now includes:

- `psycopg[binary]`
- `alembic`

## Environment variable

Create a `.env` file in `SwiftFlow-Backend` or set the environment variable directly:

```env
DATABASE_URL=postgresql+psycopg://swiftflow_user:YOUR_PASSWORD@YOUR_RDS_HOST:5432/swiftflow
```

Example template:

- `.env.example`

## Initialize schema and admin account

Run:

```bash
python scripts/init_database.py
```

This will:

- create tables if they do not exist
- seed core roles
- ensure a clean default `admin / admin` account exists
- remove any legacy placeholder area named `Default Area` if present

## Recommended production rollout

1. Create a PostgreSQL database on RDS.
2. Create an application user with full rights on the target database.
3. Set `DATABASE_URL`.
4. Run:

```bash
python scripts/init_database.py
```

5. Start the backend:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Notes

- SQLite compatibility is still kept for local development.
- Existing SQLite runtime patch helpers are only used when `DATABASE_URL` points to SQLite.
- For production, PostgreSQL is the recommended target.
