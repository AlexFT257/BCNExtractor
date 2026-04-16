"""
Adaptador de sync para la API REST. Llama a services.sync.sync_institucion
sin callbacks de progreso — la API devuelve el SyncStats al completar.

Para progreso en tiempo real desde la API se puede implementar un endpoint
SSE en el futuro pasando un on_progress que escriba a un asyncio.Queue.
"""

from services.sync import SyncStats, sync_institucion
from api.dependencies import (
    get_metadata_manager,
    get_download_logger,
    get_norm_manager,
    get_tipos_manager,
)


def sync_normas_institucion(normas: list, institucion_id: int) -> dict:
    """
    Sincroniza las normas de una institución desde la API REST.

    Recibe la lista de normas ya obtenida por el router para evitar
    una segunda llamada a la BCN. Los managers se obtienen de las
    dependencias FastAPI (instancias compartidas por la app).

    Returns:
        Dict con el resumen de la operación (SyncStats.as_dict()).
    """
    managers = {
        "conn":     get_norm_manager().conn,
        "normas":   get_norm_manager(),
        "tipos":    get_tipos_manager(),
        "metadata": get_metadata_manager(),
        "logger":   get_download_logger(),
    }

    # La API no tiene límite propio — lo debe aplicar el router antes de llamar aquí
    # TODO: Agregar límite, queue/on_progress
    stats: SyncStats = sync_institucion(
        inst_id=institucion_id,
        managers=managers,
    )

    return stats.as_dict()
