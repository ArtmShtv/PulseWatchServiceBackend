# PulseWatch

Uptime monitoring backend — periodically checks HTTP endpoints, tracks status
history, and raises incidents on downtime with email notification.

## Stack
- FastAPI
- PostgreSQL + SQLAlchemy
- Celery + Redis (scheduled endpoint checks)
- Alembic (migrations)
- pytest

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
For testing was used pytest 
1. Add `.env.tests` file with structure like in example:
```
TESTS_POSTGRES_HOST=localhost
TESTS_POSTGRES_USER=tests
TESTS_POSTGRES_PASSWORD=tests_postgres
TESTS_POSTGRES_PORT=5433
TESTS_POSTGRES_NAME=postgres_for_tests
```
2. Start a tests DB with:
```
docker compose --env-file .env.test up -d db_test
```
3. Start tests with
```
python -m pytest -v
```