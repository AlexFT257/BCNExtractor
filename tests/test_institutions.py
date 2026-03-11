import os
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from managers.institutions import InstitutionManager
from utils.institution_types import Institution

# Cargar variables de entorno
load_dotenv()

inst_manager = InstitutionManager()
test_inst_id = 1041
test_query = "minis"


def test_get_all():
    institutions = inst_manager.get_all()

    assert len(institutions) > 0
    assert isinstance(institutions, List)
    for institution in institutions:
        assert isinstance(institution, Institution)


def test_get_by_id(id: int = test_inst_id):
    inst = inst_manager.get_by_id(id)

    assert inst is None or isinstance(inst, Institution)
    if inst is not None:
        assert inst.id == id


def test_search(query: str = test_query):
    institutions = inst_manager.search(query=query)

    assert len(institutions) > 0
    assert isinstance(institutions, List)
    for inst in institutions:
        assert isinstance(inst, Institution)
        assert inst.nombre.lower().find(query) != -1


def test_stats():
    stats = inst_manager.get_stats()

    assert isinstance(stats, Dict)
    assert stats.get("total", False)
    assert stats.get("con_normas", False)
    assert stats.get("sin_normas", False)
