from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    app_images,
    audit,
    auth,
    components,
    docker_images,
    gold_images,
    helm_charts,
    integrations,
    mirroring,
    pipelines,
    projects,
    schedules,
    webhooks,
)
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import AsyncSessionLocal
    from app.services.scheduler import scheduler_service
    from app.services.sync_scheduler import SyncScheduler

    await scheduler_service.start()

    sync_scheduler = SyncScheduler(AsyncSessionLocal)
    await sync_scheduler.start()
    app.state.sync_scheduler = sync_scheduler

    yield

    # Shutdown
    await sync_scheduler.stop()
    await scheduler_service.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="DevOps Sync & Build Service API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(gold_images.router, prefix="/api/gold-images", tags=["gold-images"])
app.include_router(app_images.router, prefix="/api/app-images", tags=["app-images"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(helm_charts.router, prefix="/api/helm-charts", tags=["helm-charts"])
app.include_router(docker_images.router, prefix="/api/docker-images", tags=["docker-images"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(components.router, prefix="/api/components", tags=["components"])
app.include_router(audit.router, prefix="/api/admin/audit-logs", tags=["audit"])
app.include_router(mirroring.router, prefix="/api/mirroring", tags=["mirroring"])


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": settings.app_name}
