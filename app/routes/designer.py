from fastapi import APIRouter, HTTPException, status, Depends, Cookie
from typing import Optional, Dict
import json
import os
from pathlib import Path

router = APIRouter()

@router.post("/designer/save-diagram")
async def save_diagram(data: Dict, session: Optional[str] = Cookie(None)):
    """
    Save a diagram to a JSON file.
    
    Args:
        data (Dict): Dictionary containing diagram data with 'name' and 'diagram' fields
        session: Session cookie for authentication
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié"
        )

    try:
        # Create diagrams directory if it doesn't exist
        diagrams_dir = Path("diagrams")
        diagrams_dir.mkdir(exist_ok=True)
        
        # Ensure file name ends with .json
        file_name = data["name"]
        if not file_name.endswith('.json'):
            file_name += '.json'
            
        file_path = diagrams_dir / file_name
        
        # Parse diagram data
        diagram_data = json.loads(data["diagram"])
        
        # Save to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(diagram_data, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "message": "Diagramme sauvegardé avec succès"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/designer/get-diagram/{filename}")
async def get_diagram(filename: str, session: Optional[str] = Cookie(None)):
    """
    Get a diagram from a JSON file.
    
    Args:
        filename (str): Name of the diagram file
        session: Session cookie for authentication
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié"
        )

    try:
        # Ensure file name ends with .json
        if not filename.endswith('.json'):
            filename += '.json'
            
        file_path = Path("diagrams") / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Diagramme {filename} non trouvé"
            )
            
        # Read from file
        with open(file_path, 'r', encoding='utf-8') as f:
            diagram_data = json.load(f)
            
        return diagram_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/designer/delete-diagram/{filename}")
async def delete_diagram(filename: str, session: Optional[str] = Cookie(None)):
    """
    Delete a diagram file.
    
    Args:
        filename (str): Name of the diagram file to delete
        session: Session cookie for authentication
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié"
        )

    try:
        # Ensure file name ends with .json
        if not filename.endswith('.json'):
            filename += '.json'
            
        file_path = Path("diagrams") / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Diagramme {filename} non trouvé"
            )
            
        # Delete file
        os.remove(file_path)
        
        return {"status": "success", "message": "Diagramme supprimé avec succès"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
