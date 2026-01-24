import argparse
import sys

from loaders.institutions import InstitutionLoader
from managers.institutions import InstitutionManager


def load_command(args):
    loader = InstitutionLoader()

    try:
        stats = loader.load_from_csv(csv_path=args.file, mode=args.mode)

        print("\n" + "-" * 50)
        print("Resumen de carga de instituciones")
        print(f"\tTotal de instituciones cargadas: {stats['total']}")
        print(f"\tInstituciones cargadas con éxito: {stats['success']}")
        print(f"\tInstituciones con errores: {stats['errors']}")
        print("-" * 50)

        return 0 if stats["errors"] == 0 else 1

    except Exception as e:
        print(f"Error al cargar las instituciones: {e}", file=sys.stderr)
        return 1

    finally:
        loader.close()


def list_command(args):
    manager = InstitutionManager()

    try:
        print("\n" + "-" * 50)
        if args.search:
            instituciones = manager.search(args.search)
            print(f"\nResultados de busqueda:{args.search}")
        else:
            instituciones = manager.get_all()
            print(f"\nLista de instituciones:")

        if not instituciones:
            print("\tNo se encontraron instituciones.")
            return 0

        if args.limit:
            instituciones = instituciones[: args.limit]

        print(f"\tTotal:{len(instituciones)}")

        for institucion in instituciones:
            print(f"\t{institucion['id']} - {institucion['nombre']}")

        print("\n" + "-" * 50)

        return 0

    except Exception as e:
        print(f"Error al listar las instituciones: {e}", file=sys.stderr)
        return 1

    finally:
        manager.close()


def get_command(args):
    manager = InstitutionManager()

    try:
        institucion = manager.get_by_id(args.id)

        print("\n" + "-" * 50)

        if not institucion:
            print(f"Institución con ID {args.id} no encontrada.")
            print("\n" + "-" * 50)
            return 1

        print("Institución:")
        print(f"\tID: {institucion['id']}")
        print(f"\tNombre: {institucion['nombre']}")
        print("\n" + "-" * 50)

        return 0

    except Exception as e:
        print(f"Error al obtener la institución: {e}", file=sys.stderr)
        return 1

    finally:
        manager.close()


def main():
    parser = argparse.ArgumentParser(
        description="Gestión de instituciones",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Cargar instituciones desde CSV (actualiza existentes)
  python institution_cli.py load data/instituciones.csv

  # Reemplazar todas las instituciones
  python institution_cli.py load data/instituciones.csv --mode replace

  # Solo agregar nuevas (ignora duplicados)
  python institution_cli.py load data/instituciones.csv --mode append

  # Listar todas las instituciones
  python institution_cli.py list

  # Buscar instituciones
  python institution_cli.py list --search ministerio

  # Ver detalles de una institución
  python institution_cli.py get 1041
        """,
    )

    subparser = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Cargar
    load_parser = subparser.add_parser("load", help="Cargar instituciones desde CSV")
    load_parser.add_argument("file", help="Archivo CSV con datos de instituciones")
    load_parser.add_argument(
        "--mode",
        choices=["update", "replace", "append"],
        default="update",
        help="Modo de carga (default: update)",
    )
    load_parser.set_defaults(func=load_command)

    # Listar
    list_parser = subparser.add_parser("list", help="Listar instituciones")
    list_parser.add_argument(
        "--search",
        help="Buscar instituciones por nombre",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        help="Número máximo de resultados",
    )
    list_parser.set_defaults(func=list_command)

    # Detalles
    get_parser = subparser.add_parser("get", help="Ver detalles de una institución")
    get_parser.add_argument("id", type=int, help="ID de la institución")
    get_parser.set_defaults(func=get_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
