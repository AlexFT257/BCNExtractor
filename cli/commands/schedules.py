"""
Comandos para gestionar el scheduler de sync automático:
  bcn scheduler start  --inst 17,42,1041
  bcn scheduler stop
  bcn scheduler stop   --inst 17
  bcn scheduler status
  bcn scheduler add    <inst_id>
  bcn scheduler remove <id_job>
  bcn scheduler list
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

import psutil
import typer

from cli import output
from cli._internal import require_managers
from managers.schedules import SchedulesManager

app = typer.Typer(help="Gestión del scheduler de sync automático.")

LOG_DIR = Path("logs")

def _parse_ids(raw: str) -> List[int]:
    """Convierte '17,42,1041' o '17 42 1041' en [17, 42, 1041]."""
    return [int(x.strip()) for x in raw.replace(" ", ",").split(",") if x.strip()]


def _log_file_for(inst_id: int) -> Path:
    return LOG_DIR / f"scheduler_{inst_id}.log"


def _launch_process(args: List[str], log_path: Path) -> "subprocess.Popen":
    import subprocess

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a")

    if sys.platform == "win32":
        return subprocess.Popen(
            args,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )

    return subprocess.Popen(
        args,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _process_is_running(pid: int) -> bool:
    """Verifica si un PID está activo. Funciona en Windows, Mac y Linux."""
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _stop_process(pid: int) -> None:
    """Termina un proceso de forma segura en cualquier OS."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass
    except psutil.TimeoutExpired:
        proc.kill()


def _get_schedules_mgr(managers: dict) -> SchedulesManager:
    return SchedulesManager(managers["conn"])

@app.command("start")
def start(
    instituciones: str = typer.Option(
        ...,
        "--inst",
        "-i",
        help="IDs de instituciones separados por coma: 17,42,1041",
    ),
    dia: Optional[str] = typer.Option(
        None,
        "--dia",
        help="Día(s) de la semana: mon tue wed thu fri sat sun. Rangos: mon-fri. Varios: mon,wed,fri.",
    ),
    hora: int = typer.Option(23, "--hora", help="Hora de ejecución (0-23) en la zona horaria indicada"),
    minuto: int = typer.Option(59, "--minuto", help="Minuto de ejecución (0-59)"),
    limite: int = typer.Option(200, "--limit", "-n", help="Normas máximas por sync"),
    espaciado: int = typer.Option(
        0, "--gap", help="Minutos de separación entre instituciones"
    ),
    timezone: str = typer.Option("UTC", "--tz", help="Zona horaria del cron: UTC, America/Santiago, etc."),
    ahora: bool = typer.Option(False, "--ahora", help="Ejecutar el sync inmediatamente al arrancar (útil para testing)"),
):
    """Lanza un proceso scheduler independiente por cada institución."""
    ids = _parse_ids(instituciones)
    if not ids:
        output.error("No se especificaron instituciones válidas.")
        raise typer.Exit(1)

    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    lanzados = 0
    for i, inst_id in enumerate(ids):
        job = schedules_mgr.get_by_inst_id(inst_id)

        # Si ya hay un proceso vivo para esta institución, saltar
        if job and job.get("pid") and _process_is_running(job["pid"]):
            output.warning(
                f"Institución #{inst_id}: scheduler ya corriendo (PID {job['pid']}). Omitiendo."
            )
            continue

        # Calcular hora/minuto con espaciado entre instituciones
        total_minutos = minuto + i * espaciado
        h = (hora + total_minutos // 60) % 24
        m = total_minutos % 60

        args_json = json.dumps({
            "inst_id":  inst_id,
            "hora":     h,
            "minuto":   m,
            "limite":   limite,
            "dia":      dia,
            "timezone": timezone,
            "ahora":    ahora,
        })

        log_path = _log_file_for(inst_id)
        proc = _launch_process([sys.executable, "scheduler_runner.py", args_json], log_path)

        # Registrar PID en DB inmediatamente para que el proceso pueda actualizarlo luego
        schedules_mgr.upsert_job(
            inst_id=inst_id,
            nombre=f"sync_{inst_id}",
            hora=h,
            minuto=m,
            limite=limite,
            pid=proc.pid,
        )

        output.success(f"Institución #{inst_id}: scheduler iniciado (PID {proc.pid}) → {h:02d}:{m:02d} {timezone}.")
        if ahora:
            output.info(f"  Sync inmediato activo.")
        output.info(f"  Logs en: {log_path}")
        lanzados += 1

    managers["conn"].close()

    if lanzados == 0:
        output.warning("No se lanzó ningún proceso nuevo.")
    else:
        output.success(f"{lanzados} proceso(s) iniciado(s).")


@app.command("stop")
def stop(
    inst_id: Optional[int] = typer.Option(
        None, "--inst", "-i", help="Detener solo la institución indicada. Omitir = todas."
    ),
):
    """Detiene uno o todos los schedulers corriendo en background."""
    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    if inst_id:
        jobs = [schedules_mgr.get_by_inst_id(inst_id)]
        jobs = [j for j in jobs if j]
    else:
        jobs = schedules_mgr.get_running()

    if not jobs:
        output.warning("No hay schedulers activos registrados.")
        managers["conn"].close()
        raise typer.Exit(0)

    detenidos = 0
    for job in jobs:
        pid = job.get("pid")
        iid = job["inst_id"]

        if not pid:
            output.warning(f"Institución #{iid}: sin PID registrado — limpiando estado.")
            schedules_mgr.clear_pid(iid)
            continue

        if not _process_is_running(pid):
            output.warning(f"Institución #{iid}: PID {pid} no existe — limpiando estado.")
            schedules_mgr.clear_pid(iid)
            continue

        _stop_process(pid)
        # El proceso actualiza su propio estado via signal handler, pero como
        # respaldo también lo actualizamos aquí si el proceso no alcanzó a hacerlo.
        schedules_mgr.clear_pid(iid)
        output.success(f"Institución #{iid}: scheduler detenido (PID {pid}).")
        detenidos += 1

    managers["conn"].close()

    if detenidos:
        output.success(f"{detenidos} proceso(s) detenido(s).")


@app.command("status")
def status(
    inst_id: Optional[int] = typer.Option(
        None, "--inst", "-i", help="Ver estado de una institución específica."
    ),
):
    """Muestra el estado de los schedulers activos."""
    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    if inst_id:
        jobs = [schedules_mgr.get_by_inst_id(inst_id)]
        jobs = [j for j in jobs if j]
    else:
        jobs = schedules_mgr.get_all()

    if not jobs:
        output.info("No hay jobs registrados.")
        managers["conn"].close()
        return

    for job in jobs:
        pid = job.get("pid")
        iid = job["inst_id"]
        nombre = job["nombre"]

        if pid and _process_is_running(pid):
            output.success(f"{nombre}: corriendo (PID {pid}) — {job['status']}.")
        elif pid:
            # PID registrado pero proceso muerto — limpiar
            output.warning(f"{nombre}: PID {pid} registrado pero proceso no existe (posible crash). Limpiando.")
            schedules_mgr.clear_pid(iid)
        else:
            output.info(f"{nombre}: detenido. Último estado: {job.get('last_status') or 'nunca ejecutado'}.")

    managers["conn"].close()


@app.command("add")
def add(
    inst_id: int = typer.Argument(..., help="ID de la institución"),
    hora: int = typer.Option(23, "--hora", help="Hora de ejecución UTC (0-23)"),
    minuto: int = typer.Option(59, "--minuto", help="Minuto de ejecución (0-59)"),
    limite: int = typer.Option(200, "--limit", "-n", help="Normas máximas por sync"),
):
    """Registra o actualiza un job en la DB. Para activarlo usa 'scheduler start --inst <id>'."""
    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    try:
        schedules_mgr.upsert_job(
            inst_id=inst_id,
            nombre=f"sync_{inst_id}",
            hora=hora,
            minuto=minuto,
            limite=limite,
        )
        output.success(
            f"Job sync_{inst_id} registrado → {hora:02d}:{minuto:02d} UTC diario."
        )
        output.info("Usa 'scheduler start --inst <id>' para lanzar el proceso.")
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("remove")
def remove(
    id_job: int = typer.Argument(..., help="ID del job (ver con 'scheduler list')"),
):
    """Detiene y elimina un job de la DB por su ID."""
    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    try:
        job = schedules_mgr.get_by_id(id_job)
        if not job:
            output.error(f"No existe un job con ID {id_job}.")
            raise typer.Exit(1)

        pid = job.get("pid")
        if pid and _process_is_running(pid):
            _stop_process(pid)
            output.info(f"Proceso detenido (PID {pid}).")

        schedules_mgr.remove_job(id_job)
        output.success(f"Job {job['nombre']} eliminado.")
    except typer.Exit:
        raise
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("list")
def list_jobs(
    inst_id: Optional[int] = typer.Option(
        None, "--inst", "-i", help="Filtrar por institución"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Máximo de resultados"),
    offset: int = typer.Option(0, "--offset", help="Desplazamiento para paginación"),
):
    """Muestra los jobs registrados y su estado."""
    managers = require_managers()
    schedules_mgr = _get_schedules_mgr(managers)

    try:
        if inst_id:
            job = schedules_mgr.get_by_inst_id(inst_id)
            jobs = [job] if job else []
        else:
            jobs = schedules_mgr.get_all(limit=limit, offset=offset)

        output.print_scheduler_jobs(jobs)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()