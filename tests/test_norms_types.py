import os
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from managers.norms_types import TiposNormasManager

# Cargar variables de entorno
load_dotenv()

types_manager = TiposNormasManager()
test_inst_id = 1041
test_norm_id = 271391
test_query = "minis"
test_type_id = 1
test_type_name = "ley"


def test_get_by_id(id: int = test_type_id):
    type = types_manager.get_by_id(id)

    assert type is not None
    assert type.get("id") == id


def test_get_by_name(name: str = test_type_name):
    type = types_manager.get_by_name(name)

    assert type is not None
    assert type.get("id")
    assert type.get("nombre") is not None


def test_get_all():
    results = types_manager.get_all()

    assert len(results) > 0
    assert results is not None
    for type in results:
        assert type.get("id") is not None
        assert type.get("nombre") is not None
