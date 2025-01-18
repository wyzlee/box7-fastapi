from fastapi import APIRouter, Depends, HTTPException
from ..auth.auth import get_current_user
from ..database.database import get_db, dict_factory, promote_to_admin
from ..models.user import User
from typing import List

router = APIRouter()

async def check_admin(current_user: dict = Depends(get_current_user)):
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Accès administrateur requis")
    return current_user

@router.get("/users")
async def list_users(current_user: dict = Depends(check_admin)):
    """Liste tous les utilisateurs (admin uniquement)"""
    with get_db() as db:
        db.row_factory = dict_factory
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()

@router.put("/users/{user_id}/toggle-admin")
async def toggle_admin(user_id: str, current_user: dict = Depends(check_admin)):
    """Active/désactive le statut admin d'un utilisateur"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Impossible de modifier son propre statut admin")
    
    with get_db() as db:
        cursor = db.cursor()
        # Récupérer le statut actuel
        cursor.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Inverser le statut
        new_status = not user[0]
        cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_status, user_id))
        db.commit()
        return {"status": "success", "is_admin": new_status}

@router.put("/users/{user_id}/toggle-active")
async def toggle_active(user_id: str, current_user: dict = Depends(check_admin)):
    """Active/désactive un utilisateur"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Impossible de désactiver son propre compte")
    
    with get_db() as db:
        cursor = db.cursor()
        # Récupérer le statut actuel
        cursor.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Inverser le statut
        new_status = not user[0]
        cursor.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
        db.commit()
        return {"status": "success", "is_active": new_status}

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(check_admin)):
    """Supprime un utilisateur"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        db.commit()
        return {"status": "success"}

# Endpoint temporaire pour promouvoir un utilisateur en administrateur
@router.post("/promote/{email}")
async def promote_user_to_admin(email: str):
    """Endpoint temporaire pour promouvoir un utilisateur en administrateur"""
    if promote_to_admin(email):
        return {"status": "success", "message": f"Utilisateur {email} promu administrateur"}
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
