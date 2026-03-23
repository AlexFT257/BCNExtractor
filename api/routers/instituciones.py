from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_client, get_institution_manager, get_norm_manager
from api.services.sync import sync_normas_institucion

router = APIRouter(prefix="/instituciones", tags=["instituciones"])


@router.get("/stats")
def get_stats(institution_manager=Depends(get_institution_manager)):
    stats = institution_manager.get_stats()
    if not stats:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron estadísticas para esta institución",
        )
    return stats


@router.get("/")
def get_instituciones(manager=Depends(get_institution_manager)):
    instituciones = manager.get_all()
    if not instituciones:
        raise HTTPException(status_code=404, detail="No se encontraron instituciones")
    return instituciones


@router.get("/buscar/{nombre}")
def buscar_instituciones(
    nombre: str,
    limit: int = 20,
    offset: int = 0,
    manager=Depends(get_institution_manager),
):
    instituciones = manager.search(nombre, limit=limit, offset=offset)
    if not instituciones:
        raise HTTPException(status_code=404, detail="No se encontraron instituciones")
    return instituciones


@router.get("/{institucion_id}")
def get_institucion(institucion_id: int, manager=Depends(get_institution_manager)):
    institucion = manager.get_by_id(institucion_id)
    if not institucion:
        raise HTTPException(status_code=404, detail="Institución no encontrada")
    return institucion


@router.get("/{institucion_id}/normas")
def get_normas_por_institucion(
    institucion_id: int,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    institution_manager=Depends(get_institution_manager),
    norm_manager=Depends(get_norm_manager),
):
    if not institution_manager.get_by_id(institucion_id):
        raise HTTPException(status_code=404, detail="Institución no encontrada")
    results = norm_manager.get_by_institucion(
        institucion_id, limit=limit, offset=offset
    )
    if not results:
        raise HTTPException(
            status_code=404, detail="No se encontraron normas para esta institución"
        )
    return {"normas": results, "limit": limit, "offset": offset}


@router.put("/{institucion_id}/normas")
def sync_normas(
    institucion_id: int,
    limit: Optional[int] = None,
    client=Depends(get_client),
    manager=Depends(get_institution_manager),
):
    if not manager.get_by_id(institucion_id):
        raise HTTPException(status_code=404, detail="Institución no encontrada")
    normas = client.get_normas_por_institucion(institucion_id)
    if not normas:
        raise HTTPException(
            status_code=404, detail="No se encontraron normas para esta institución"
        )
    if limit:
        normas = normas[:limit]
    return sync_normas_institucion(normas, institucion_id)
