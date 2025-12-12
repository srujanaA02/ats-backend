# ATS Backend — README

> Job Application Tracking System (ATS)

## Project Summary

This repository contains a Django + DRF backend for an ATS. It implements:

* Role-based users (candidate, recruiter, hiring_manager)
* Company, Job, Application, and ApplicationHistory models
* A strict application stage state machine: `Applied -> Screening -> Interview -> Offer -> Hired` (plus `Rejected` from any stage)
* RBAC enforced at the API level
* JWT authentication (Simple JWT) and Session auth support for the browsable API
* Asynchronous email notifications using Celery + Redis
* Clean separation of concerns (views → services → tasks)

---

## Repository Structure

```
project/                  # Django project
  ├─ settings.py
  ├─ urls.py
  ├─ celery.py
  └─ wsgi.py

ats/                      # Application
  ├─ models.py             # User, Company, Job, Application, ApplicationHistory
  ├─ serializers.py
  ├─ views.py
  ├─ permissions.py
  ├─ services.py          # business / workflow logic
  ├─ workflow.py          # state machine (valid transitions)
  ├─ tasks.py             # celery tasks (email notifications)
  ├─ urls.py
  └─ tests.py

manage.py
requirements.txt
.env.example
postman_collection.json   # import into Postman
README.md
```

---

## Architecture Overview

**Layers**

* **API / Views** (`ats.views`) — HTTP layer, minimal business logic; delegates to services
* **Services** (`ats.services`) — single-source-of-truth for workflows and coordination (e.g. change stage transaction + history + enqueue notifications)
* **Tasks** (`ats.tasks`) — Celery tasks for side effects (sending emails)
* **Data** (`models.py`) — Django ORM models and constraints

**Background worker interaction**

1. API call triggers `services.change_stage()` or `services.create_application()`.
2. Service updates DB inside a transaction and creates `ApplicationHistory`.
3. Service calls a Celery task, e.g. `tasks.send_candidate_email.delay(...)`.
4. Celery worker (separate process) consumes task from Redis and sends email (console backend in dev or SMTP in prod).

This decouples user-facing requests from slow network I/O and keeps API latency low.

---

## State Machine Diagram

Valid transitions (ASCII):

```
Applied -> Screening -> Interview -> Offer -> Hired
   \                                  /
    `------------- Rejected ---------'

Meaning: from any of Applied/Screening/Interview/Offer you can go to Rejected.
No transitions out of Hired or Rejected.
```

You can find the canonical rules in `ats.models.Application.VALID_TRANSITIONS`.

---

## RBAC Matrix

|                                    Endpoint |   Candidate  |  Recruiter  |  Hiring Manager |
| ------------------------------------------: | :----------: | :---------: | :-------------: |
|                          `POST /api/token/` |       ✅      |      ✅      |        ✅        |
|                            `GET /api/jobs/` |       ✅      |      ✅      |        ✅        |
|                           `POST /api/jobs/` |       ❌      |      ✅      |        ❌        |
|                    `GET /api/applications/` |    ✅ (own)   | ✅ (company) |   ✅ (company)   |
|             `POST /api/applications/apply/` |       ✅      |      ❌      |        ❌        |
| `POST /api/applications/{id}/change-stage/` |       ❌      |      ✅      | ✅ (if assigned) |
|                       `GET /api/histories/` | ❌ (own only) |      ✅      |        ✅        |

Notes:

* Candidate endpoints are limited to their own data for privacy.
* Recruiters manage jobs for their company.
* Hiring managers can view company job applications (implementation configurable).

---

## ERD (Entity Relationship)

```
User (ats_user)
  - id, username, role, company_id (FK -> Company)

Company
  - id, name

Job
  - id, title, description, status, company_id (FK -> Company)

Application
  - id, candidate_id (FK -> User), job_id (FK -> Job), stage, created_at
  - unique(candidate_id, job_id)

ApplicationHistory
  - id, application_id (FK -> Application), from_stage, to_stage, changed_by (FK -> User), changed_at
```

---

## Environment & Setup (Development)

> The app uses environment variables (see `.env.example`).

1. Create & activate virtualenv

```bash
python -m venv .venv
source .venv/bin/activate   # mac/linux
.venv\Scripts\activate     # windows
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and update values:

```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

3. Run migrations & create fixtures / superuser:

```bash
python manage.py migrate
python manage.py createsuperuser
```

4. Start Redis (local) — required for Celery

* With Docker (recommended):

```bash
docker run -d --name redis-server -p 6379:6379 redis:latest
```

* Or install redis locally and start the service.

5. Start the Django dev server

```bash
python manage.py runserver
```

6. Start a Celery worker in another terminal

```bash
# Use solo pool on Windows if you encounter fork/permission errors
celery -A project worker -l info --pool=solo
```

7. Use Postman or curl (collection provided) to interact with the API.

---

## Run Tests

```bash
# run Django tests
python manage.py test

# or pytest if available
pytest
```

---

## API Quick Examples (curl)

* Obtain JWT access token

```bash
curl -X POST http://127.0.0.1:8000/api/token/ -H "Content-Type: application/json" -d '{"username":"recruiter1","password":"1234"}'
```

* List jobs (use returned access token)

```bash
curl -X GET http://127.0.0.1:8000/api/jobs/ -H "Authorization: Bearer <ACCESS_TOKEN>"
```

* Candidate apply

```bash
curl -X POST http://127.0.0.1:8000/api/applications/apply/ -H "Authorization: Bearer <CANDIDATE_TOKEN>" -H "Content-Type: application/json" -d '{"job": 1}'
```

* Recruiter change stage

```bash
curl -X POST http://127.0.0.1:8000/api/applications/1/change-stage/ -H "Authorization: Bearer <RECRUITER_TOKEN>" -H "Content-Type: application/json" -d '{"stage": "Screening"}'
```

---

## Postman Collection

A Postman collection file `postman_collection.json` is included in the repo. Import it into Postman and set the collection variables:

* `base_url` = `http://127.0.0.1:8000`
* `username`, `password` for login

I included requests for:

* `Auth: Login` (JWT)
* `Jobs: list/create/retrieve`
* `Applications: list/apply/change-stage/detail`
* `Histories: list`

---


## Security & Production Notes

* **Do not** store secrets in repository. Use environment variables or a secrets manager.
* For production: set `DEBUG=False`, use a proper SMTP provider, run workers in supervised processes (systemd / docker-compose / kubernetes), and secure the Redis instance.
* Use HTTPS, rotate keys, and apply database backups and monitoring.

---


