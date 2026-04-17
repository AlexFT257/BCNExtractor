"""
Proceso independiente que ejecuta el APScheduler para UNA institución.
No se invoca directamente — lo lanza 'cli/commands/scheduler.py' via subprocess,
uno por cada institución a sincronizar.

Recibe un único JSON con los parámetros del job:
    {
        "inst_id": 17,
        "hora": 23,
        "minuto": 59,
        "limite": 200,
        "dia": "mon-fri",      # opcional
        "timezone": "UTC",     # opcional, default UTC
        "ahora": false         # opcional, ejecutar inmediatamente al arrancar
    }
"""

import json
import logging
import os
import signal
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


def _make_sync_job(inst_id: int, limite: int, managers: dict, schedules_mgr: SchedulesManager):
    """Devuelve la función de sync para un inst_id dado."""
    from services.sync import sync_institucion

    nombre = f"sync_{inst_id}"

    def job() -> None:
        job_logger = logging.getLogger(f"scheduler_runner.{nombre}")
        schedules_mgr.update_status(inst_id, "running")

        def on_log(msg: str) -> None:
            clean = (
                msg.replace("[/]", "").replace("[red]", "").replace("[green]", "")
                .replace("[cyan]", "").replace("[yellow]", "").replace("[dim]", "")
            )
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
    inst_id: int,
    hora: int,
    minuto: int,
    limite: int,
    dia: Optional[str] = None,
    timezone: str = "UTC",
    ahora: bool = False,
) -> None:
    managers = _build_managers()
    schedules_mgr = SchedulesManager(managers["conn"])
    nombre = f"sync_{inst_id}"

    # Registrar el job en DB al arrancar con estado "scheduled"
    schedules_mgr.upsert_job(
        inst_id=inst_id,
        nombre=nombre,
        hora=hora,
        minuto=minuto,
        limite=limite,
        pid=os.getpid(),
    )
    schedules_mgr.update_status(inst_id, "scheduled")
    logger.info(f"Job {nombre} registrado → {hora:02d}:{minuto:02d} {timezone} (PID {os.getpid()})")

    scheduler = BlockingScheduler(timezone=timezone)

    def listener(event) -> None:
        if event.exception:
            logger.error(f"Job {nombre} falló: {event.exception}")
            schedules_mgr.update_run(inst_id, "error", str(event.exception))
        else:
            logger.info(f"Job {nombre} completado OK.")
            schedules_mgr.update_run(inst_id, "ok")

    scheduler.add_listener(listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    sync_fn = _make_sync_job(inst_id, limite, managers, schedules_mgr)

    # Ejecución inmediata al arrancar — útil para testing
    if ahora:
        logger.info(f"Flag --ahora activo: ejecutando sync de #{inst_id} inmediatamente.")
        scheduler.add_job(
            sync_fn,
            id=f"{nombre}_ahora",
            name=f"{nombre}_ahora",
        )

    # Construir el trigger cron — día y timezone son opcionales
    trigger_kwargs: dict = {"hour": hora, "minute": minuto}
    if dia:
        trigger_kwargs["day_of_week"] = dia

    scheduler.add_job(
        sync_fn,
        CronTrigger(timezone=timezone, **trigger_kwargs),
        id=nombre,
        name=nombre,
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    def _graceful_shutdown(signum, frame) -> None:
        logger.info(f"Señal {signum} recibida — deteniendo {nombre}.")
        schedules_mgr.update_status(inst_id, "stopped")
        schedules_mgr.clear_pid(inst_id)
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _graceful_shutdown)
    # SIGINT solo en Unix; en Windows se ignora el segundo argumento
    if sys.platform != "win32":
        signal.signal(signal.SIGINT, _graceful_shutdown)

    logger.info(f"Scheduler para institución #{inst_id} iniciado.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info(f"Scheduler {nombre} detenido.")
        schedules_mgr.update_status(inst_id, "stopped")
    finally:
        schedules_mgr.clear_pid(inst_id)
        managers["conn"].close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scheduler_runner.py '<json_args>'")
        sys.exit(1)

    args = json.loads(sys.argv[1])
    main(
        inst_id=args["inst_id"],
        hora=args["hora"],
        minuto=args["minuto"],
        limite=args["limite"],
        dia=args.get("dia"),
        timezone=args.get("timezone", "UTC"),
        ahora=args.get("ahora", False),
    )