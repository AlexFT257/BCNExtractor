"""
Lógica de sincronización de normas — único punto de verdad para todas las interfaces.

Consumidores:
    CLI      → pasa on_progress con Rich console, on_log ignorado
    TUI      → pasa on_progress y on_log con call_from_thread
    API REST → no pasa callbacks; recibe el SyncStats al finalizar
    Scheduler→ no pasa callbacks; los errores quedan en el logger de DB

Flujo:
    1. Obtener lista de normas de la BCN para la institución
    2. Registrar tipos en batch
    3. Por cada norma: descargar XML → parsear → save + metadata EAV → log DB
    4. Emitir eventos de progreso vía callbacks opcionales
    5. Devolver SyncStats

La función no abre ni cierra conexiones — recibe los managers ya construidos
para que cada interfaz controle el ciclo de vida de su conexión.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tipo del callback de progreso.
# Argumentos: (procesadas, total, id_norma, resultado)
# resultado: "nueva" | "actualizada" | "sin_cambios" | "error"
ProgressCallback = Callable[[int, int, int, str], None]

# Tipo del callback de log libre (para TUI/scheduler).
# Argumento: mensaje ya formateado (puede incluir markup Rich)
LogCallback = Callable[[str], None]


@dataclass
class SyncStats:
    """Resultado de una sincronización completa."""

    nuevas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    errores: int = 0
    cancelada: bool = False

    @property
    def total_procesadas(self) -> int:
        return self.nuevas + self.actualizadas + self.sin_cambios + self.errores

    def as_dict(self) -> Dict:
        return {
            "nuevas": self.nuevas,
            "actualizadas": self.actualizadas,
            "sin_cambios": self.sin_cambios,
            "errores": self.errores,
            "total_procesadas": self.total_procesadas,
            "cancelada": self.cancelada,
        }

    def resumen(self) -> str:
        sufijo = " (cancelada)" if self.cancelada else ""
        return (
            f"{self.nuevas} nuevas, {self.actualizadas} actualizadas, "
            f"{self.sin_cambios} sin cambios, {self.errores} errores{sufijo}"
        )


def sync_institucion(
    inst_id: int,
    managers: dict,
    limit: Optional[int] = None,
    force: bool = False,
    on_progress: Optional[ProgressCallback] = None,
    on_log: Optional[LogCallback] = None,
    cancelado: Optional[Callable[[], bool]] = None,
) -> SyncStats:
    """
    Sincroniza todas las normas de una institución a la base de datos.

    Args:
        inst_id:     ID de la institución en BCN.
        managers:    Dict con keys: conn, normas, tipos, metadata, logger.
                     La función no abre ni cierra la conexión.
        limit:       Máximo de normas a procesar. None = todas.
        force:       Re-guardar aunque el XML no haya cambiado.
        on_progress: Callback llamado tras procesar cada norma.
                     Firma: (procesadas, total, id_norma, resultado) -> None
        on_log:      Callback para mensajes de texto durante el proceso.
                     Firma: (msg: str) -> None
        cancelado:   Callable que devuelve True si el llamador quiere abortar.
                     La función lo consulta antes de cada norma.

    Returns:
        SyncStats con el resultado de la operación.
    """
    from bcn_client import BCNClient
    from utils.norm_parser import BCNXMLParser

    def log(msg: str) -> None:
        logger.info(msg)
        if on_log:
            on_log(msg)

    stats = SyncStats()
    client = BCNClient()
    parser = BCNXMLParser()

    try:
        log(f"Consultando normas de institución #{inst_id} en BCN...")
        normas = client.get_normas_por_institucion(inst_id)

        if not normas:
            log("[red]Sin normas disponibles en BCN para esta institución.[/red]")
            return stats

        if limit:
            normas = normas[:limit]

        total = len(normas)
        log(f"{total} normas en cola")

        # ── Tipos en batch antes del loop principal ────────────────────────────
        tipos = {
            n["id_tipo"]: {
                "id": n["id_tipo"],
                "nombre": n["tipo"],
                "abreviatura": n["abreviatura"],
            }
            for n in normas
            if n.get("id_tipo") and n.get("tipo")
        }
        if tipos:
            managers["tipos"].add_batch(list(tipos.values()))

        # ── Loop principal ─────────────────────────────────────────────────────
        for i, norma_info in enumerate(normas, 1):
            if cancelado and cancelado():
                log("[yellow]Sync cancelado por el usuario.[/yellow]")
                stats.cancelada = True
                break

            nid = norma_info["id"]
            resultado = _procesar_norma(
                nid=nid,
                norma_info=norma_info,
                inst_id=inst_id,
                managers=managers,
                client=client,
                parser=parser,
                force=force,
                log=log,
            )

            # Acumular stats
            if resultado == "nueva":
                stats.nuevas += 1
            elif resultado == "actualizada":
                stats.actualizadas += 1
            elif resultado == "sin_cambios":
                stats.sin_cambios += 1
            else:
                stats.errores += 1

            if on_progress:
                on_progress(i, total, nid, resultado)

        log(f"Completado: {stats.resumen()}")

    finally:
        client.close()

    return stats


def _procesar_norma(
    nid: int,
    norma_info: dict,
    inst_id: int,
    managers: dict,
    client,
    parser,
    force: bool,
    log: Callable[[str], None],
) -> str:
    """
    Descarga, parsea y guarda una norma individual.

    Devuelve el resultado: "nueva" | "actualizada" | "sin_cambios" | "error"
    """
    try:
        xml = client.get_norma_completa(nid)

        if not xml:
            managers["logger"].log(nid, "error", "sincronizacion", "Sin respuesta XML")
            log(f"[red]✗ #{nid} sin respuesta XML[/red]")
            return "error"

        markdown, metadata = parser.parse_from_string(xml)

        # to_parsed_data() es la fuente de verdad — evita construir el dict a mano
        parsed = metadata.to_parsed_data()

        result = managers["normas"].save(
            id_norma=nid,
            xml_content=xml,
            parsed_data=parsed,
            id_tipo=norma_info.get("id_tipo"),
            id_institucion=inst_id,
            markdown=markdown,
            force=force,
        )

        # Metadata EAV — solo cuando hay algo que escribir
        if result in ("nueva", "actualizada"):
            cursor = managers["conn"].cursor()
            managers["metadata"].save(cursor, nid, parsed)
            managers["conn"].commit()
            cursor.close()

        managers["logger"].log(nid, "exitosa", "sincronizacion")
        log(f"[{'green' if result == 'nueva' else 'cyan' if result == 'actualizada' else 'dim'}]"
            f"✓ #{nid} {result}[/]")
        return result

    except Exception as e:
        managers["logger"].log(nid, "error", "sincronizacion", str(e))
        log(f"[red]✗ #{nid} {str(e)[:72]}[/red]")
        return "error"