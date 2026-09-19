from fastapi import APIRouter

from app.api.v1 import auth, health, task_lists, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(task_lists.router)
