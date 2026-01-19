import argparse
from ast import arg
import json
import sys
from pathlib import Path

from bcn_client import BCNClient
from norm_parser import BCNXMLParser, NormaMetadata


def list_normas_command(args):
    client = BCNClient()

    try:
        print(f"Consultando normas de la institucion {args.institucion}")

        normas = client.get_normas_por_institucion(args.institucion)

        if not normas:
            print("\tNo se encontraron normas para la institucion especificada.")
            return 1

        print(f"\n{len(normas)} normas encontradas.")

        if args.limit:
            normas = normas[: args.limit]

        for norma in normas:
            print(f"Norma {norma['id']} - {norma['titulo']}")
            print(f"Tipo: {norma['tipo']}")
            print(f"ID Tipo: {norma['id_tipo']}")
            print(f"Numero: {norma['numero']}")
            print(f"Abreviatura: {norma['abreviatura']}")
            print(f"Materia: {norma['materia']}")
            print(f"Fecha de promulgacion: {norma['fecha_promulgacion']}")
            print(f"Fecha de publicacion: {norma['fecha_publicacion']}")
            print(f"Organismos: {norma['organismos']}")
            print(f"URL: {norma['url']}")
            print()

        return 0

    except Exception as e:
        print(f"Error al consultar las normas: {e}")
        return 1

    finally:
        client.close()


def get_norma_command(args):
    client = BCNClient()

    try:
        print(f"\nDescargando norma {args.id}...")

        if args.full:
            xml = client.get_norma_completa(args.id)
        else:
            xml = client.get_norma_metadatos(args.id)
            

        if not xml:
            print(f"\tNorma {args.id} no encontrada")
            return 1

        if args.output_md:
            parser = BCNXMLParser()
            markdown, metadata = parser.parse_from_string(xml)
            output_path = Path(args.output_md)
            output_path.write_text(markdown, encoding="utf-8")
            print(f"\tNorma {args.id} guardada en {output_path}")

        elif args.output_xml:
            output_path = Path(args.output)
            output_path.write_text(xml, encoding="utf-8")
            print(f"\tNorma {args.id} guardada en {args.output}")

        else:
            lines = xml.split("\n")[:40]
            print("\n" + "-" * 20 + "Vista previa" + "-" * 20)
            for line in lines:
                print(line)
            print("-" * 60)

        return 0

    except Exception as e:
        print(f"\tError al guardar la norma {args.id}: {e}")
        return 1

    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Descarga normas desde la BCN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Ejemplos de uso:

            # Listar normas de una institución
            python bcn_cli.py list 1041 --limit 10

            # Descargar todas las normas (solo metadatos)
            python bcn_cli.py download 1041 --output-dir data/normas

            # Descargar primeras 10 normas (XML completo)
            python bcn_cli.py download 1041 --full --limit 10

            # Descargar una norma específica
            python bcn_cli.py get 206396 --output_xml ./data/xml/norma.xml

            # Descargar una norma específica en markdown
            python bcn_cli.py get 206396 --output_md ./data/md/norma.md

            # Ver estadísticas de caché
            python bcn_cli.py cache stats

            # Limpiar caché
            python bcn_cli.py cache clear
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Comando: list
    list_parser = subparsers.add_parser("list", help="Listar normas de una institución")
    list_parser.add_argument("institucion", type=int, help="ID de la institución")
    list_parser.add_argument("--limit", type=int, help="Limitar número de resultados")
    list_parser.add_argument("--output", "-o", help="Guardar lista como JSON")
    list_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Mostrar más detalles"
    )
    list_parser.set_defaults(func=list_normas_command)

    # Comando: get
    get_parser = subparsers.add_parser("get", help="Descargar una norma específica")
    get_parser.add_argument("id", type=int, help="ID de la norma")
    get_parser.add_argument("--output_xml", "-o", help="Archivo de salida en xml")
    get_parser.add_argument("--output_md", "-m", help="Archivo de salida en markdown")
    get_parser.add_argument(
        "--full",
        "-f",
        action="store_true",
        help="Descargar XML completo (default: solo metadatos)",
    )
    get_parser.set_defaults(func=get_norma_command)

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
