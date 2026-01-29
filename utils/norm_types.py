from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import date

class Norm(BaseModel):
    """Metadatos extraídos de la norma"""
    norma_id: int
    tipo: str
    numero: str
    titulo: str
    fecha_publicacion: Optional[date]
    fecha_promulgacion: Optional[date]
    organismos: List[str]
    derogado: bool
    es_tratado: bool
    materias: List[str]

        
class NormResponse(BaseModel):
    norma: Norm
    markdown: str
    
    
        
        

        