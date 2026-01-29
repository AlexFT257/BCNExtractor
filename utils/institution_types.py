from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class Institution(BaseModel):
    id: int
    nombre: str
    fecha_agregada: datetime
    fecha_actualizada: Optional[datetime]
