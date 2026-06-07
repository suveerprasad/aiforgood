import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.v1 import patients, donors, matching, inventory, insights, webhooks, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodbridge")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BloodBridge AI starting up...")
    yield
    logger.info("BloodBridge AI shutting down.")


app = FastAPI(
    title="BloodBridge AI",
    description="Autonomous blood coordination and transfusion planning system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["patients"])
app.include_router(donors.router, prefix="/api/v1/donors", tags=["donors"])
app.include_router(matching.router, prefix="/api/v1/matching", tags=["matching"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "healthy",
        "service": "BloodBridge AI",
        "version": "1.0.0",
        "region": settings.AWS_REGION,
    }


@app.get("/", tags=["system"])
def root():
    return {"message": "BloodBridge AI — Autonomous Blood Coordination System"}
