"""
Comandos para gestionar el scheduler de sync automático:
  bcn scheduler start  --inst 17,42,1041
  bcn scheduler stop
  bcn scheduler status
  bcn scheduler add    <inst_id>
  bcn scheduler remove <id_job>
  bcn scheduler list
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import psutil
import typer

from cli import output
from cli._internal import require_managers
from managers.schedules import SchedulesManager

app = typer.Typer(help="Gestión del scheduler de sync automático.")

PID_FILE = Path(".scheduler.pid")
LOG_FILE = Path("logs/scheduler.log")


# ── Helpers de proceso ────────────────────────────────────────────────────────


def _parse_ids(raw: str) -> list[int]:
    """Convierte '17,42,1041' o '17 42 1041' en [17, 42, 1041]."""
    return [int(x.strip()) for x in raw.replace(" ", ",").split(",") if x.strip()]


def _launch_process(args: list[str]) -> subprocess.Popen:
    """Lanza un proceso desacoplado del padre. Compatible con Windows, Mac y Linux."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG_FILE, "a")

    if sys.platform == "win32":
        return subprocess.Popen(
            args,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS,
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


def _read_pid() -> Optional[int]:
    """Lee el PID guardado. Retorna None si el archivo no existe."""
    if not PID_FILE.exists():
        return None
    return int(PID_FILE.read_text().strip().split(",")[0])


def _clear_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


# ── Comandos ──────────────────────────────────────────────────────────────────


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
        help="Día(s) de la semana: mon tue wed thu fri sat sun. Rangos: mon-fri. Varios: mon,wed,fri. Omitir = todos los días.",
    ),
    hora: int = typer.Option(23, "--hora", help="Hora de ejecución UTC (0-23)"),
    minuto: int = typer.Option(59, "--minuto", help="Minuto de ejecución (0-59)"),
    limite: int = typer.Option(200, "--limit", "-n", help="Normas máximas por sync"),
    espaciado: int = typer.Option(
        0, "--gap", help="Minutos de separación entre instituciones"
    ),
):
    """Lanza el scheduler como proceso independiente en background."""
    ids = _parse_ids(instituciones)
    if not ids:
        output.error("No se especificaron instituciones válidas.")
        raise typer.Exit(1)

    pid = _read_pid()
    if pid and _process_is_running(pid):
        output.warning(f"El scheduler ya está corriendo (PID {pid}).")
        output.info("Usa 'scheduler stop' para detenerlo primero.")
        raise typer.Exit(0)

    if pid:
        output.warning("PID registrado pero proceso no existe — limpiando.")
        _clear_pid()

    args_json = json.dumps(
        {
            "inst_ids": ids,
            "hora": hora,
            "minuto": minuto,
            "limite": limite,
            "espaciado": espaciado,
            "dia": dia,
        }
    )

    proc = _launch_process([sys.executable, "scheduler_runner.py", args_json])
    PID_FILE.write_text(str(proc.pid) + f",{instituciones}")

    output.success(f"Scheduler iniciado en background (PID {proc.pid}).")
    output.info(f"Instituciones: {', '.join(str(i) for i in ids)}")
    output.info(f"Logs en: {LOG_FILE}")


@app.command("stop")
def stop():
    """Detiene el scheduler que está corriendo en background."""
    pid = _read_pid()
    if not pid:
        output.warning("No hay scheduler corriendo.")
        raise typer.Exit(0)

    if not _process_is_running(pid):
        output.warning(f"PID {pid} registrado pero proceso no existe — limpiando.")
        _clear_pid()
        raise typer.Exit(0)

    _stop_process(pid)
    _clear_pid()
    output.success(f"Scheduler detenido (PID {pid}).")


@app.command("status")
def status():
    """Muestra si el scheduler está corriendo y desde qué PID."""
    pid = _read_pid()

    if not pid:
        output.info("Scheduler: detenido.")
        return

    if _process_is_running(pid):
        output.success(f"Scheduler: corriendo (PID {pid}).")
        output.info(f"Logs en: {LOG_FILE}")
    else:
        output.warning(
            "Scheduler: PID registrado pero proceso no existe (posible crash)."
        )
        output.info("Usa 'scheduler start' para reiniciarlo.")
        _clear_pid()


@app.command("add")
def add(
    inst_id: int = typer.Argument(..., help="ID de la institución"),
    hora: int = typer.Option(23, "--hora", help="Hora de ejecución UTC (0-23)"),
    minuto: int = typer.Option(59, "--minuto", help="Minuto de ejecución (0-59)"),
    limite: int = typer.Option(200, "--limit", "-n", help="Normas máximas por sync"),
):
    """Registra o actualiza un job en la DB. Surte efecto al próximo start."""
    managers = require_managers()
    schedules_mgr = SchedulesManager(managers["conn"])

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
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("remove")
def remove(
    id_job: int = typer.Argument(..., help="ID del job (ver con 'scheduler list')"),
):
    """Elimina un job de la DB por su ID."""
    managers = require_managers()
    schedules_mgr = SchedulesManager(managers["conn"])

    try:
        job = schedules_mgr.get_by_id(id_job)
        if not job:
            output.error(f"No existe un job con ID {id_job}.")
            raise typer.Exit(1)

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
    schedules_mgr = SchedulesManager(managers["conn"])

    try:
        if inst_id:
            jobs = schedules_mgr.get_by_inst_id(inst_id, limit=limit, offset=offset)
        else:
            jobs = schedules_mgr.get_all(limit=limit, offset=offset)

        output.print_scheduler_jobs(jobs)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()
