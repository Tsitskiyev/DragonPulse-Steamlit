from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings
from app.core.db import init_db

app = FastAPI(title=settings.app_name, version="0.2.2")

@app.on_event("startup")
def startup_event():
    init_db()

app.include_router(router, prefix="/api")
