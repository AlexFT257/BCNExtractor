import argparse
import sys
from pathlib import Path
from bcn_client import BCNClient
import json

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
            normas = normas[:args.limit]
        
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
        
def main():
    parser = argparse.ArgumentParser(
        description='Descarga normas desde la BCN',
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
            python bcn_cli.py get 206396 --output norma.xml
            
            # Ver estadísticas de caché
            python bcn_cli.py cache stats
            
            # Limpiar caché
            python bcn_cli.py cache clear
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comando a ejecutar')
    
    # Comando: list
    list_parser = subparsers.add_parser('list', help='Listar normas de una institución')
    list_parser.add_argument('institucion', type=int, help='ID de la institución')
    list_parser.add_argument('--limit', type=int, help='Limitar número de resultados')
    list_parser.add_argument('--output', '-o', help='Guardar lista como JSON')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar más detalles')
    list_parser.set_defaults(func=list_normas_command)
    
    args = parser.parse_args()
    
    return list_normas_command(args)

if __name__ == "__main__":
    sys.exit(main())