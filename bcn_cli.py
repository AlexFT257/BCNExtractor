"""
CLI Principal para interactuar con BCN
Orquesta todos los componentes
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from bcn_client import BCNClient
from norm_parser import BCNXMLParser
from norm_manager import NormsManager
from norms_types_manager import TiposNormasManager
from institution_loader import InstitutionLoader
from institution_manager import InstitutionManager
from db_logger import DBLogger


def init_managers():
    """
    Inicializa todos los managers en el orden correcto
    y con una única conexión a base de datos.
    """

    import psycopg2
    import os
    from dotenv import load_dotenv

    load_dotenv()

    conn = psycopg2.connect(
        host='localhost',
        port=os.getenv('POSTGRES_PORT', 5432),
        database=os.getenv('POSTGRES_DB', 'bcn_normas'),
        user=os.getenv('POSTGRES_USER', 'bcn_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme')
    )

    try:
        inst_loader = InstitutionLoader(db_connection=conn)
        inst_loader.ensure_institution_table()
    
        tipos_mgr = TiposNormasManager(db_connection=conn)
    
        norms_mgr = NormsManager(db_connection=conn)
    
        inst_mgr = InstitutionManager(db_connection=conn)
    
        logger = DBLogger(db_connection=conn)
        
        return {
            'conn': conn,
            'instituciones': inst_mgr,
            'instituciones_loader': inst_loader,
            'tipos': tipos_mgr,
            'normas': norms_mgr,
            'logger': logger
        }
    except Exception as e:
        print(f"Error al inicializar el cliente: {e}")
        return None
    
def init_db(args):
    """
    Inicializa únicamente el esquema de la base de datos.
    """

    print("\nInicializando Base de Datos\n")

    managers = init_managers()

    managers['conn'].close()

    print("\nBase de datos inicializada correctamente\n")



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
            normas = normas[:args.limit]
        
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
                json.dumps(normas, indent=2, ensure_ascii=False),
                encoding='utf-8'
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
            print("\n" + "="*60)
            print("Vista previa (primeras 30 líneas)")
            print("="*60)
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
    inst_mgr = managers['instituciones']
    tipos_mgr = managers['tipos']
    norms_mgr = managers['normas']
    logger = managers['logger']
    
    try:
        print(f"\n{'='*60}")
        print(f"SINCRONIZANDO INSTITUCIÓN {args.institucion}")
        print(f"{'='*60}")
        
        # Verificar institución
        inst = inst_mgr.get_by_id(args.institucion)
        if not inst:
            print(f"✗ Institución {args.institucion} no encontrada")
            return 1
        
        print(f"Institución: {inst['nombre']}")
        
        # Obtener lista
        normas = client.get_normas_por_institucion(args.institucion)
        if not normas:
            print("✗ No se pudo obtener lista")
            return 1
        
        total = len(normas)
        print(f"Total: {total} normas")
        
        if args.limit:
            normas = normas[:args.limit]
            print(f"Limitando a {args.limit}")
        
        # Procesar tipos en batch
        tipos_unicos = {}
        for n in normas:
            if n['id_tipo'] and n['tipo']:
                tipos_unicos[n['id_tipo']] = {
                    'id': n['id_tipo'],
                    'nombre': n['tipo'],
                    'abreviatura': n['abreviatura']
                }
        
        if tipos_unicos:
            print(f"\nProcesando {len(tipos_unicos)} tipos...")
            tipos_mgr.add_batch(list(tipos_unicos.values()))
        
        # Procesar normas
        print("\nDescargando normas...\n")
        stats = {'nuevas': 0, 'actualizadas': 0, 'sin_cambios': 0, 'errores': 0}
        
        for i, norma_info in enumerate(normas, 1):
            id_norma = norma_info['id']
            print(f"[{i}/{len(normas)}] Norma {id_norma}... ", end='', flush=True)
            
            try:
                # Descargar
                xml = client.get_norma_completa(id_norma)
                if not xml:
                    print("✗ Error descarga")
                    stats['errores'] += 1
                    logger.log(id_norma, 'descarga', 'error', 'No se pudo descargar')
                    continue
                
                # Parsear
                markdown, metadata = parser.parse_from_string(xml)
                parsed_data = {
                    'numero': metadata.numero,
                    'titulo': metadata.titulo,
                    'estado': 'derogada' if metadata.derogado else 'vigente',
                    'fecha_publicacion': metadata.fecha_publicacion,
                    'fecha_promulgacion': metadata.fecha_promulgacion,
                    'organismo': metadata.organismos[0] if metadata.organismos else None,
                    'materias': metadata.materias,
                    'organismos': metadata.organismos
                }
                
                # Guardar
                result = norms_mgr.save(
                    id_norma=id_norma,
                    xml_content=xml,
                    parsed_data=parsed_data,
                    id_tipo=norma_info.get('id_tipo'),
                    id_institucion=args.institucion,
                    markdown=markdown,
                    force=args.force
                )
                
                if result == 'nueva':
                    stats['nuevas'] += 1
                elif result == 'actualizada':
                    stats['actualizadas'] += 1
                elif result == 'sin_cambios':
                    stats['sin_cambios'] += 1

                logger.log(id_norma, 'sincronizacion', 'exitosa')
                
                print(f"✓ {result}")
                
            except Exception as e:
                print(f"✗ Error: {e}")
                stats['errores'] += 1
                logger.log(id_norma, 'sincronizacion', 'error', str(e))
        
        # Resumen
        print(f"\n{'='*60}")
        print("COMPLETADO")
        print(f"{'='*60}")
        print(f"Total procesadas: {len(normas)}")
        print(f"\tNuevas:         {stats['nuevas']}")
        print(f"\tActualizadas:   {stats['actualizadas']}")
        print(f"\tSin cambios:    {stats['sin_cambios']}")
        print(f"\tErrores:        {stats['errores']}")
        print(f"{'='*60}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error fatal: {e}")
        return 1
    finally:
        client.close()
        norms_mgr.close()


def stats_command(args):
    """Muestra estadísticas del sistema"""
    norms_mgr = NormsManager()
    tipos_mgr = TiposNormasManager(db_connection=norms_mgr.conn)
    inst_manager = InstitutionManager(db_connection=norms_mgr.conn)
    logger = DBLogger(db_connection=norms_mgr.conn)
    
    try:
        print(f"\n{'='*60}")
        print("ESTADÍSTICAS DEL SISTEMA")
        print(f"{'='*60}")
        
        # Normas
        norms_stats = norms_mgr.get_stats()
        print(f"\nNormas:")
        print(f"\tTotal:      {norms_stats['total']}")
        print(f"\tVigentes:   {norms_stats['vigentes']}")
        print(f"\tDerogadas:  {norms_stats['derogadas']}")
        
        # Instituciones
        # inst_stats = inst_manager.get_stats()
        # print(f"\nInstituciones:")
        # print(f"\tTotal:      {inst_stats['total']}")
        
        # Tipos
        tipos_stats = tipos_mgr.get_all()
        print(f"\nTipos de normas:")
        print(f"\tTotal:      {len(tipos_stats)}")
        
        # Logs
        log_stats = logger.get_stats(days=7)
        print(f"\nOperaciones (últimos 7 días):")
        for estado, count in log_stats.items():
            print(f"\t{estado:12s}: {count}")
        
        # Errores recientes
        if args.errors:
            errors = logger.get_recent_errors(limit=5)
            if errors:
                print(f"\n\tErrores recientes:")
                for err in errors:
                    print(f"\tNorma {err[0]} - {err[2][:50]}")
        
        print(f"\n{'='*60}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        norms_mgr.close()


def search_command(args):
    """Busca normas en la base de datos"""
    norms_mgr = NormsManager()
    
    try:
        print(f"\nBuscando: '{args.query}'...\n")
        
        results = norms_mgr.search(args.query, limit=args.limit or 20)
        
        if not results:
            print("\tNo se encontraron resultados")
            return 0
        
        print(f"\t{len(results)} resultados:\n")
        
        for i, norma in enumerate(results, 1):
            estado_icon = "🟢" if norma['estado'] == 'vigente' else "🔴"
            print(f"{i:2d}. {estado_icon} [{norma['id']:6d}] {norma['titulo'][:60]}")
            print(f"\t{norma['numero']} - {norma['fecha_publicacion']}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        norms_mgr.close()


def cache_command(args):
    """Gestiona el caché del cliente"""
    client = BCNClient()
    
    try:
        if args.action == 'stats':
            stats = client.get_cache_stats()
            print(f"\nCaché:")
            print(f"\tArchivos:  {stats['total_archivos']}")
            print(f"\tTamaño:    {stats['tamano_total_mb']:.2f} MB")
            print(f"\tDir:       {stats['directorio']}")
        
        elif args.action == 'clear':
            if not args.force:
                resp = input("¿Eliminar caché? (s/N): ")
                if resp.lower() != 's':
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
        description='CLI para interactuar con normas de la BCN',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Ejemplos de uso:
        
          # Inicializar el esquema de la base de datos (Recomendado antes de cualquier otra operación)
          python bcn_cli.py init
        
          # Listar normas de una institución desde la BCN
          python bcn_cli.py list 17 --limit 10
        
          # Descargar una norma específica
          python bcn_cli.py get 206396 --output_md ./norma.md
        
          # Sincronizar normas de una institución en la base de datos
          python bcn_cli.py sync 17 --limit 5
        
          # Buscar normas almacenadas localmente
          python bcn_cli.py search "medio ambiente"
        
          # Ver estadísticas del sistema
          python bcn_cli.py stats
        
          # Mostrar errores recientes
          python bcn_cli.py stats --errors
        
          # Consultar información del caché
          python bcn_cli.py cache stats
        
          # Limpiar caché local
          python bcn_cli.py cache clear
        """

    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comando a ejecutar')
    
    # init
    init_parser = subparsers.add_parser('init', help='Inicializar la base de datos')
    init_parser.set_defaults(func=init_db)
    
    # list
    list_parser = subparsers.add_parser('list', help='Listar normas')
    list_parser.add_argument('institucion', type=int)
    list_parser.add_argument('--limit', type=int)
    list_parser.add_argument('--output', '-o')
    list_parser.add_argument('--verbose', '-v', action='store_true')
    list_parser.set_defaults(func=list_normas_command)
    
    # get
    get_parser = subparsers.add_parser('get', help='Descargar norma')
    get_parser.add_argument('id', type=int)
    get_parser.add_argument('--output_xml', '-x')
    get_parser.add_argument('--output_md', '-m')
    get_parser.add_argument('--full', '-f', action='store_true')
    get_parser.set_defaults(func=get_norma_command)
    
    # sync
    sync_parser = subparsers.add_parser('sync', help='Sincronizar a DB')
    sync_parser.add_argument('institucion', type=int)
    sync_parser.add_argument('--limit', type=int)
    sync_parser.add_argument('--force', action='store_true')
    sync_parser.set_defaults(func=sync_command)
    
    # search
    search_parser = subparsers.add_parser('search', help='Buscar normas')
    search_parser.add_argument('query')
    search_parser.add_argument('--limit', type=int)
    search_parser.set_defaults(func=search_command)
    
    # stats
    stats_parser = subparsers.add_parser('stats', help='Estadísticas')
    stats_parser.add_argument('--errors', action='store_true')
    stats_parser.set_defaults(func=stats_command)
    
    # cache
    cache_parser = subparsers.add_parser('cache', help='Gestionar caché')
    cache_parser.add_argument('action', choices=['stats', 'clear'])
    cache_parser.add_argument('--force', action='store_true')
    cache_parser.set_defaults(func=cache_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())