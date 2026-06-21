from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base

# Import all models so Alembic and SQLAlchemy discover them
from app.models import citizen, district, issue, participation, comment, evidence, notification, moderation  # noqa: F401

from app.routers import (
    auth,
    verification,
    issues,
    feed,
    participation as participationRouter,
    comments,
    profile,
    search,
    notifications,
    moderation as moderationRouter,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create all tables (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Pre-warm connection pool
    import asyncio
    from sqlalchemy import text
    import logging

    async def warmConnection():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        # Run 20 concurrent connections to warm up the pool
        await asyncio.gather(*(warmConnection() for _ in range(20)))
    except Exception as e:
        logger = logging.getLogger("uvicorn.error")
        logger.warning(f"Could not pre-warm database connection pool: {e}")

    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="Loka API",
    description="Verified Civic Participation Platform — Backend API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(verification.router)
app.include_router(issues.router)
app.include_router(feed.router)
app.include_router(participationRouter.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(notifications.router)
app.include_router(moderationRouter.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Loka API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def healthCheck():
    return {"status": "healthy"}


@app.post("/tests/run", tags=["Tests"])
async def runTests(concurrency: int = 100):
    import os
    import json
    import asyncio
    import subprocess

    cwd = os.getcwd()
    pythonBin = os.path.join(cwd, "venv", "Scripts", "python.exe")
    if not os.path.exists(pythonBin):
        pythonBin = "python"  # Fallback

    def executePytest():
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        env["TEST_CONCURRENCY"] = str(concurrency)
        
        # Run pytest synchronously inside the thread
        res = subprocess.run(
            [pythonBin, "-m", "pytest", "-v", "-s"],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd
        )
        return res.stdout, res.stderr

    try:
        # Offload the blocking process execution to a worker thread
        stdoutStr, stderrStr = await asyncio.to_thread(executePytest)
    except Exception as e:
        import traceback
        return {
            "error": f"Failed to run pytest in thread: {type(e).__name__} - {str(e)}",
            "stdout": "",
            "stderr": traceback.format_exc(),
            "passed": 0,
            "failed": 0,
            "error_count": 1,
            "total": 0,
            "duration": 0.0,
            "tests": []
        }


    
    resultsPath = os.path.join(cwd, "tests", "test_results.json")
    if os.path.exists(resultsPath):
        with open(resultsPath, "r") as f:
            data = json.load(f)
        return data
    else:
        return {
            "error": "Failed to generate test results JSON file",
            "stdout": stdoutStr,
            "stderr": stderrStr,
            "passed": 0,
            "failed": 0,
            "error_count": 1,
            "total": 0,
            "duration": 0.0,
            "tests": []
        }


@app.get("/tests/results", tags=["Tests"])
async def getTestResults(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    import os
    import json
    cwd = os.getcwd()
    resultsPath = os.path.join(cwd, "tests", "test_results.json")
    if os.path.exists(resultsPath):
        with open(resultsPath, "r") as f:
            data = json.load(f)
        return data
    else:
        return {"error": "No previous test results found", "tests": []}


@app.get("/tests/report", tags=["Tests"])
async def getReportCard(response: Response):
    from fastapi.responses import HTMLResponse
    from fastapi import HTTPException
    import os
    
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    cwd = os.getcwd()
    # Check parent dir or current dir
    reportPath = os.path.join(cwd, "..", "report_card.html")
    if not os.path.exists(reportPath):
        reportPath = os.path.join(cwd, "report_card.html")
        
    if os.path.exists(reportPath):
        with open(reportPath, "r", encoding="utf-8") as f:
            htmlContent = f.read()
        return HTMLResponse(content=htmlContent, status_code=200)
    else:
        raise HTTPException(status_code=404, detail="Report card HTML template not found")

