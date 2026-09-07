# PulseWatch

Uptime monitoring backend — periodically checks HTTP endpoints, tracks status
history, and raises incidents on downtime.

## Stack
- FastAPI
- PostgreSQL + SQLAlchemy
- Celery + Redis (scheduled endpoint checks)
- Alembic (migrations)

## Setup

1. Copy `.env.example` to `.env` and fill in values
2. `docker-compose up --build`
3. Run migrations: `docker-compose exec celery alembic upgrade head`
   (or wherever you run alembic from)

## Project structure
- `app/api/` — routes
- `app/db/models/` — SQLAlchemy models
- `app/services/` — business logic
- `app/tasks/` — Celery tasks (endpoint checks, dispatching)
- `alembic/` — migrations

## Running tests
(add once you have a test suite)