"""
Comandos relacionados con normas:
  bcn normas list <institucion>
  bcn normas get <id>
  bcn normas sync <institucion>
  bcn normas search <query>
"""

from pathlib import Path
from typing import Optional

import typer

from cli import output
from cli._internal import require_managers
from cli.console import console

app = typer.Typer(help="Gestión de normas legales")


@app.command("list")
def list_normas(
    institucion: int = typer.Argument(..., help="ID de la institución"),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Máximo de normas a mostrar"
    ),
    output_path: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Guardar lista como JSON"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Lista normas de una institución consultando la BCN directamente."""
    import json

    from bcn_client import BCNClient

    client = BCNClient()
    try:
        console.print(
            f"\nConsultando normas de institución [cyan]{institucion}[/cyan]..."
        )
        normas = client.get_normas_por_institucion(institucion)

        if not normas:
            output.warning("No se encontraron normas.")
            raise typer.Exit(1)

        console.print(f"  [bold]{len(normas)}[/bold] normas encontradas\n")

        if limit:
            normas = normas[:limit]

        output.print_normas_list(normas, verbose=verbose)

        if output_path:
            output_path.write_text(
                json.dumps(normas, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            output.success(f"Lista guardada en {output_path}")

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("get")
def get_norma(
    id: int = typer.Argument(..., help="ID de la norma"),
    output_xml: Optional[Path] = typer.Option(
        None, "--xml", "-x", help="Guardar XML en ruta"
    ),
    output_md: Optional[Path] = typer.Option(
        None, "--md", "-m", help="Guardar Markdown en ruta"
    ),
    full: bool = typer.Option(False, "--full", "-f", help="Descargar texto completo"),
):
    """Descarga una norma específica desde la BCN."""
    from bcn_client import BCNClient
    from utils.norm_parser import BCNXMLParser

    client = BCNClient()
    parser = BCNXMLParser()

    try:
        console.print(f"\nDescargando norma [cyan]{id}[/cyan]...")

        xml = client.get_norma_completa(id) if full else client.get_norma_metadatos(id)
        if not xml:
            output.error(f"Norma {id} no encontrada.")
            raise typer.Exit(1)

        if output_md:
            markdown, _ = parser.parse_from_string(xml)
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(markdown, encoding="utf-8")
            output.success(f"Markdown guardado en {output_md}")

        if output_xml:
            output_xml.parent.mkdir(parents=True, exist_ok=True)
            output_xml.write_text(xml, encoding="utf-8")
            output.success(f"XML guardado en {output_xml}")

        if not output_md and not output_xml:
            output.print_norma_preview(xml)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("sync")
def sync(
    institucion: int = typer.Argument(..., help="ID de la institución"),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Máximo de normas a procesar"
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-descargar aunque no haya cambios"
    ),
):
    """Sincroniza normas de una institución a la base de datos."""
    from bcn_client import BCNClient
    from utils.norm_parser import BCNXMLParser

    client = BCNClient()
    parser = BCNXMLParser()
    managers = require_managers()

    inst_mgr = managers["instituciones"]
    tipos_mgr = managers["tipos"]
    norms_mgr = managers["normas"]
    logger = managers["logger"]

    try:
        inst = inst_mgr.get_by_id(institucion)
        if not inst:
            output.error(f"Institución {institucion} no encontrada en la DB.")
            raise typer.Exit(1)

        console.print(f"\nSincronizando [bold cyan]{inst.nombre}[/bold cyan]")

        normas = client.get_normas_por_institucion(institucion)
        if not normas:
            output.error("No se pudo obtener la lista de normas.")
            raise typer.Exit(1)

        total_disponibles = len(normas)
        if limit:
            normas = normas[:limit]

        output.info(
            f"{total_disponibles} normas disponibles — procesando {len(normas)}\n"
        )

        # Tipos en batch
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

        stats = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "errores": 0}

        for i, norma_info in enumerate(normas, 1):
            id_norma = norma_info["id"]
            try:
                xml = client.get_norma_completa(id_norma)
                if not xml:
                    output.print_sync_error(
                        i, len(normas), id_norma, "no se pudo descargar"
                    )
                    stats["errores"] += 1
                    logger.log(id_norma, "descarga", "error", "No se pudo descargar")
                    continue

                markdown, metadata = parser.parse_from_string(xml)

                result = norms_mgr.save(
                    id_norma=id_norma,
                    xml_content=xml,
                    parsed_data=metadata.to_parsed_data(),
                    id_tipo=norma_info.get("id_tipo"),
                    id_institucion=institucion,
                    markdown=markdown,
                    force=force,
                )

                stats[result] = stats.get(result, 0) + 1
                output.print_sync_progress(i, len(normas), id_norma, result)
                logger.log(id_norma, "sincronizacion", "exitosa")

            except Exception as e:
                output.print_sync_error(i, len(normas), id_norma, str(e))
                stats["errores"] += 1
                logger.log(id_norma, "sincronizacion", "error", str(e))

        output.print_sync_summary(stats, len(normas))

    except Exception as e:
        output.error(f"Error fatal: {e}")
        raise typer.Exit(1)
    finally:
        client.close()
        managers["conn"].close()


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Texto a buscar"),
    limit: int = typer.Option(20, "--limit", "-n", help="Máximo de resultados"),
):
    """Busca normas en la base de datos local (full-text search)."""
    from managers.norms import NormsManager

    managers = require_managers()
    norms_mgr = managers["normas"]

    try:
        console.print(f"\nBuscando: [bold]'{query}'[/bold]\n")
        results = norms_mgr.search(query, limit=limit)
        output.print_search_results(results)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("metadata")
def get_metadata(
    id: int = typer.Argument(..., help="ID de la norma"),
):
    """Muestra la metadata de una norma específica."""
    managers = require_managers()
    meta_mgr = managers["metadata"]

    try:
        metadata = meta_mgr.get_by_norma(id)
        output.print_norma_metadata(id, metadata)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("by-metadata")
def by_metadata(
    clave: str = typer.Argument(..., help="Clave de metadata (ej: materia, organismo)"),
    valor: str = typer.Argument(..., help="Valor a buscar"),
    limit: int = typer.Option(20, "--limit", "-n", help="Máximo de resultados"),
    offset: int = typer.Option(0, "--offset", help="Desplazamiento para paginación"),
):
    """Busca normas filtrando por una clave y valor de metadata."""
    managers = require_managers()
    meta_mgr = managers["metadata"]

    try:
        console.print(
            f"\nBuscando normas con [bold]{clave}[/bold] = '[bold cyan]{valor}[/bold cyan]'\n"
        )
        results = meta_mgr.get_normas_by_clave_valor(
            clave=clave, valor=valor, limit=limit, offset=offset
        )
        output.print_search_results(results)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()
