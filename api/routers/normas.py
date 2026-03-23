from datetime import date
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from api.dependencies import get_client, get_parser, get_norm_manager
from utils.norm_types import NormResponse

router = APIRouter(prefix="/normas", tags=["normas"])


@router.get("/stats")
def get_stats(
    norm_manager=Depends(get_norm_manager),
):
    stats = norm_manager.get_stats()
    if not stats:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron estadísticas para esta institución",
        )
    return stats


@router.get("/buscar/{query}")
def search_normas(
    query: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    manager=Depends(get_norm_manager),
):
    results = manager.search(query, limit=limit, offset=offset)
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron resultados")
    return {"normas": results, "limit": limit, "offset": offset}


@router.get("/estado/{estado}")
def get_normas_by_status(
    estado: Literal["vigente", "derogada"],
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    manager=Depends(get_norm_manager),
):
    results = manager.get_by_status(estado, limit=limit, offset=offset)
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron normas")
    return {"normas": results, "limit": limit, "offset": offset}


@router.get("/tipo/{tipo}")
def get_normas_by_type(
    tipo: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    manager=Depends(get_norm_manager),
):
    results = manager.get_by_type(tipo, limit=limit, offset=offset)
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron normas para ese tipo")
    return {"normas": results, "limit": limit, "offset": offset}


@router.get("/rango")
def get_normas_by_date_range(
    start_date: date,
    end_date: date = date.today(),
    date_type: Literal["pub", "prom"] = Query(default="pub"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    manager=Depends(get_norm_manager),
):
    results = manager.get_by_range_date(
        start_date=start_date,
        end_date=end_date,
        date_type=date_type,
        limit=limit,
        offset=offset,
    )
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron normas en ese rango")
    return {"normas": results, "limit": limit, "offset": offset}


@router.get("/")
def get_all_normas(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    manager=Depends(get_norm_manager),
):
    results = manager.get_all(limit=limit, offset=offset)
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron normas")
    return {"normas": results, "limit": limit, "offset": offset}


@router.get("/{norma_id}")
def get_norma(
    norma_id: int,
    client=Depends(get_client),
    parser=Depends(get_parser),
):
    norma = client.get_norma_completa(norma_id)
    if not norma:
        raise HTTPException(status_code=404, detail="Norma no encontrada")
    markdown, norm_data = parser.parse_from_string(norma)
    return NormResponse(norma=norm_data, markdown=markdown)


@router.post("/batch")
def get_normas_batch(
    normas_id: list[int],
    client=Depends(get_client),
    parser=Depends(get_parser),
):
    if not normas_id:
        raise HTTPException(status_code=400, detail="No se proporcionaron IDs de normas")
    normas = []
    for norma_id in normas_id:
        norma = client.get_norma_completa(norma_id)
        if not norma:
            raise HTTPException(status_code=404, detail=f"Norma {norma_id} no encontrada")
        markdown, norm_data = parser.parse_from_string(norma)
        normas.append({"norma": norm_data, "markdown": markdown})
    return normas
    
