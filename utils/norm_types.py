from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Norm(BaseModel):
    """Metadatos extraídos de una norma BCN."""

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

    def to_parsed_data(self) -> Dict[str, Any]:
        """Convierte el modelo al dict que esperan NormsManager y MetadataManager."""
        return {
            "numero": self.numero,
            "titulo": self.titulo,
            "estado": "derogada" if self.derogado else "vigente",
            "fecha_publicacion": self.fecha_publicacion,
            "fecha_promulgacion": self.fecha_promulgacion,
            "organismo": self.organismos[0] if self.organismos else None,
            "contenido_texto": None,
            # campos para MetadataManager
            "materias": self.materias,
            "organismos": self.organismos,
            "derogado": self.derogado,
            "es_tratado": self.es_tratado,
        }


class NormResponse(BaseModel):
    norma: Norm
    markdown: str
