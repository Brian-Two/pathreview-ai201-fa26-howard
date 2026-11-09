## Unit 7 — Issue selection

**Issue link:** [CodePath PathReview #61](https://github.com/codepath/pathreview-ai201-fa26-howard/issues/61)

**Issue title:** Health check DB probe passes a raw SQL string, which fails under SQLAlchemy 2.x

**Tier:** Tier 1

**Problem summary:**
The PostgreSQL check in `api/routes/health.py` sends a plain `SELECT 1` string to an async SQLAlchemy session. SQLAlchemy 2.x rejects the string before the query reaches PostgreSQL. The error handler then reports PostgreSQL as unhealthy even when it is reachable. A successful fix would pass the query as a SQLAlchemy text statement so the PostgreSQL status reflects whether the probe actually succeeded.

**Selection notes:**
- **Scope and tier fit.** The change is centered on `health_check()` and a focused regression test. The PostgreSQL result can be checked independently from the Redis and vector database checks.
- **Code and tests.** The route gets its async session from `core/database.py`. The repository has no dedicated health-route test. The async tests in `tests/unit/test_review_service.py` show the session fixture pattern, and a regression test can check how the route handles a successful probe and a failed one.
- **Time and dependencies.** Budget 2–4 hours to reproduce the bug, make the change, and verify it. The PostgreSQL probe can be fixed independently of the Redis issue (#62). At selection time, #61 had no GitHub comments and zero claims in the cohort ledger.

**Branch name:** `fix/61-health-check-db-probe`

**Setup confirmation:** The app runs at http://localhost:5173. The frontend login route loaded and the API authenticated a seeded user. Local setup uses Python 3.11, Node 20, and a Compose override for Chroma's NumPy dependency and heartbeat check.

**Baseline observation:** PostgreSQL responds to `SELECT 1` directly, but `GET /health` returns HTTP 503 and reports PostgreSQL as unhealthy. The API log shows that SQLAlchemy rejected the raw SQL string.

**Cohort ledger:** Pending claim and ledger entry.
