from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, admin, projects, mirrors, gold_images, app_images, schedules, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.services.scheduler import scheduler_service
    await scheduler_service.start()
    yield
    # Shutdown
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
app.include_router(mirrors.router, prefix="/api/mirrors", tags=["mirrors"])
app.include_router(gold_images.router, prefix="/api/gold-images", tags=["gold-images"])
app.include_router(app_images.router, prefix="/api/app-images", tags=["app-images"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": settings.app_name}
