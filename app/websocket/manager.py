from fastapi import WebSocket
from typing import List
import logging
import asyncio

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._cleanup_task = None  # La tâche de nettoyage sera initialisée plus tard

    async def start_cleanup_task(self):
        """Démarre la tâche de nettoyage des connexions inactives."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
            logger.info("Cleanup task started.")

    async def connect(self, websocket: WebSocket):
        """Accepte une nouvelle connexion WebSocket et l'ajoute à la liste des connexions actives."""
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            logger.info(f"New WebSocket connection: {websocket}")
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {e}")

    def disconnect(self, websocket: WebSocket):
        """Supprime une connexion WebSocket de la liste des connexions actives."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected: {websocket}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Envoie un message à un client WebSocket spécifique."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Envoie un message à tous les clients WebSocket connectés."""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to WebSocket: {e}")
                disconnected.append(connection)
                
        # Nettoie les connexions déconnectées
        for connection in disconnected:
            self.disconnect(connection)

    async def _cleanup_inactive_connections(self):
        """Nettoie périodiquement les connexions inactives."""
        while True:
            await asyncio.sleep(60)  # Nettoyage toutes les 60 secondes
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json({"type": "ping"})  # Test de connexion
                except Exception:
                    disconnected.append(connection)
            for connection in disconnected:
                self.disconnect(connection)

    async def shutdown(self):
        """Ferme proprement toutes les connexions WebSocket."""
        if self._cleanup_task:
            self._cleanup_task.cancel()  # Annule la tâche de nettoyage
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled.")
        
        for connection in self.active_connections:
            await connection.close()
        self.active_connections.clear()
        logger.info("All WebSocket connections closed.")

# Instance globale du gestionnaire de connexions
manager = ConnectionManager()