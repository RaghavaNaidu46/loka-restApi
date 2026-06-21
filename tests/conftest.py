import sys
import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine

# Import database module first to modify its engine
import app.core.database
from app.core.config import settings

# Override the engine in app.core.database to use NullPool for tests
app.core.database.engine = create_async_engine(
    settings.databaseUrl,
    echo=settings.debug,
    poolclass=NullPool,
)

# Also override AsyncSessionFactory to use the new engine
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.core.database import OptimizingAsyncSession
app.core.database.AsyncSessionFactory = async_sessionmaker(
    app.core.database.engine,
    class_=OptimizingAsyncSession,
    expire_on_commit=False,
)

# Now import the remaining elements
from httpx import AsyncClient, ASGITransport
from app.main import app as lokaApp
from app.core.database import engine, getDb
from app.core.security import createAccessToken
from app.models.citizen import Citizen, VerificationStatus



@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def dbSession() -> AsyncGenerator[AsyncSession, None]:
    # Establish a connection and start a nested transaction
    connection = await engine.connect()
    transaction = await connection.begin()
    
    # Bind session to the connection so everything is part of the transaction
    session = OptimizingAsyncSession(bind=connection, expire_on_commit=False)

    # Override getDb dependency to yield this transactional session
    async def overrideGetDb() -> AsyncGenerator[AsyncSession, None]:
        yield session

    lokaApp.dependency_overrides[getDb] = overrideGetDb

    yield session

    # Roll back transaction at the end of the test to keep database clean
    await session.close()
    await transaction.rollback()
    await connection.close()
    lokaApp.dependency_overrides.clear()


@pytest_asyncio.fixture
async def httpClient(dbSession: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Transport points directly to FastAPI app via ASGITransport
    transport = ASGITransport(app=lokaApp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def verifiedCitizen(dbSession: AsyncSession) -> Citizen:
    # Seed a verified citizen in the transactional session
    citizen = Citizen(
        email="test_verified_citizen@loka.test",
        displayName="Verified Citizen",
        verificationStatus=VerificationStatus.verified,
        role="citizen"
    )
    dbSession.add(citizen)
    await dbSession.flush()
    await dbSession.refresh(citizen)
    return citizen


@pytest_asyncio.fixture
async def verifiedClient(
    httpClient: AsyncClient,
    verifiedCitizen: Citizen
) -> AsyncClient:
    # Generate token for the verified citizen
    token = createAccessToken(str(verifiedCitizen.id), role=verifiedCitizen.role)
    httpClient.headers["Authorization"] = f"Bearer {token}"
    return httpClient


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    import json
    import os
    
    results = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "total": 0,
        "duration": terminalreporter._sessiontime if hasattr(terminalreporter, "_sessiontime") else 0.0,
        "tests": []
    }
    
    def process_reports(reports):
        for rep in reports:
            if rep.when == "call" or (rep.when == "setup" and rep.failed):
                status = rep.outcome
                duration = getattr(rep, "duration", 0.0)
                
                # Extract logs from sections
                logs = ""
                for section in rep.sections:
                    if any(x in section[0] for x in ("stdout", "stderr", "log")):
                        logs += section[1] + "\n"
                
                if rep.longrepr:
                    logs += str(rep.longrepr) + "\n"

                # Standardize names using camelCase where appropriate
                testName = rep.head_line or rep.nodeid.split("::")[-1]
                
                results["tests"].append({
                    "name": testName,
                    "status": status,
                    "duration": duration,
                    "logs": logs.strip()
                })
                
                if status == "passed":
                    results["passed"] += 1
                elif status == "failed":
                    results["failed"] += 1
                else:
                    results["error"] += 1
                results["total"] += 1

    for outcome in ["passed", "failed", "error", "skipped"]:
        if outcome in terminalreporter.stats:
            process_reports(terminalreporter.stats[outcome])
            
    # Merge concurrency metrics if they exist
    metricsPath = os.path.join(os.path.dirname(__file__), "concurrency_metrics.json")
    if os.path.exists(metricsPath):
        try:
            with open(metricsPath, "r") as f:
                results["concurrency"] = json.load(f)
        except Exception:
            pass

    # Write to tests/test_results.json
    resultsPath = os.path.join(os.path.dirname(__file__), "test_results.json")
    with open(resultsPath, "w") as f:
        json.dump(results, f, indent=2)

