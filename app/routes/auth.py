from fastapi import APIRouter, Response, Cookie
from typing import Optional
from app.auth.auth import (
    login_user,
    register_user,
    logout_user,
    check_auth_status,
    get_current_user_info
)
from app.models.user import UserLogin, UserRegistration
import logging

# Configuration du router
router = APIRouter()

@router.post("/login")
async def login(response: Response, user_data: UserLogin):
    """Endpoint de login qui retourne un token JWT et crée une session"""
    try:
        # login_user gère déjà la création du token et du cookie
        result = await login_user(response, user_data)
        return result
    except HTTPException as e:
        # Propager les exceptions HTTP
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in login route: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur est survenue lors de la connexion"
        )

@router.post("/register")
async def register(user_data: UserRegistration):
    """Endpoint d'enregistrement d'un nouvel utilisateur"""
    return await register_user(user_data)

@router.post("/logout")
async def logout(response: Response, session: Optional[str] = Cookie(None)):
    """Endpoint de déconnexion qui supprime la session"""
    return await logout_user(response, session)

@router.get("/check-auth")
async def check_auth(session: Optional[str] = Cookie(None)):
    """Vérifie si l'utilisateur est authentifié via le cookie de session"""
    return await check_auth_status(session)

@router.get("/me")
async def read_users_me(session: Optional[str] = Cookie(None)):
    """Récupère les informations de l'utilisateur connecté"""
    return await get_current_user_info(session)
