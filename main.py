from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from app.routes.auth import router as auth_router
from app.auth.auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.routes.admin import router as admin_router
from app.websocket.manager import manager
from app.database.database import init_db
import json
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
from app.services.diagram_service import (execute_process_from_diagram, 
                                        generate_diagram_from_description,
                                        ask_process_from_diagram,
                                        enhance_diagram_from_description,
                                        crewai_summarize)
import aiofiles
from datetime import timedelta
from app.utils.crewai_functions import choose_llm, llm_configs

from config import settings
import asyncio

# Configuration des logs
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAGENTA = "\033[95m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
END = "\033[0m"

# Initialisation de l'application avec configuration des slashes
app = FastAPI(
    title="Box8 API",
    description="API Backend pour Box8",
    version="1.0.0",
    redirect_slashes=True
)

# Chargement des variables d'environnement
load_dotenv()

# Configuration CORS avec support des cookies
""" origins = [
    os.getenv("FRONTEND_URL", "http://localhost:3000"),  # Frontend React (URL principale)
    os.getenv("FRONTEND_URL_ALTERNATIVE", "http://127.0.0.1:3000"),  # URL alternative
    "https://box7-react-68938d4bd5ee.herokuapp.com",  # Production React frontend
] """
origins = settings.allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=["*"],  # Ou au minimum: ["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"]
    expose_headers=["*"],
    max_age=3600,
)

# Add CORS headers to all responses
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# Initialisation de la base de données
init_db()

# WebSocket connection manager
@app.websocket("/ws/diagram")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)  # Accepte la connexion
    try:
        while True:
            try:
                # Reçoit des messages du client
                data = await websocket.receive_text()
                logger.info(f"Message reçu : {data}")

                # Envoie une réponse au client
                await websocket.send_text("pong")

                # Exemple de diffusion d'un message à tous les clients
                await manager.broadcast({"type": "notification", "content": f"New message: {data}"})
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        manager.disconnect(websocket)  # Nettoie la connexio

@app.middleware("http")
async def extend_session_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Récupérer le cookie de session
    session = request.cookies.get("session")
    if session:
        # Créer un nouveau token avec une durée prolongée
        try:
            # Vérifier si l'utilisateur est valide
            user = await get_current_user(session)
            if user:
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    data={"sub": user["email"]},
                    expires_delta=access_token_expires
                )
                
                is_production = settings.environment == "production"
                secure_cookie = is_production  # True en production

                response.set_cookie(
                    key="session",
                    value=access_token,
                    httponly=True,
                    secure=secure_cookie,  # True en production
                    samesite="lax",
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
                )
        except HTTPException:
            # Si le token est invalide, on ne fait rien
            pass
    
    return response

# Inclusion des routes
app.include_router(auth_router, prefix="/auth", tags=["auth"])  # Routes d'authentification
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])  # Routes d'administration

# Modèle pour les données de diagramme
class DiagramData(BaseModel):
    name: str
    diagram: str

class DiagramDescription(BaseModel):
    name: str
    description: str

class DiagramSave(BaseModel):
    name: str
    diagram: str

class LLMSelection(BaseModel):
    llm: str

def get_absolute_path(relative_path: str) -> str:
    """Fonction utilitaire pour obtenir le chemin absolu d'un fichier"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)

def get_user_folder(user_email: str) -> str:
    """Obtient le chemin du dossier de l'utilisateur"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_folder = os.path.join(base_dir, 'sharepoint', user_email)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder

# Routes pour la gestion des diagrammes
@app.get("/designer/list-json-files")
async def designer_list_json_files():
    """Liste tous les fichiers JSON dans le dossier designer"""
    try:
        designer_path = get_absolute_path('sharepoint/designer')
        if not os.path.exists(designer_path):
            os.makedirs(designer_path)
        
        files = [f for f in os.listdir(designer_path) if f.endswith('.json')]
        return JSONResponse(files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/designer/get-diagram/{filename}")
async def designer_get_diagram(filename: str):
    """Récupère le contenu d'un diagramme spécifique"""
    try:
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = get_absolute_path(f'sharepoint/designer/{filename}')
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            content = json.loads(await file.read())
        return JSONResponse(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/designer/save-diagram")
async def save_diagram(request: Request, data: DiagramSave):
    """Sauvegarde un diagramme au format JSON"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    try:
        if not data.name.endswith('.json'):
            data.name += '.json'
        
        file_path = get_absolute_path(f'sharepoint/designer/{data.name}')
        
        # Vérifier si le dossier existe, sinon le créer
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
            await file.write(data.diagram)
        
        return {"status": "success", "message": f"Diagramme {data.name} sauvegardé avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/designer/delete-diagram/{filename}")
async def designer_delete_diagram(filename: str):
    """Supprime un diagramme existant"""
    try:
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = get_absolute_path(f'sharepoint/designer/{filename}')
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        os.remove(file_path)
        return JSONResponse({"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/designer/launch-crewai")
async def designer_launch_crewai(request: Request):
    """Lance le processus CrewAI à partir d'un diagramme"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")

    try:
        data = await request.json()
        user_folder = get_user_folder(user["email"])
        llm = request.cookies.get("selected_llm", 'openai')
        chat_input = data.get('chatInput', '')
        
        print(f"Chat input reçu: {chat_input}")  # Afficher la valeur du chat
        
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
            
        result = await execute_process_from_diagram(data, folder=user_folder, llm=llm)
        if not chat_input=='': 
            chat = await ask_process_from_diagram(chat_input, result["message"], llm)
            print(f"Chat renvoyé: {chat}")
            result["message"] += chat

        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/designer/generate-diagram")
async def generate_diagram(request: Request, data: DiagramDescription):
    """Génère un diagramme à partir d'une description textuelle"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    try:
        llm = request.cookies.get("selected_llm", 'openai')
        diagram_data = await generate_diagram_from_description(data.description, data.name, llm=llm)
        return JSONResponse(content=diagram_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du diagramme: {str(e)}")


@app.post("/designer/enhance-diagram")
async def enhance_diagram(request: Request):
    """Génère un diagramme à partir d'une description textuelle"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    try:
        data = await request.json()
        llm = request.cookies.get("selected_llm", 'openai')
        chat_input = data.get('chatInput', '')

        diagram_data = await enhance_diagram_from_description(data, chat_input, llm)
        return JSONResponse(content=diagram_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du diagramme: {str(e)}")

@app.get("/designer/get_user_files/")
async def get_user_files(request: Request):
    """Liste les fichiers de l'utilisateur"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    user_folder = get_user_folder(user["email"])
    try:
        files = []
        for f in os.listdir(user_folder):
            if f.endswith(('.pdf', '.docx')):
                file_path = os.path.join(user_folder, f)
                files.append({
                    'name': f,
                    'size': os.path.getsize(file_path),
                    'modified': os.path.getmtime(file_path)
                })
        return JSONResponse(files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/designer/upload_user_file/")
async def upload_user_file(request: Request, file: UploadFile = File(...)):
    """Upload un fichier dans le dossier de l'utilisateur"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF et DOCX sont acceptés")
    
    user_folder = get_user_folder(user["email"])
    try:
        file_path = os.path.join(user_folder, file.filename)
        
        # Lecture du contenu du fichier uploadé
        content = await file.read()
        
        # Écriture asynchrone du fichier
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return {"message": f"Fichier {file.filename} uploadé avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/designer/delete_user_file/{filename}")
async def delete_user_file(request: Request, filename: str):
    """Supprime un fichier de l'utilisateur"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    user_folder = get_user_folder(user["email"])
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    try: 
        os.remove(file_path)
        txt_file_path = file_path + ".txt"
        if os.path.exists(txt_file_path):
            os.remove(txt_file_path)
            print(f"TXT file removed: {txt_file_path}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/designer/get_user_file/{filename}")
async def get_user_file(request: Request, filename: str):
    """Récupère un fichier spécifique de l'utilisateur"""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    user_folder = get_user_folder(user["email"])
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    # Détermine le type MIME en fonction de l'extension du fichier
    if filename.lower().endswith('.pdf'):
        media_type = 'application/pdf'
    elif filename.lower().endswith('.docx'):
        media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        raise HTTPException(status_code=400, detail="Type de fichier non supporté")
    
    return FileResponse(file_path, media_type=media_type, filename=filename)

@app.post("/designer/set-llm")
async def set_llm(request: Request, llm_data: LLMSelection):
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    user = await get_current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    print(f"LLM sélectionné: {llm_data.llm}")
    response = JSONResponse(content={"message": "LLM sélectionné avec succès"})
    response.set_cookie(key="selected_llm", value=llm_data.llm)
    return response

@app.get("/designer/get-llms")
async def designer_get_llms(request: Request):
    """Récupère la liste des configurations LLM disponibles"""
    # Récupérer le LLM sélectionné depuis les cookies
    current_llm = request.cookies.get("selected_llm", "openai")
    
    # Préparer la configuration pour le frontend
    frontend_configs = {
        key: {
            "model": config["model"],
            "label": config["model"]
        }
        for key, config in llm_configs.items()
    }
    
    # Ajouter la valeur actuelle à la réponse
    response_data = {
        "configs": frontend_configs,
        "current": current_llm
    }
    
    return JSONResponse(content=response_data)



@app.get("/designer/summarize_file/{filename}")
async def summarize_file(request: Request, filename: str):
    """Résume le contenu d'un fichier utilisateur en utilisant CrewAI"""
    # print(f"\n{MAGENTA}[SUMMARY] Starting summary for file: {filename}{END}")
    
    session = request.cookies.get("session")
    if not session:
        # print(f"{RED}[SUMMARY] No session cookie found{END}")
        raise HTTPException(status_code=401, detail="Non authentifié")
        
    user = await get_current_user(session)
    if not user:
        # print(f"{RED}[SUMMARY] Authentication failed{END}")
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    # print(f"{GREEN}[SUMMARY] User authenticated: {user['email']}{END}")
    user_folder = get_user_folder(user["email"])
    file_path = os.path.join(user_folder, filename)
    # print(f"{GREEN}[SUMMARY] File path: {file_path}{END}")
    
    if not os.path.exists(file_path):
        # print(f"{RED}[SUMMARY] File not found: {file_path}{END}")
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    try:
        # print(f"{YELLOW}[SUMMARY] Starting CrewAI summarization with LLM: {request.cookies.get('selected_llm', 'openai')}{END}")
        summary = await crewai_summarize(file_path, pages=-1, llm=request.cookies.get("selected_llm", 'openai'))
        # print(f"{GREEN}[SUMMARY] Summary generated successfully{END}")
        return {"summary": summary}
    except Exception as e:
       #  print(f"{RED}[SUMMARY] Error during summarization: {str(e)}{END}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/designer/get_summary_file/{filename}")
async def get_summary_file(request: Request, filename: str):
    """Récupère le contenu du fichier de résumé associé à un fichier"""
    # print(f"\n{MAGENTA}[GET SUMMARY] Getting summary for file: {filename}{END}")
    
    session = request.cookies.get("session")
    if not session:
        # print(f"{RED}[GET SUMMARY] No session cookie found{END}")
        raise HTTPException(status_code=401, detail="Non authentifié")
        
    user = await get_current_user(session)
    if not user:
        # print(f"{RED}[GET SUMMARY] Authentication failed{END}")
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    # print(f"{GREEN}[GET SUMMARY] User authenticated: {user['email']}{END}")
    user_folder = get_user_folder(user["email"])
    file_path = os.path.join(user_folder, filename)
    summary_path = f"{file_path}.txt"
    
    # print(f"{GREEN}[GET SUMMARY] Summary path: {summary_path}{END}")
    
    if not os.path.exists(summary_path):
       #  print(f"{RED}[GET SUMMARY] Summary file not found: {summary_path}{END}")
        return {"has_summary": False, "summary": None}
    
    try:
        async with aiofiles.open(summary_path, 'r', encoding='utf-8') as file:
            content = await file.read()
           #  print(f"{GREEN}[GET SUMMARY] Summary file read successfully{END}")
            return {"has_summary": True, "summary": content}
    except Exception as e:
        # print(f"{RED}[GET SUMMARY] Error reading summary file: {str(e)}{END}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Route de test
@app.get("/")
async def root():
    return {"message": "Box8 API is running"}

# Point d'entrée pour lancer l'application
if __name__ == "__main__":
    import uvicorn

    # Démarre la tâche de nettoyage des connexions inactives
    async def start_cleanup_task():
        await manager.start_cleanup_task()

    # Démarre la boucle d'événements et la tâche de nettoyage
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_cleanup_task())

    # Démarre l'application FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
