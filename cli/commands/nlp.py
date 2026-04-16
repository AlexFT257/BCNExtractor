"""
Comandos de análisis NLP:
  bcn nlp analizar <id>
  bcn nlp analizar-institucion <id>
  bcn nlp resolver
  bcn nlp referencias <id>
  bcn nlp entidades <id>
  bcn nlp obligaciones <id>
  bcn nlp stats
"""

from typing import Optional

import typer

from cli import output
from cli._internal import require_managers
from cli.console import console

app = typer.Typer(help="Análisis NLP de normas legales")


@app.command("analizar")
def analizar_norma(
    id: int = typer.Argument(..., help="ID de la norma a analizar"),
    forzar: bool = typer.Option(
        False, "--forzar", "-f", help="Re-analizar aunque ya tenga análisis previo"
    ),
):
    """Extrae referencias, entidades y obligaciones de una norma específica."""
    from bcn_client import BCNClient
    from utils.norm_parser import BCNXMLParser

    client = BCNClient()
    parser = BCNXMLParser()
    managers = require_managers()
    nlp_mgr = managers["nlp"]
    norms_mgr = managers["normas"]

    try:
        norma = norms_mgr.get_by_id(id)

        if not norma:
            output.error(f"Norma {id} no encontrada en la base de datos.")
            raise typer.Exit(1)

        console.print(f"\nAnalizando norma [cyan]{id}[/cyan] — {norma.get('titulo')}")

        xml = client.get_norma_completa(id)
        if not xml:
            output.error(f"No se pudo obtener el XML de la norma {id}.")
            raise typer.Exit(1)

        markdown, _ = parser.parse_from_string(xml)

        resultado = nlp_mgr.analizar_y_guardar(
            id_norma=id,
            texto_markdown=markdown,
        )

        output.print_nlp_resumen(resultado)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()
        managers["conn"].close()


@app.command("analizar-institucion")
def analizar_institucion(
    institucion: int = typer.Argument(..., help="ID de la institución"),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Máximo de normas a procesar"
    ),
    forzar: bool = typer.Option(
        False, "--forzar", "-f", help="Re-analizar normas que ya tienen análisis"
    ),
):
    """Analiza en batch todas las normas sincronizadas de una institución."""
    from bcn_client import BCNClient
    from utils.norm_parser import BCNXMLParser

    client = BCNClient()
    parser = BCNXMLParser()
    managers = require_managers()
    inst_mgr = managers["instituciones"]
    norms_mgr = managers["normas"]
    nlp_mgr = managers["nlp"]

    try:
        inst = inst_mgr.get_by_id(institucion)
        if not inst:
            output.error(f"Institución {institucion} no encontrada.")
            raise typer.Exit(1)

        console.print(f"\nAnalizando NLP — [bold cyan]{inst.nombre}[/bold cyan]")

        # Trae las normas registradas en DB para esta institución
        normas = norms_mgr.get_by_institucion(id_institucion=institucion, limit=limit)

        if not normas:
            output.warning("No hay normas sincronizadas para esta institución.")
            raise typer.Exit(0)

        # Filtrar las que ya tienen análisis salvo que se fuerce
        if not forzar:
            ids_con_analisis = nlp_mgr.get_normas_analizadas()
            for id in ids_con_analisis:
                for norma in normas:
                    if norma.get("id") == id:
                        normas.remove(norma)
                        break

        if not normas:
            output.info(
                "Todas las normas ya tienen análisis NLP. Usa --forzar para re-analizar."
            )
            raise typer.Exit(0)

        output.info(f"{len(normas)} normas a procesar\n")

        stats = {"ok": 0, "errores": 0, "sin_xml": 0, "referencias": 0, "entidades": 0}

        for i, norma in enumerate(normas, 1):
            id_norma = norma.get("id", None)
            if id_norma is None:
                continue
            try:
                # BCNClient usa caché — no llama a la BCN si el XML ya existe localmente
                xml = client.get_norma_completa(id_norma)
                if not xml:
                    stats["sin_xml"] += 1
                    output.print_sync_error(
                        i, len(normas), id_norma, "XML no disponible"
                    )
                    continue

                markdown, _ = parser.parse_from_string(xml)

                resultado = nlp_mgr.analizar_y_guardar(
                    id_norma=id_norma,
                    texto_markdown=markdown,
                )
                stats["ok"] += 1
                stats["referencias"] += len(resultado.referencias)
                stats["entidades"] += len(resultado.entidades)
                output.print_nlp_progress(i, len(normas), id_norma, resultado)

            except Exception as e:
                stats["errores"] += 1
                output.print_sync_error(i, len(normas), id_norma, str(e))

        output.print_nlp_batch_summary(stats, len(normas))

    except Exception as e:
        output.error(f"Error fatal: {e}")
        raise typer.Exit(1)
    finally:
        client.close()
        managers["conn"].close()


@app.command("resolver")
def resolver_referencias(
    id: Optional[int] = typer.Argument(
        None, help="ID de norma específica (omitir = todas las pendientes)"
    ),
):
    """Intenta resolver referencias normativas pendientes contra la DB local."""
    managers = require_managers()
    nlp_mgr = managers["nlp"]

    try:
        if id:
            console.print(f"\nResolviendo referencias de norma [cyan]{id}[/cyan]...")
        else:
            console.print("\nResolviendo todas las referencias pendientes...")

        resueltas = nlp_mgr.resolver_referencias_pendientes(id_norma=id)

        if resueltas:
            output.success(f"{resueltas} referencia(s) resueltas.")
        else:
            output.info("No se encontraron referencias nuevas para resolver.")

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("referencias")
def ver_referencias(
    id: int = typer.Argument(..., help="ID de la norma"),
    resueltas: bool = typer.Option(
        False, "--resueltas", "-r", help="Mostrar solo referencias resueltas"
    ),
):
    """Muestra las referencias normativas extraídas de una norma."""
    managers = require_managers()
    nlp_mgr = managers["nlp"]

    try:
        refs = nlp_mgr.get_referencias(id, solo_resueltas=resueltas)

        if not refs:
            label = "resueltas" if resueltas else ""
            output.warning(
                f"Norma {id} no tiene referencias normativas {label} registradas."
            )
            raise typer.Exit(0)

        output.print_nlp_referencias(id, refs)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("entidades")
def ver_entidades(
    id: int = typer.Argument(..., help="ID de la norma"),
    tipo: Optional[str] = typer.Option(
        None,
        "--tipo",
        "-t",
        help="Filtrar por tipo (organismo, persona, lugar, fecha)",
    ),
):
    """Muestra las entidades nombradas extraídas de una norma."""
    managers = require_managers()
    nlp_mgr = managers["nlp"]

    try:
        entidades = nlp_mgr.get_entidades(id, tipo=tipo)

        if not entidades:
            label = f" de tipo '{tipo}'" if tipo else ""
            output.warning(f"Norma {id} no tiene entidades{label} registradas.")
            raise typer.Exit(0)

        output.print_nlp_entidades(id, entidades)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("obligaciones")
def ver_obligaciones(
    id: int = typer.Argument(..., help="ID de la norma"),
    solo_con_plazo: bool = typer.Option(
        False, "--con-plazo", "-p", help="Mostrar solo obligaciones con plazo detectado"
    ),
):
    """Muestra las obligaciones y plazos detectados en una norma."""
    managers = require_managers()
    nlp_mgr = managers["nlp"]

    try:
        obligaciones = nlp_mgr.get_obligaciones(id)

        if solo_con_plazo:
            obligaciones = [o for o in obligaciones if o.get("plazo")]

        if not obligaciones:
            label = " con plazo" if solo_con_plazo else ""
            output.warning(f"Norma {id} no tiene obligaciones{label} registradas.")
            raise typer.Exit(0)

        output.print_nlp_obligaciones(id, obligaciones)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("stats")
def stats_nlp():
    """Muestra estadísticas globales del análisis NLP."""
    managers = require_managers()
    nlp_mgr = managers["nlp"]

    try:
        stats = nlp_mgr.get_stats_globales()
        output.print_nlp_stats(stats)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()
