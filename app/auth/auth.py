from datetime import datetime, timedelta, timezone
from typing import Optional, Set
from fastapi import HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from uuid import uuid4
from passlib.context import CryptContext
from os import getenv

from app.models.user import User, UserLogin, UserRegistration
from app.database.database import get_user_by_email, create_user, check_user_exists

# Configuration de la sécurité
SECRET_KEY = getenv("SECRET_KEY", "votre_clé_secrète_ici")  # Must be set in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Configuration du hachage de mot de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Set pour stocker les tokens invalidés
invalidated_tokens: Set[str] = set()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si le mot de passe correspond au hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Génère un hash pour le mot de passe"""
    return pwd_context.hash(password)

def get_user(email: str) -> Optional[dict]:
    """Récupère un utilisateur par son email"""
    return get_user_by_email(email)

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authentifie un utilisateur"""
    user = get_user(email)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def invalidate_token(token: str) -> None:
    """Ajoute un token à la blacklist"""
    invalidated_tokens.add(token)

def is_token_valid(token: str) -> bool:
    """Vérifie si un token est valide (non blacklisté)"""
    return token not in invalidated_tokens

async def get_current_user(session: Optional[str] = Cookie(None)) -> Optional[dict]:
    """Récupère l'utilisateur actuellement connecté à partir du cookie de session"""
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié"
        )

    # Vérifier si le token est dans la blacklist
    if not is_token_valid(session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide"
        )

    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
        user = get_user(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé"
            )
        
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte désactivé"
            )

        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide"
        )

async def login_user(response: Response, user_data: UserLogin):
    """Logique de connexion d'un utilisateur"""
    user = authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

    print(f"user['is_active']: {user['is_active']}")
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=access_token_expires
    )

    # Configuration du cookie de session
    response.set_cookie(
        key="session",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="strict",
        secure=True,
        domain=None,
        path="/"
    )

    return {
        "authenticated": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "is_active": user["is_active"],
            "is_admin": user["is_admin"]
        }
    }

async def register_user(user_data: UserRegistration):
    """Logique d'enregistrement d'un nouvel utilisateur"""
    print(f"Tentative d'inscription - Email: {user_data.email}, Username: {user_data.username}")
    
    exists, error_message = check_user_exists(user_data.email, user_data.username)
    print(f"Résultat de la vérification - Existe: {exists}, Message: {error_message}")
    
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )

    hashed_password = get_password_hash(user_data.password)
    new_user = {
        "id": str(uuid4()),
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": hashed_password,
        "is_active": False,  # Les nouveaux utilisateurs sont inactifs par défaut
        "is_admin": False
    }

    try:
        print("Tentative de création de l'utilisateur dans la base de données")
        create_user(new_user)
        print("Utilisateur créé avec succès")
        return {
            "id": new_user["id"],
            "email": new_user["email"],
            "username": new_user["username"],
            "is_active": new_user["is_active"],
            "is_admin": new_user["is_admin"]
        }
    except Exception as e:
        print(f"Erreur lors de la création de l'utilisateur: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de l'utilisateur"
        )

async def logout_user(response: Response, session: Optional[str] = Cookie(None)):
    """Logique de déconnexion d'un utilisateur"""
    if session:
        invalidate_token(session)
    
    response.delete_cookie(
        key="session",
        httponly=True,
        samesite="lax",
        secure=False  # Mettre à True en production avec HTTPS
    )
    
    return {"message": "Déconnecté avec succès"}

async def check_auth_status(session: Optional[str] = Cookie(None)):
    """Vérifie le statut d'authentification d'un utilisateur"""
    if not session:
        return {"authenticated": False}

    try:
        user = await get_current_user(session)
        if not user:
            return {"authenticated": False}

        return {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "is_active": user["is_active"],
                "is_admin": user["is_admin"]
            }
        }
    except HTTPException:
        return {"authenticated": False}

async def get_current_user_info(session: Optional[str] = Cookie(None)):
    """Récupère les informations détaillées de l'utilisateur connecté"""
    user = await get_current_user(session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié"
        )

    return {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "is_active": user["is_active"],
        "is_admin": user["is_admin"]
    }
