import sqlite3
from typing import Optional, Tuple
from contextlib import contextmanager
import os
from pathlib import Path

# Chemin vers la base de données
DATABASE_PATH = Path("users.db").absolute()

def init_db():
    """Initialise la base de données et crée les tables si elles n'existent pas"""
    with get_db() as db:
        db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )
        ''')
        db.commit()

@contextmanager
def get_db():
    """Gestionnaire de contexte pour les connexions à la base de données"""
    db = sqlite3.connect(DATABASE_PATH)
    try:
        yield db
    finally:
        db.close()

def dict_factory(cursor, row):
    """Convertit les lignes de la base de données en dictionnaires"""
    fields = [column[0] for column in cursor.description]
    result = {}
    for key, value in zip(fields, row):
        # Convertir explicitement les booléens
        if key in ('is_active', 'is_admin'):
            # Assurer que la valeur est convertie en entier puis en booléen
            result[key] = bool(int(value)) if value is not None else False
        else:
            result[key] = value
    return result

def get_user_by_email(email: str) -> Optional[dict]:
    """Récupère un utilisateur par son email"""
    with get_db() as db:
        db.row_factory = dict_factory
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        return cursor.fetchone()

def get_user_by_username(username: str) -> Optional[dict]:
    """Récupère un utilisateur par son nom d'utilisateur"""
    with get_db() as db:
        db.row_factory = dict_factory
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cursor.fetchone()

def check_user_exists(email: str, username: str) -> Tuple[bool, str]:
    """Vérifie si un utilisateur avec l'email ou le nom d'utilisateur existe déjà"""
    print(f"Vérification de l'existence de l'utilisateur - Email: {email}, Username: {username}")  # Log
    with get_db() as db:
        cursor = db.cursor()
        query = 'SELECT email, username FROM users WHERE email = ? OR username = ?'
        params = (email, username)
        print(f"Exécution de la requête: {query} avec params: {params}")  # Log
        cursor.execute(query, params)
        result = cursor.fetchone()
        print(f"Résultat de la requête: {result}")  # Log
        if result:
            if result[0] == email:
                return True, "Email déjà enregistré"
            return True, "Nom d'utilisateur déjà pris"
        return False, ""

def create_user(user_data: dict) -> None:
    """Crée un nouvel utilisateur dans la base de données"""
    print(f"Création d'un nouvel utilisateur: {user_data['email']}")  # Log
    try:
        with get_db() as db:
            cursor = db.cursor()
            query = '''
            INSERT INTO users (id, username, email, hashed_password, is_active, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
            '''
            params = (
                user_data['id'],
                user_data['username'],
                user_data['email'],
                user_data['hashed_password'],
                user_data['is_active'],
                user_data.get('is_admin', False)
            )
            print(f"Exécution de la requête: {query} avec params: {params}")  # Log
            cursor.execute(query, params)
            db.commit()
            print("Utilisateur créé avec succès dans la base de données")  # Log
    except sqlite3.IntegrityError as e:
        print(f"Erreur d'intégrité SQLite: {str(e)}")  # Log
        raise Exception(f"Erreur d'intégrité de la base de données: {str(e)}")
    except Exception as e:
        print(f"Erreur inattendue: {str(e)}")  # Log
        raise

def update_user(user_id: str, update_data: dict) -> None:
    """Met à jour les informations d'un utilisateur"""
    allowed_fields = {'username', 'email', 'hashed_password', 'is_active', 'is_admin'}
    update_fields = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not update_fields:
        return
    
    query_parts = [f"{field} = ?" for field in update_fields.keys()]
    query = f"UPDATE users SET {', '.join(query_parts)} WHERE id = ?"
    
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute(query, (*update_fields.values(), user_id))
        db.commit()

def delete_user(user_id: str) -> None:
    """Supprime un utilisateur de la base de données"""
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        db.commit()

def promote_to_admin(email: str) -> bool:
    """Promouvoir un utilisateur au rang d'administrateur"""
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (email,))
        db.commit()
        return cursor.rowcount > 0

# Initialisation de la base de données au démarrage
if not os.path.exists(DATABASE_PATH):
    init_db()
