from datetime import date
from typing import Dict, List, Optional

from dotenv import load_dotenv

from managers.norms import NormsManager
from utils.norm_types import Norm

# Cargar variables de entorno
load_dotenv()

norm_manager = NormsManager()
test_inst_id = 1041
test_norm_id = 271391
test_query = "minis"
test_date_start = date(2000, 1, 1)
test_date_end = date(2010, 1, 1)
test_id_version = 1


def test_get_by_id(id: int = test_norm_id):
    norm = norm_manager.get_by_id(id)
    # print(norm)

    assert isinstance(norm, Dict)
    if isinstance(norm, Dict):
        assert norm.get("id") == id


def test_get_by_instituciones(id_institucion: int = test_inst_id, limit: int = 100):
    results = norm_manager.get_by_institucion(
        id_institucion=id_institucion, limit=limit
    )

    assert isinstance(results, List)
    assert len(results) > 0
    for norm in results:
        assert norm.get("id")


def test_search(query: str = test_query, limit: int = 10, offset: int = 10):
    results = norm_manager.search(query=query, limit=limit)

    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")

    results = norm_manager.search(query=query, limit=limit, offset=offset)
    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_by_pub_date_range(
    start_date: date = test_date_start, end_date: date = test_date_end
):
    results = norm_manager.get_by_range_date(
        start_date=start_date, end_date=end_date, date_type="pub"
    )

    assert isinstance(results, List)
    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_by_prom_date_range(
    start_date: date = test_date_start, end_date: date = test_date_end
):
    results = norm_manager.get_by_range_date(
        start_date=start_date, end_date=end_date, date_type="prom"
    )

    assert isinstance(results, List)
    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_by_status(status: str = "vigente", limit: int = 50, offset: int = 0):
    results = norm_manager.get_by_status(status=status, limit=limit, offset=offset)

    assert isinstance(results, List)
    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_by_type(type: str = "ley", limit: int = 50, offset: int = 0):
    results = norm_manager.get_by_type(type=type, limit=limit, offset=offset)

    assert isinstance(results, List)
    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_all(limit: int = 50, offset: int = 50):
    results = norm_manager.get_all(limit=limit)

    assert isinstance(results, List)
    assert len(results) > 0
    last_id = None
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")
        last_id = norm.get("norma_id")

    # get last id from the first batch
    assert last_id

    results = norm_manager.get_all(limit=limit, offset=offset)
    assert isinstance(results, List)
    assert len(results) > 0
    second_last_id = None
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")
        second_last_id = norm.get("norma_id")

    # check that the second batch has a different last id than the first batch
    assert second_last_id
    assert second_last_id != last_id


def test_get_stats():
    stats = norm_manager.get_stats()

    assert stats.get("total")
    assert stats.get("vigentes")
    assert stats.get("derogadas")


def test_get_versiones(id_norma: int = test_norm_id):
    versions = norm_manager.get_versiones(id_norma=id_norma)

    assert isinstance(versions, List)
    assert len(versions) > 0
    for version in versions:
        assert version.get("version_num")
        assert version.get("hash_xml")
        assert version.get("detectado_en")


def test_get_version(id_norma: int = test_norm_id, version_num: int = test_id_version):
    version = norm_manager.get_version(id_norma=id_norma, version_num=version_num)

    assert version
    assert version.get("version_num")
    assert version.get("hash_xml")
    assert version.get("detectado_en")
