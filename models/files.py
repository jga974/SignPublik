 
from pydantic import BaseModel
from typing import Optional, Any

# Pour les parametres
class FileDef(BaseModel):
    filename: str
    content: str

class ImageRequest(BaseModel):
    image: FileDef
    recherche: Optional[str] = "Secrétaire"
    store: Optional[bool] = False

class SignBasePDFRequest(BaseModel):
    page: int
    ocrlayer: bool
    protect: bool
    protect_password: Optional[str] = None
    signature_box: Optional[str] = "350, 120, 550, 220"
    filedef1: FileDef

class InfoSearchPDFRequest(BaseModel):
    fichier: FileDef
    recherche: Optional[str] = "Secrétaire"

class SimplePDFPublik(BaseModel):
    fichier: FileDef

