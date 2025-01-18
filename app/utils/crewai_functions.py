import os
from crewai import LLM, Agent, Task, Crew
from crewai_tools import (PDFSearchTool,
                         DOCXSearchTool,
                         TXTSearchTool,
                         CSVSearchTool)
import chromadb
from chromadb.config import Settings
from typing import Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration globale des LLMs
llm_configs = {
    "hosted": {
        "model": "hosted_vllm/cognitivecomputations/dolphin-2.9-llama3-8b",
        "base_url": "https://1yq4yjjl8ydge2-8000.proxy.runpod.net/v1",
        "api_key": "token-abc123",
    },
    "local": {
        "model": "ollama/gemma2:2b",
        "base_url": "http://localhost:11434",
        "api_key": "not needed",
    },
    "openai": {
        "model": "gpt-4",
        "temperature": 0.2,
        "api_key": os.getenv("OPENAI_API_KEY")
    },
    "openai3.5": {
        "model": "gpt-3.5-turbo",
        "temperature": 0.2,
        "api_key": os.getenv("OPENAI_API_KEY")
    },
    "mistral": {
        "model": "mistral/mistral-medium-latest",
        "temperature": 0.2,
        "api_key": os.getenv("MISTRAL_API_KEY")
    },
    "mistral-large": {
        "model": "mistral/mistral-large-latest",
        "temperature": 0.2,
        "api_key": os.getenv("MISTRAL_API_KEY")
    },
    "groq": {
        "model": "groq/mixtral-8x7b-32768",
        "temperature": 0.2,
        "api_key": os.getenv("GROQ_API_KEY")
    },
    "groq-large": {
        "model": "groq/llama-3.1-70b-versatile",
        "temperature": 0.2,
        "api_key": os.getenv("GROQ_API_KEY")
    }
}

def check_llm_availability(config: dict) -> bool:
    """
    Check if an LLM is available and properly configured.
    
    Args:
        config (dict): LLM configuration
        
    Returns:
        bool: True if LLM is available, False otherwise
    """
    try:
        # Check for API key if needed
        if "api_key" in config and not config["api_key"]:
            return False
            
        # For local models, check if the service is running
        if config.get("base_url", "").startswith("http://localhost"):
            try:
                response = requests.get(config["base_url"])
                return response.status_code == 200
            except requests.RequestException:
                return False
                
        return True
    except Exception:
        return False

def get_available_llm() -> Optional[str]:
    """
    Get the first available LLM from the configuration.
    
    Returns:
        Optional[str]: Name of the first available LLM, or None if none are available
    """
    priority_order = ["local", "openai", "mistral", "groq"]
    
    for llm_name in priority_order:
        if llm_name in llm_configs and check_llm_availability(llm_configs[llm_name]):
            return llm_name
    return None

def choose_llm(name: str = "") -> LLM:
    """
    Sélectionne et configure un modèle de langage en fonction du nom fourni.
    
    Args:
        name (str): Nom du modèle à utiliser
        
    Returns:
        LLM: Instance du modèle de langage configuré
        
    Raises:
        RuntimeError: Si aucun LLM n'est disponible
    """
    if not name:
        name = get_available_llm()
        if not name:
            raise RuntimeError("No LLM available. Please check your configuration and API keys.")
    
    config = llm_configs.get(name)
    if not config:
        raise ValueError(f"Unknown LLM: {name}")
        
    if not check_llm_availability(config):
        available_llm = get_available_llm()
        if not available_llm:
            raise RuntimeError("No LLM available. Please check your configuration and API keys.")
        print(f"Warning: {name} is not available, falling back to {available_llm}")
        name = available_llm
        config = llm_configs[name]
    
    return LLM(**config)

def reset_chroma() -> bool:
    """
    Réinitialise la base de données ChromaDB.
    
    Returns:
        bool: True si la réinitialisation a réussi, False sinon
    """
    path = "db/"
    if os.path.isdir(path):
        client = chromadb.PersistentClient(path=path, settings=Settings(allow_reset=True))
        client.reset()
        state = True
    else:
        state = False
    print(f"Chromadb reset : {state}")
    return state

def choose_tool(src: str):
    """
    Sélectionne et instancie l'outil approprié en fonction de l'extension du fichier.
    
    Args:
        src (str): Chemin vers le fichier source
        
    Returns:
        Tool: Instance de l'outil approprié pour le type de fichier
        
    Raises:
        ValueError: Si le fichier n'existe pas ou si l'extension n'est pas supportée
        FileNotFoundError: Si le chemin du fichier n'existe pas
    """
    # Vérifier si le fichier existe
    if not os.path.exists(src):
        raise FileNotFoundError(f"Le fichier n'existe pas : {src}")
    
    # Obtenir l'extension en minuscules
    extension = os.path.splitext(src)[1].lower()
    
    # Définir les correspondances entre extensions et outils
    if extension == '.pdf':
        return PDFSearchTool(pdf=src)
    elif extension == '.docx':
        return DOCXSearchTool(docx=src)
    elif extension == '.txt':
        return TXTSearchTool(txt=src)
    elif extension == '.csv':
        return CSVSearchTool(csv=src)
    else:
        supported_extensions = ['.pdf', '.docx', '.txt', '.csv']
        raise ValueError(
            f"Extension '{extension}' non supportée. "
            f"Extensions supportées : {', '.join(supported_extensions)}"
        )
