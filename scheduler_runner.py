"""
Proceso independiente que ejecuta el APScheduler.
No se invoca directamente — lo lanza 'cli/commands/scheduler.py' via subprocess.

Uso interno:
    python scheduler_runner.py '{"inst_ids": [17, 42], "hora": 23, "minuto": 59, "limite": 200, "espaciado": 0}'
"""

import json
import logging
import os
import sys
from typing import Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from bcn_client import BCNClient
from managers.schedules import SchedulesManager
from managers.norms import NormsManager
from managers.institutions import InstitutionManager
from managers.norms_types import TiposNormasManager
from utils.db_logger import DBLogger
from utils.norm_parser import BCNXMLParser

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler_runner")



def _build_managers() -> dict:
    """Inicializa todos los managers con conexiones propias."""
    import psycopg2

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", 5432),
        database=os.getenv("POSTGRES_DB", "bcn_normas"),
        user=os.getenv("POSTGRES_USER", "bcn_user"),
        password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
    )
    return {
        "conn":          conn,
        "instituciones": InstitutionManager(conn),
        "tipos":         TiposNormasManager(conn),
        "normas":        NormsManager(conn),
        "logger":        DBLogger(conn),
    }


def _make_sync_job(inst_id: int, limite: int, managers: dict):
    """Devuelve la función de sync para un inst_id dado."""

    def job() -> None:
        client = BCNClient()
        parser = BCNXMLParser()

        inst_mgr = managers["instituciones"]
        tipos_mgr = managers["tipos"]
        norms_mgr = managers["normas"]
        db_logger = managers["logger"]

        try:
            normas = client.get_normas_por_institucion(inst_id)
            if not normas:
                logger.warning(f"[sync_{inst_id}] Sin normas disponibles.")
                return

            normas = normas[:limite]

            tipos_unicos = {
                n["id_tipo"]: {
                    "id": n["id_tipo"],
                    "nombre": n["tipo"],
                    "abreviatura": n["abreviatura"],
                }
                for n in normas
                if n.get("id_tipo") and n.get("tipo")
            }
            if tipos_unicos:
                tipos_mgr.add_batch(list(tipos_unicos.values()))

            for norma_info in normas:
                id_norma = norma_info["id"]
                try:
                    xml = client.get_norma_completa(id_norma)
                    if not xml:
                        db_logger.log(id_norma, "descarga", "error", "No se pudo descargar")
                        continue

                    markdown, metadata = parser.parse_from_string(xml)
                    parsed_data = {
                        "numero":             metadata.numero,
                        "titulo":             metadata.titulo,
                        "estado":             "derogada" if metadata.derogado else "vigente",
                        "fecha_publicacion":  metadata.fecha_publicacion,
                        "fecha_promulgacion": metadata.fecha_promulgacion,
                        "organismo":          metadata.organismos[0] if metadata.organismos else None,
                        "materias":           metadata.materias,
                        "organismos":         metadata.organismos,
                    }

                    norms_mgr.save(
                        id_norma=id_norma,
                        xml_content=xml,
                        parsed_data=parsed_data,
                        id_tipo=norma_info.get("id_tipo"),
                        id_institucion=inst_id,
                        markdown=markdown,
                        force=False,
                    )
                    db_logger.log(id_norma, "sincronizacion", "exitosa")

                except Exception as e:
                    logger.error(f"[sync_{inst_id}] Error en norma {id_norma}: {e}")
                    db_logger.log(id_norma, "sincronizacion", "error", str(e))

        except Exception as e:
            logger.error(f"[sync_{inst_id}] Error fatal: {e}")
        finally:
            client.close()

    return job


def main(inst_ids: list[int], hora: int, minuto: int, limite: int, espaciado: int, dia: Optional[str] = None) -> None:
    managers = _build_managers()
    schedules_mgr = SchedulesManager(managers["conn"])

    scheduler = BlockingScheduler(timezone="UTC")

    def listener(event) -> None:
        nombre = event.job_id
        if event.exception:
            logger.error(f"Job {nombre} falló: {event.exception}")
            schedules_mgr.update_run(nombre, "error", str(event.exception))
        else:
            logger.info(f"Job {nombre} completado OK.")
            schedules_mgr.update_run(nombre, "ok")

    scheduler.add_listener(listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    for i, inst_id in enumerate(inst_ids):
        total_minutos = minuto + i * espaciado
        h = (hora + total_minutos // 60) % 24
        m = total_minutos % 60
        nombre = f"sync_{inst_id}"

        scheduler.add_job(
            _make_sync_job(inst_id, limite, managers),
            CronTrigger(hour=h, minute=m),
            id=nombre,
            name=nombre,
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )
        schedules_mgr.upsert_job(
            inst_id=inst_id,
            nombre=nombre,
            hora=h,
            minuto=m,
            limite=limite,
        )
        logger.info(f"Job {nombre} registrado → {h:02d}:{m:02d} UTC diario.")

    logger.info("Scheduler iniciado.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler detenido.")
    finally:
        managers["conn"].close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scheduler_runner.py '<json_args>'")
        sys.exit(1)

    args = json.loads(sys.argv[1])
    main(
        inst_ids=args["inst_ids"],
        hora=args["hora"],
        minuto=args["minuto"],
        limite=args["limite"],
        espaciado=args["espaciado"],
        dia=args.get("dia"),
    )