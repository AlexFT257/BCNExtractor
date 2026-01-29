from typing import Dict, List, Optional, Union
from fastapi import FastAPI
from bcn_client import BCNClient
from utils.norm_parser import BCNXMLParser
from utils.db_logger import DBLogger
from managers.norms import NormsManager
from managers.institutions import InstitutionManager
from managers.norms_types import TiposNormasManager

from utils.norm_types import Norm, NormResponse

app = FastAPI()
client = BCNClient()
parser = BCNXMLParser()
norm_manager = NormsManager()
institution_manager = InstitutionManager()
tipos_normas_manager = TiposNormasManager()
logger = DBLogger()


        
@app.get("/normas/{norma_id}")
def get_norma(norma_id: int):
    norma = client.get_norma_completa(norma_id)
    if not norma:
        return {"error": "Norma no encontrada"}
        
    markdown, norm_data = parser.parse_from_string(norma)
    
    return NormResponse(
        norma=norm_data,
        markdown=markdown
    )

@app.post("/normas")
def get_normas_batch(normas_id:list[int]):
    if not normas_id:
        return {"error": "No se proporcionaron IDs de normas"}
        
    normas = []
    for norma_id in normas_id:
        norma = client.get_norma_completa(norma_id)
        if not norma:
            return {"error": f"Norma {norma_id} no encontrada"}
        
        markdown, norm_data = parser.parse_from_string(norma)
        normas.append({
            "norma": norm_data,
            "markdown": markdown
        })
        
    return normas

@app.get("/normas/buscar/{query}")
def search_normas(query: str, limit: int | None = 10):
    try:
        results = norm_manager.search(query, limit=limit or 10)
        
        if not results:
            return {"error": "No se encontraron resultados"}
            
        return {"normas": results}
    except Exception as e:
        return {"error": str(e)}

@app.get("/institucion/{institucion_id}")
def get_institucion(institucion_id: int):
    institucion = institution_manager.get_by_id(institucion_id)
    if not institucion:
        return {"error": "Institucion no encontrada"}
        
    return institucion

@app.get("/instituciones")
def get_instituciones():
    instituciones = institution_manager.get_all()
    if not instituciones:
        return {"error": "No se encontraron instituciones"}
        
    return instituciones

@app.get("/instituciones/{institucion_id}/normas")
def get_normas_por_institucion(institucion_id: int, limit: int | None = None):
    institucion = institution_manager.get_by_id(institucion_id)
    if not institucion:
        return {"error": "Institucion no encontrada"}
        
    normas = client.get_normas_por_institucion(institucion_id)
    if not normas:
        return {"error": "No se encontraron normas para esta institucion"}
        
    if limit:
        normas = normas[:limit]
        
    return normas

@app.put("/instituciones/{institucion_id}/normas")
def update_normas_por_institucion(institucion_id: int, limit: int | None = None):
    """Actualiza la información de todas las normas de una institución en la base de datos."""
    institucion = institution_manager.get_by_id(institucion_id)
    if not institucion:
        return {"error": "Institucion no encontrada"}
        
    normas = client.get_normas_por_institucion(institucion_id)
    if not normas:
        return {"error": "No se encontraron normas para esta institucion"}
        
    if limit:
        normas = normas[:limit]
        
    tipos_unicos = {}
    for n in normas:
        if n['id_tipo'] and n['tipo']:
            tipos_unicos[n['id_tipo']] = {
                'id': n['id_tipo'],
                'nombre': n['tipo'],
                'abreviatura': n['abreviatura']
            }
    
    if tipos_unicos:
        tipos_normas_manager.add_batch(list(tipos_unicos.values()))
    
    stats = {'nuevas': 0, 'actualizadas': 0, 'sin_cambios': 0, 'errores': 0}
    for norma in normas:
        try:
            xml = client.get_norma_completa(norma['id'])
            if not xml:
                continue
            
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
            result = norm_manager.save(
                id_norma=norma['id'],
                xml_content=xml,
                parsed_data=parsed_data,
                id_tipo=norma.get('id_tipo'),
                id_institucion=institucion_id,
                markdown=markdown,
            )
            
            if result == 'nueva':
                stats['nuevas'] += 1
            elif result == 'actualizada':
                stats['actualizadas'] += 1
            elif result == 'sin_cambios':
                stats['sin_cambios'] += 1
                
            logger.log(norma['id'], 'sincronizacion', 'exitosa')
        except Exception as e:
            stats['errores'] += 1
            logger.log(norma['id'], 'sincronizacion', 'error', str(e))
    
    return stats