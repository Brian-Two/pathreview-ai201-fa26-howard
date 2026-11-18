"""Regression tests for the health route's PostgreSQL probe (issue #61)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from api.routes.health import router
from core.database import get_db

pytestmark = pytest.mark.unit


@pytest.fixture
def health_client(monkeypatch):
    """Isolate the route from external services with a strict SQL statement double."""

    async def execute(statement):
        # A permissive AsyncMock would hide the SQLAlchemy 2.x regression.
        if not isinstance(statement, TextClause):
            raise ArgumentError("Textual SQL must be explicitly wrapped in text()")
        assert str(statement) == "SELECT 1"

    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = execute
    redis_client = Mock()
    monkeypatch.setattr(redis, "Redis", Mock(return_value=redis_client))
    # Redis configuration is a separate seeded bug (#62), outside this fix.
    monkeypatch.setattr(
        "core.config.settings",
        SimpleNamespace(redis_host="localhost", redis_port=6379, vector_db_url="http://vector"),
    )

    async def override_db():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, session, redis_client


def test_health_reports_healthy_postgres_with_sqlalchemy_text(health_client):
    """Return HTTP 200 when the text probe and other dependency checks succeed."""
    client, session, redis_client = health_client

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["dependencies"] == {
        "postgres": "healthy",
        "redis": "healthy",
        "vector_db": "healthy",
    }
    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    assert isinstance(statement, TextClause)
    assert str(statement) == "SELECT 1"
    redis_client.ping.assert_called_once()


def test_health_reports_unhealthy_postgres_when_query_fails(health_client):
    """Preserve HTTP 503 and the dependency result when database execution fails."""
    client, session, redis_client = health_client
    session.execute.side_effect = ConnectionError("PostgreSQL unavailable")

    response = client.get("/health")

    assert response.status_code == 503
    payload = response.json()["detail"]
    assert payload["status"] == "unhealthy"
    assert payload["dependencies"] == {
        "postgres": "unhealthy",
        "redis": "healthy",
        "vector_db": "healthy",
    }
    session.execute.assert_awaited_once()
    redis_client.ping.assert_called_once()


def test_health_keeps_postgres_healthy_when_redis_fails(health_client):
    """Report HTTP 503 for Redis without incorrectly marking PostgreSQL unhealthy."""
    client, session, redis_client = health_client
    redis_client.ping.side_effect = redis.exceptions.ConnectionError("Redis unavailable")

    response = client.get("/health")

    assert response.status_code == 503
    payload = response.json()["detail"]
    assert payload["status"] == "unhealthy"
    assert payload["dependencies"] == {
        "postgres": "healthy",
        "redis": "unhealthy",
        "vector_db": "healthy",
    }
    session.execute.assert_awaited_once()
    redis_client.ping.assert_called_once()
