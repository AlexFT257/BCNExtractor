"""
Proceso independiente que ejecuta el APScheduler.
No se invoca directamente — lo lanza 'cli/commands/scheduler.py' via subprocess.
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

from managers.downloads import DownloadManager
from managers.institutions import InstitutionManager
from managers.metadata import MetadataManager
from managers.norms import NormsManager
from managers.norms_types import TiposNormasManager
from managers.schedules import SchedulesManager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler_runner")


def _build_managers() -> dict:
    """Inicializa managers con una conexión compartida para el proceso scheduler."""
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
        "normas":        NormsManager(db_connection=conn),
        "metadata":      MetadataManager(db_connection=conn),
        "logger":        DownloadManager(conn),
    }


def _make_sync_job(inst_id: int, limite: int, managers: dict):
    """Devuelve la función de sync para un inst_id dado."""
    from services.sync import sync_institucion

    def job() -> None:
        job_logger = logging.getLogger(f"scheduler_runner.sync_{inst_id}")

        def on_log(msg: str) -> None:
            # Quitar markup Rich antes de escribir al logger de archivo
            clean = msg.replace("[/]", "").replace("[red]", "").replace("[green]", "")
            clean = clean.replace("[cyan]", "").replace("[yellow]", "").replace("[dim]", "")
            job_logger.info(clean)

        stats = sync_institucion(
            inst_id=inst_id,
            managers=managers,
            limit=limite,
            on_log=on_log,
        )

        job_logger.info(f"Sync finalizado: {stats.resumen()}")

    return job


def main(
    inst_ids: list,
    hora: int,
    minuto: int,
    limite: int,
    espaciado: int,
    dia: Optional[str] = None,
) -> None:
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
    nombre = ""
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
        if nombre:
            schedules_mgr.update_run(nombre, "stopped", "User stopped")
    finally:
        managers["conn"].close()
        if nombre:
            schedules_mgr.update_run(nombre, "completed")


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