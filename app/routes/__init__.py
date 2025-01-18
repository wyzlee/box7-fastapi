# Routes package initialization
from .admin import router as admin_router
from .auth import router as auth_router

admin = admin_router
auth = auth_router
