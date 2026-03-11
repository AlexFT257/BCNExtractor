import os
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from managers.norms import NormsManager
from utils.norm_types import Norm

# Cargar variables de entorno
load_dotenv()

norm_manager = NormsManager()
test_inst_id = 1041
test_norm_id = 271391
test_query = "minis"


def test_get_by_id(id: int = test_norm_id):
    norm = norm_manager.get_by_id(id)
    # print(norm)

    assert norm is None or isinstance(norm, Dict)
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


def test_search(query: str = test_query, limit: int = 10):
    results = norm_manager.search(query=query, limit=limit)

    assert len(results) > 0
    for norm in results:
        assert norm.get("norma_id")
        assert norm.get("tipo_nombre")


def test_get_stats():
    stats = norm_manager.get_stats()

    assert stats.get("total")
    assert stats.get("vigentes")
    assert stats.get("derogadas")
