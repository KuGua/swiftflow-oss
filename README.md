# SwiftFlow OSS

[中文说明](./README.zh-CN.md)

SwiftFlow OSS is a personal project that explores how software can make frontline service operations more structured, traceable, and scalable.

It started from a simple observation: in many offline retail and service environments, staffing information is still coordinated through fragmented chats, spreadsheets, and manual follow-up. That makes scheduling slower, harder to standardize, and more vulnerable to missing details or inconsistent records.

SwiftFlow OSS is my attempt to turn those operational gaps into a more systematic workflow. The project brings store configuration, employee readiness, availability management, staffing rules, and schedule execution into one product-oriented system.

## Why This Project

In many real-world service teams, scheduling is not only a calendar problem. It is also an information-organization problem.

Typical issues include:

- employee availability scattered across chat messages or temporary notes
- staffing requirements defined informally instead of as reusable rules
- store-level differences handled manually by managers
- schedule updates that are difficult to trace, review, or standardize
- operational knowledge living in people rather than in process

This project is built around the idea that better operational software should not just generate shifts. It should also make staffing data clearer, decisions more consistent, and workflows easier to maintain.

## What SwiftFlow OSS Does

SwiftFlow OSS is an open-source multi-store workforce scheduling system for retail and service operations. It combines operational setup and scheduling workflows in a single workspace.

The current scope includes:

- multi-store scheduling with weekly and daily editing views
- store-level business hours, staffing demand, and scheduling rule configuration
- employee profile management with skills, keyholder settings, and two-week availability
- role-based access control for admins, area managers, store managers, and staff
- anomaly detection, repair workflows, and batch schedule generation
- SQLite support for local development and PostgreSQL support for production deployment

## Product Value

From a product and operations perspective, SwiftFlow OSS is designed to improve three things:

- Information clarity: staffing rules, employee capability, and availability are structured instead of being spread across ad hoc communication
- Process consistency: different stores can follow a shared scheduling framework while still keeping store-level configuration
- Operational efficiency: managers can generate, inspect, and adjust schedules in one place instead of bouncing between tools

## Role Model

The current role design separates platform administration from day-to-day operational scheduling:

- `admin`: manages users, roles, and platform-level store data
- `area_manager`: manages scheduling operations across stores within assigned areas
- `store_manager`: manages scheduling and staffing configuration for assigned stores
- `staff`: views personal schedule and maintains self-service profile data

The `area_manager` role is especially important for operational scenarios where scheduling needs to be coordinated above the single-store level. It can be used to manage area-scoped employee data, staffing rules, and schedule generation workflows after an admin assigns the relevant areas.

## Key Workflows

The system focuses on the day-to-day workflows behind staffing operations:

- operations overview for admins, area managers, and store managers
- store directory, area assignment, business hours, staffing demand, and rule configuration
- employee roster management, skill matrix editing, store authorization, and relation constraints
- schedule generation, weekly calendar editing, daily slot inspection, and manual adjustment
- personal schedule and profile views for staff-facing self-service scenarios

## Tech Stack

- Frontend: Vue 3 + Vite
- Backend: FastAPI
- Data layer: SQLAlchemy
- Database: SQLite for local setup, PostgreSQL recommended for production

## Repository Structure

- `SwiftFlow-Frontend/`: frontend application
- `SwiftFlow-Backend/`: backend API, database models, and scheduling workflows
- `algorithms/`: scheduling algorithm references
- `docs/`: deployment notes and release materials

## Quick Start

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

The backend initialization script creates the schema and seeds a default `admin / admin` account for local setup.

It also seeds a default `area_manager / area_manager` account so the area-manager workflow can be tested immediately. After login, an admin can assign area scope to this account from user management.

## Production Notes

- local development defaults to SQLite
- PostgreSQL is the recommended production target
- see `SwiftFlow-Backend/docs/postgresql_deployment.md` for deployment guidance

## Open-Source Positioning

This repository is a sanitized open-source edition of the project:

- private or client-specific data has been removed
- sample naming has been generalized
- local-only runtime artifacts have been excluded
- the repository is presented as a reusable scheduling-system baseline

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
