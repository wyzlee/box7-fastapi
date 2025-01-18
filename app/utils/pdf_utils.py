import os
import shutil
import pypdf
import aiofiles
from io import BytesIO
from pypdf import PdfWriter
from docx import Document

async def extract_page_text_from_file(src: str) -> list:
    """
    Extrait le texte d'un fichier PDF ou DOCX page par page de manière asynchrone.
    
    Args:
        src (str): Chemin vers le fichier source
        
    Returns:
        list: Liste des textes extraits par page
    """
    texte_pages = []
    try:
        extension = os.path.splitext(src)[1].lower()

        if extension == '.pdf':
            async with aiofiles.open(src, 'rb') as pdf_file:
                file_content = await pdf_file.read()
                # Créer un objet BytesIO à partir des bytes lus
                pdf_bytes = BytesIO(file_content)
                reader = pypdf.PdfReader(pdf_bytes)

                for page_num, page in enumerate(reader.pages):
                    try:
                        texte = page.extract_text()
                        if texte:
                            texte_pages.append(texte)
                        else:
                            print(f"Le texte de la page {page_num + 1} est vide ou illisible.")
                    except Exception as e:
                        print(f"Erreur lors de l'extraction du texte de la page {page_num + 1}: {e}")

        elif extension == '.docx':
            try:
                doc = Document(src)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

                # Grouper les paragraphes par blocs de 11
                bloc = []
                for i, paragraphe in enumerate(paragraphs, start=1):
                    bloc.append(paragraphe)
                    if i % 11 == 0:
                        texte_pages.append("\n".join(bloc))
                        bloc = []

                if bloc:
                    texte_pages.append("\n".join(bloc))

            except Exception as e:
                print(f"Erreur lors de la lecture du fichier DOCX : {e}")
                raise

    except Exception as e:
        print(f"Erreur lors de la lecture du fichier : {e}")
        raise

    return texte_pages
