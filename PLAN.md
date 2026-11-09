## Solution plan

**Issue:** [#61 — Health check DB probe passes a raw SQL string, which fails under SQLAlchemy 2.x](https://github.com/codepath/pathreview-ai201-fa26-howard/issues/61)

### Understand

`GET /health` calls `health_check()` in `api/routes/health.py`. The PostgreSQL branch awaits `db.execute("SELECT 1")`. SQLAlchemy 2.x rejects a raw string passed to `AsyncSession.execute()` with an `ArgumentError` before sending the statement to PostgreSQL. The catch block then records the database as unhealthy, which is what the local endpoint reported even though a direct PostgreSQL query returned `1`.

The probe should run the constant query and mark PostgreSQL healthy when it succeeds. An actual database or query failure should still mark PostgreSQL unhealthy and contribute to an HTTP 503. I confirmed that `text("SELECT 1")` executes through the app's session and returns `1`. [SQLAlchemy text statements](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.text)

### Map

| File | Role |
| --- | --- |
| `api/routes/health.py` | Change the PostgreSQL statement inside `health_check()` to use `sqlalchemy.text()`. |
| `tests/unit/test_health.py` | Add focused route tests for successful execution and a database failure. |
| `core/database.py` | `get_db()` supplies the `AsyncSession` used by the route. Use it as the test dependency to override. |
| `pyproject.toml` | Review the existing mypy overrides for `api.routes.health`. Remove a suppression only if it is obsolete because of #61. |
| `tests/unit/test_review_service.py` | Reference for the repository's use of async session mocks. |

### Plan

1. Capture the baseline with the commands in `JOURNAL.md` and run `make test-unit` to record any existing failures before editing the route.
2. Add the focused tests in `tests/unit/test_health.py`. Mount the health router in a small test app and override `get_db()` with a test session. Make the session's async `execute()` reject a raw string and accept a `TextClause` containing `SELECT 1`. Stub the Redis client and supply a vector URL so the PostgreSQL assertion is isolated. Confirm that the success test fails against the current route.
3. Import `text` from SQLAlchemy and pass `text("SELECT 1")` to the existing `await db.execute(...)` call. Keep the existing exception handler and response shape.
4. Run the focused tests, then call `/health` against the local Compose stack. Verify `postgres: healthy` in the live response. Repeat the failure test with `execute()` raising a database error and confirm the 503 response has `detail.dependencies.postgres: unhealthy`.
5. Run `make test-unit`, `make lint`, `make typecheck`, and `.venv/bin/black --check api/routes/health.py tests/unit/test_health.py`. Check the route's mypy overrides against the resulting diagnostics before opening the Unit 9 PR.

### Inputs & outputs

The route receives a GET request with no request body and uses the session supplied by `get_db()`. The probe passes a SQLAlchemy `TextClause` for the constant `SELECT 1` to that session. A successful execution sets `dependencies.postgres` to `healthy`. An exception sets it to `unhealthy` in the HTTP 503 response body under `detail.dependencies`. The overall status still reflects the other dependency checks.

### Risks & unknowns

- A permissive `AsyncMock` would accept the raw string and let the regression test pass on the buggy code. Make the test double enforce the SQLAlchemy statement type and verify that the test fails before applying the change.
- The Redis check also fails locally because it reads a missing setting. Verify the PostgreSQL field independently of the overall HTTP status when running the live endpoint. [Redis issue #62](https://github.com/codepath/pathreview-ai201-fa26-howard/issues/62)
- The mypy override in `pyproject.toml` covers multiple diagnostics for `api.routes.health`. Check each relevant diagnostic before removing a suppression, since the Redis and response-dictionary code share that module.

### Edge cases

| Scenario | Expected result |
| --- | --- |
| PostgreSQL reachable and other checks pass | HTTP 200 with `dependencies.postgres: healthy`. |
| PostgreSQL unreachable or the query raises | HTTP 503 with `detail.dependencies.postgres: unhealthy`. |
| PostgreSQL reachable while Redis fails | HTTP 503 with `detail.dependencies.postgres: healthy` and `detail.dependencies.redis: unhealthy`. |
