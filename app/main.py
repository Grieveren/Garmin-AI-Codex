"""FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.routers import health, manual_sync, recommendations


app = FastAPI(title="Training Optimizer API")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse, tags=["dashboard"])
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard showing AI training recommendations."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Simple health probe for liveness checks."""
    return {"status": "ok"}


# Include routers
app.include_router(health.router)
app.include_router(manual_sync.router)
app.include_router(recommendations.router)
