"""
CLI Principal para interactuar con BCN
Orquesta todos los componentes
"""

import argparse
import json
import sys
from pathlib import Path

from bcn_client import BCNClient
from loaders.institutions import InstitutionLoader
from managers.downloads import DownloadManager
from managers.institutions import InstitutionManager
from managers.norms import NormsManager
from managers.norms_types import TiposNormasManager
from utils.norm_parser import BCNXMLParser


def _create_connection():
    """Crea y retorna una conexion PostgreSQL"""
    import os

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()

    return psycopg2.connect(
        host="localhost",
        port=os.getenv("POSTGRES_PORT", 5432),
        database=os.getenv("POSTGRES_DB", "bcn_normas"),
        user=os.getenv("POSTGRES_USER", "bcn_user"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )


def init_managers():
    """
    Inicializa todos los managers en el orden correcto
    y con una única conexión a base de datos.
    """
    try:
        conn = _create_connection()
        inst_loader = InstitutionLoader(db_connection=conn)
        tipos_mgr = TiposNormasManager(db_connection=conn)
        norms_mgr = NormsManager(db_connection=conn)
        inst_mgr = InstitutionManager(db_connection=conn)
        logger = DownloadManager(db_connection=conn)

        return {
            "conn": conn,
            "instituciones": inst_mgr,
            "instituciones_loader": inst_loader,
            "tipos": tipos_mgr,
            "normas": norms_mgr,
            "logger": logger,
        }
    except Exception as e:
        print(f"Error al inicializar el cliente: {e}")
        return None


def init_db(args=None):
    """Inicializa el esquema de la base de datos y carga las instituciones."""
    print("\n── Inicializando Base de Datos ──")
    managers = init_managers()
    if not managers:
        return 1

    # Cargar instituciones desde el CSV incluido en el repo
    csv_path = (
        Path(args.csv)
        if args and hasattr(args, "csv") and args.csv
        else Path("data/instituciones.csv")
    )
    if csv_path.exists():
        print(f"\n── Cargando instituciones desde {csv_path} ──")
        try:
            stats = managers["instituciones_loader"].load_from_csv(
                str(csv_path), mode="append"
            )
            print(
                f"✓ {stats['insertadas']} instituciones cargadas ({stats['total']} en CSV)"
            )
        except Exception as e:
            print(f"⚠ No se pudieron cargar instituciones: {e}")
    else:
        print(f"⚠ CSV no encontrado en {csv_path} — omitiendo carga de instituciones")

    managers["conn"].close()
    print("\n✓ Base de datos inicializada correctamente\n")
    return 0


def list_normas_command(args):
    """Lista normas de una institución"""
    client = BCNClient()

    try:
        print(f"\nConsultando normas de institución {args.institucion}...")
        normas = client.get_normas_por_institucion(args.institucion)

        if not normas:
            print("\tNo se encontraron normas")
            return 1

        print(f"\n{len(normas)} normas encontradas\n")

        if args.limit:
            normas = normas[: args.limit]

        for i, norma in enumerate(normas, 1):
            print(f"{i:3d}. [{norma['id']:6d}] {norma['tipo']} {norma['numero']}")
            print(f"\t{norma['titulo'][:70]}")
            if args.verbose:
                print(f"\tPublicación: {norma['fecha_publicacion']}")
            print()

        # Guardar como JSON
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(
                json.dumps(normas, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"✓ Lista guardada en {output_path}")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        client.close()


def get_norma_command(args):
    """Descarga una norma específica"""
    client = BCNClient()
    parser = BCNXMLParser()

    try:
        print(f"\nDescargando norma {args.id}...")

        # Descargar
        if args.full:
            xml = client.get_norma_completa(args.id)
        else:
            xml = client.get_norma_metadatos(args.id)

        if not xml:
            print(f"  ✗ Norma {args.id} no encontrada")
            return 1

        # Guardar Markdown
        if args.output_md:
            markdown, metadata = parser.parse_from_string(xml)
            output_path = Path(args.output_md)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
            print(f"  ✓ Markdown guardado en {output_path}")

        # Guardar XML
        if args.output_xml:
            output_path = Path(args.output_xml)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(xml, encoding="utf-8")
            print(f"  ✓ XML guardado en {output_path}")

        # Vista previa
        if not args.output_md and not args.output_xml:
            lines = xml.split("\n")[:30]
            print("\n" + "=" * 60)
            print("Vista previa (primeras 30 líneas)")
            print("=" * 60)
            for line in lines:
                print(line)
            print("...")

        return 0

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return 1
    finally:
        client.close()


def sync_command(args):
    """Sincroniza normas de una institución a la DB"""
    client = BCNClient()
    parser = BCNXMLParser()

    managers = init_managers()
    if not managers:
        return 1

    inst_mgr = managers["instituciones"]
    tipos_mgr = managers["tipos"]
    norms_mgr = managers["normas"]
    logger = managers["logger"]

    try:
        print(f"\n{'=' * 60}")
        print(f"SINCRONIZANDO INSTITUCIÓN {args.institucion}")
        print(f"{'=' * 60}")

        # Verificar institución
        inst = inst_mgr.get_by_id(args.institucion)
        if not inst:
            print(f"✗ Institución {args.institucion} no encontrada")
            return 1

        print(f"Institución: {inst.nombre}")

        # Obtener lista
        normas = client.get_normas_por_institucion(args.institucion)
        if not normas:
            print("✗ No se pudo obtener lista")
            return 1

        total = len(normas)
        print(f"Total: {total} normas")

        if args.limit:
            normas = normas[: args.limit]
            print(f"Limitando a {args.limit}")

        # Procesar tipos en batch
        tipos_unicos = {}
        for n in normas:
            if n["id_tipo"] and n["tipo"]:
                tipos_unicos[n["id_tipo"]] = {
                    "id": n["id_tipo"],
                    "nombre": n["tipo"],
                    "abreviatura": n["abreviatura"],
                }

        if tipos_unicos:
            print(f"\nProcesando {len(tipos_unicos)} tipos...")
            tipos_mgr.add_batch(list(tipos_unicos.values()))

        # Procesar normas
        print("\nDescargando normas...\n")
        stats = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "errores": 0}

        for i, norma_info in enumerate(normas, 1):
            id_norma = norma_info["id"]
            print(f"[{i}/{len(normas)}] Norma {id_norma}... ", end="", flush=True)

            try:
                # Descargar
                xml = client.get_norma_completa(id_norma)
                if not xml:
                    print("✗ Error descarga")
                    stats["errores"] += 1
                    logger.log(id_norma, "descarga", "error", "No se pudo descargar")
                    continue

                # Parsear
                markdown, metadata = parser.parse_from_string(xml)
                parsed_data = {
                    "numero": metadata.numero,
                    "titulo": metadata.titulo,
                    "estado": "derogada" if metadata.derogado else "vigente",
                    "fecha_publicacion": metadata.fecha_publicacion,
                    "fecha_promulgacion": metadata.fecha_promulgacion,
                    "organismo": metadata.organismos[0]
                    if metadata.organismos
                    else None,
                    "materias": metadata.materias,
                    "organismos": metadata.organismos,
                }

                # Guardar
                result = norms_mgr.save(
                    id_norma=id_norma,
                    xml_content=xml,
                    parsed_data=parsed_data,
                    id_tipo=norma_info.get("id_tipo"),
                    id_institucion=args.institucion,
                    markdown=markdown,
                    force=args.force,
                )

                if result == "nueva":
                    stats["nuevas"] += 1
                elif result == "actualizada":
                    stats["actualizadas"] += 1
                elif result == "sin_cambios":
                    stats["sin_cambios"] += 1

                logger.log(id_norma, "sincronizacion", "exitosa")

                print(f"✓ {result}")

            except Exception as e:
                print(f"✗ Error: {e}")
                stats["errores"] += 1
                logger.log(id_norma, "sincronizacion", "error", str(e))

        # Resumen
        print(f"\n{'=' * 60}")
        print("COMPLETADO")
        print(f"{'=' * 60}")
        print(f"Total procesadas: {len(normas)}")
        print(f"\tNuevas:         {stats['nuevas']}")
        print(f"\tActualizadas:   {stats['actualizadas']}")
        print(f"\tSin cambios:    {stats['sin_cambios']}")
        print(f"\tErrores:        {stats['errores']}")
        print(f"{'=' * 60}")

        return 0

    except Exception as e:
        print(f"✗ Error fatal: {e}")
        return 1
    finally:
        client.close()
        norms_mgr.close()


def stats_command(args, managers=None):
    """Muestra estadísticas del sistema"""
    own_connection = managers is None
    if managers is None:
        managers = init_managers()
    if not managers:
        return 1

    norms_mgr = managers["normas"]
    tipos_mgr = managers["tipos"]
    inst_mgr = managers["instituciones"]
    logger = managers["logger"]

    try:
        print(f"\n{'=' * 60}")
        print("ESTADÍSTICAS DEL SISTEMA")
        print(f"{'=' * 60}")

        norms_stats = norms_mgr.get_stats()
        print(f"\nNormas:")
        print(f"  Total:      {norms_stats['total']}")
        print(f"  Vigentes:   {norms_stats['vigentes']}")
        print(f"  Derogadas:  {norms_stats['derogadas']}")

        if norms_stats.get("por_tipo"):
            print(f"\n  Por tipo:")
            for t in norms_stats["por_tipo"]:
                print(f"    {t['tipo']:<30} {t['total']}")

        inst_stats = inst_mgr.get_stats()  # ── FIX: ahora existe ──
        print(f"\nInstituciones:")
        print(f"  Total:       {inst_stats['total']}")
        print(f"  Con normas:  {inst_stats['con_normas']}")
        print(f"  Sin normas:  {inst_stats['sin_normas']}")

        tipos_stats = tipos_mgr.get_all()
        print(f"\nTipos de normas: {len(tipos_stats)}")

        log_stats = logger.get_stats(days=7)
        print(f"\nOperaciones (últimos 7 días):")
        for estado, count in log_stats.items():
            print(f"  {estado:<14} {count}")

        if args.errors:
            errors = logger.get_recent(days=7, estado="error", limit=5)
            if errors:
                print(f"\nErrores recientes:")
                for err in errors:
                    print(f"  Norma {err[0]} — {err[2][:60]}")

        print(f"\n{'=' * 60}")
        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        if own_connection:
            managers["conn"].close()


def search_command(args, managers=None):
    """Busca normas en la base de datos"""
    # Acepta managers externos (util para tests de integracion)
    # Si no se pasan, crea su propia conexion como siempre
    own_connection = managers is None
    norms_mgr = managers["normas"] if managers else NormsManager()

    try:
        print(f"\nBuscando: '{args.query}'...\n")

        results = norms_mgr.search(args.query, limit=args.limit or 20)

        if not results:
            print("\tNo se encontraron resultados")
            return 0

        print(f"\t{len(results)} resultados:\n")

        for i, norma in enumerate(results, 1):
            estado_icon = "🟢" if norma["estado"] == "vigente" else "🔴"
            print(
                f"{i:2d}. {estado_icon} [{norma['norma_id']:6d}] {norma['titulo'][:60]}"
            )
            print(
                f"\tTipo: {norma['tipo_nombre']} ({norma['tipo_id']}) - Numero: {norma['numero']} - Fecha Publicacion: {norma['fecha_publicacion']} - Estado: {norma['estado']}"
            )
            print()

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        if own_connection:
            norms_mgr.close()


def cache_command(args):
    """Gestiona el caché del cliente"""
    client = BCNClient()

    try:
        if args.action == "stats":
            stats = client.get_cache_stats()
            print(f"\nCaché:")
            print(f"\tArchivos:  {stats['total_archivos']}")
            print(f"\tTamaño:    {stats['tamano_total_mb']:.2f} MB")
            print(f"\tDir:       {stats['directorio']}")

        elif args.action == "clear":
            if not args.force:
                resp = input("¿Eliminar caché? (s/N): ")
                if resp.lower() != "s":
                    print("Cancelado")
                    return 0

            client.clear_cache()
            print("✓ Caché eliminado")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="CLI para interactuar con normas de la BCN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python bcn_cli.py init                          # Inicializar DB
  python bcn_cli.py list 17 --limit 10            # Listar normas de institución
  python bcn_cli.py get 206396 --output_md out.md # Descargar norma como Markdown
  python bcn_cli.py sync 17 --limit 5             # Sincronizar institución a DB
  python bcn_cli.py search "medio ambiente"       # Buscar en DB local
  python bcn_cli.py stats                         # Ver estadísticas
  python bcn_cli.py stats --errors                # Ver errores recientes
  python bcn_cli.py cache stats                   # Info del caché
  python bcn_cli.py cache clear                   # Limpiar caché
        """,
    )

    sub = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # init
    p = sub.add_parser(
        "init", help="Inicializar la base de datos y cargar instituciones"
    )
    p.add_argument(
        "--csv", help="Ruta al CSV de instituciones (default: data/instituciones.csv)"
    )
    p.set_defaults(func=init_db)

    # list
    p = sub.add_parser("list", help="Listar normas de una institución (desde BCN)")
    p.add_argument("institucion", type=int, help="ID de la institución")
    p.add_argument("--limit", type=int, help="Máximo de normas a mostrar")
    p.add_argument("--output", "-o", help="Guardar lista como JSON")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=list_normas_command)

    # get
    p = sub.add_parser("get", help="Descargar una norma específica")
    p.add_argument("id", type=int, help="ID de la norma")
    p.add_argument("--output_xml", "-x", help="Guardar XML en ruta")
    p.add_argument("--output_md", "-m", help="Guardar Markdown en ruta")
    p.add_argument("--full", "-f", action="store_true", help="Descargar texto completo")
    p.set_defaults(func=get_norma_command)

    # sync
    p = sub.add_parser("sync", help="Sincronizar normas de una institución a la DB")
    p.add_argument("institucion", type=int, help="ID de la institución")
    p.add_argument("--limit", type=int, help="Máximo de normas a procesar")
    p.add_argument(
        "--force", action="store_true", help="Forzar re-descarga aunque no haya cambios"
    )
    p.set_defaults(func=sync_command)

    # search
    p = sub.add_parser("search", help="Buscar normas en la DB local")
    p.add_argument("query", help="Texto a buscar")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=search_command)

    # stats
    p = sub.add_parser("stats", help="Estadísticas del sistema")
    p.add_argument("--errors", action="store_true", help="Mostrar errores recientes")
    p.set_defaults(func=stats_command)

    # cache
    p = sub.add_parser("cache", help="Gestionar caché local")
    p.add_argument("action", choices=["stats", "clear"])
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cache_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
