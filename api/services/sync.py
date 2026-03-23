from api.dependencies import (
    get_client, get_parser, get_norm_manager,
    get_tipos_manager, get_download_logger
)


def sync_normas_institucion(normas: list, institucion_id: int) -> dict:
    client = get_client()
    parser = get_parser()
    norm_manager = get_norm_manager()
    tipos_manager = get_tipos_manager()
    logger = get_download_logger()

    tipos_unicos = {
        n["id_tipo"]: {"id": n["id_tipo"], "nombre": n["tipo"], "abreviatura": n["abreviatura"]}
        for n in normas if n["id_tipo"] and n["tipo"]
    }
    if tipos_unicos:
        tipos_manager.add_batch(list(tipos_unicos.values()))

    stats = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "errores": 0}
    for norma in normas:
        try:
            xml = client.get_norma_completa(norma["id"])
            if not xml:
                continue
            markdown, metadata = parser.parse_from_string(xml)
            parsed_data = {
                "numero": metadata.numero,
                "titulo": metadata.titulo,
                "estado": "derogada" if metadata.derogado else "vigente",
                "fecha_publicacion": metadata.fecha_publicacion,
                "fecha_promulgacion": metadata.fecha_promulgacion,
                "organismo": metadata.organismos[0] if metadata.organismos else None,
                "materias": metadata.materias,
                "organismos": metadata.organismos,
            }
            result = norm_manager.save(
                id_norma=norma["id"],
                xml_content=xml,
                parsed_data=parsed_data,
                id_tipo=norma.get("id_tipo"),
                id_institucion=institucion_id,
                markdown=markdown,
            )
            stats[result] = stats.get(result, 0) + 1
            logger.log(norma["id"], "sincronizacion", "exitosa")
        except Exception as e:
            stats["errores"] += 1
            logger.log(norma["id"], "sincronizacion", "error", str(e))

    return stats