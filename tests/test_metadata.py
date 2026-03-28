from typing import Dict, List

from dotenv import load_dotenv

from managers.metadata import MetadataManager

load_dotenv()

metadata_manager = MetadataManager()
test_norm_id = 271391
test_clave = "materia"
test_valor = "medio"


def test_get_by_norma(id_norma: int = test_norm_id):
    result = metadata_manager.get_by_norma(id_norma)

    assert isinstance(result, Dict)


def test_get_by_norma_clave(id_norma: int = test_norm_id, clave: str = test_clave):
    result = metadata_manager.get_by_norma_clave(id_norma, clave)

    assert isinstance(result, List)


def test_get_normas_by_clave_valor(
    clave: str = test_clave, valor: str = test_valor, limit: int = 4, offset: int = 4
):
    results = metadata_manager.get_normas_by_clave_valor(
        clave=clave, valor=valor, limit=limit
    )

    assert isinstance(results, List)
    assert len(results) > 0
    for norma in results:
        assert norma.get("norma_id")
        assert norma.get("titulo")

    results2 = metadata_manager.get_normas_by_clave_valor(
        clave=clave, valor=valor, limit=limit, offset=offset
    )
    assert isinstance(results2, List)
    assert len(results2) > 0

    last_id = results[-1].get("norma_id")
    last_id2 = results2[-1].get("norma_id")
    assert last_id != last_id2


def test_get_claves_disponibles():
    result = metadata_manager.get_claves_disponibles()

    assert isinstance(result, List)
    assert len(result) > 0
    for clave in result:
        assert isinstance(clave, str)


def test_get_stats():
    stats = metadata_manager.get_stats()

    assert isinstance(stats, Dict)
    assert stats.get("total_entradas")
    assert stats.get("normas_con_metadata")
    assert isinstance(stats.get("por_clave"), List)
    assert len(stats.get("por_clave")) > 0
