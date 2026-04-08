# SwiftFlow OSS

SwiftFlow OSS is a generalized multi-store workforce scheduling system built with:

- Vue 3 + Vite frontend
- FastAPI backend
- SQLAlchemy data layer

This repository is a sanitized open-source variant intended for:

- multi-store staff management
- scheduling and weekly calendar editing
- store rule and staffing-demand configuration
- role-based access control

## Project structure

- `SwiftFlow-Frontend/` - frontend application
- `SwiftFlow-Backend/` - backend API and scheduling logic
- `algorithms/` - algorithm notes / references
- `docs/` - deployment and design notes

## Current status

This repository has been cleaned for open-source use:

- local test databases removed
- private evaluation scripts removed
- customer-specific sample names replaced with generic examples
- store archetype naming generalized

## Local development

### Frontend

```bash
cd SwiftFlow-Frontend
npm install
npm run dev
```

### Backend

```bash
cd SwiftFlow-Backend
pip install -r requirements.txt
python scripts/init_database.py
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## Database

The backend supports:

- SQLite for local development
- PostgreSQL for production deployment

See:

- `SwiftFlow-Backend/docs/postgresql_deployment.md`

## Notes

This open-source edition is intended to be a reusable baseline, not a copy of any client-specific deployment.
