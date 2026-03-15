import argparse

import bcn_cli

test_inst_id = 1041
test_norm_id = 271391
test_query = "minis"


def make_args(**kwargs):
    defaults = {
        "institucion": test_inst_id,
        "limit": None,
        "verbose": False,
        "force": False,
        "output": None,
        "id": test_norm_id,
        "full": True,
        "output_md": None,
        "output_xml": None,
        "query": test_query,
        "errors": False,
        "csv": None,
        "action": "stats",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_init_managers():
    managers = bcn_cli.init_managers()

    assert managers is not None
    assert isinstance(managers, dict)
    assert managers.get("conn") is not None
    assert managers.get("instituciones") is not None
    assert managers.get("instituciones_loader") is not None
    assert managers.get("tipos") is not None
    assert managers.get("normas") is not None
    assert managers.get("logger") is not None


def test_init_db():
    response = bcn_cli.init_db()
    assert response == 0


def test_list_normas_fail():
    # Sin institución válida (None) debe retornar 1
    response = bcn_cli.list_normas_command(make_args(institucion=0))
    assert response == 1


def test_list_normas_success():
    response = bcn_cli.list_normas_command(make_args(institucion=test_inst_id))
    assert response == 0


def test_get_norma_fail():
    # ID inexistente debe retornar 1
    response = bcn_cli.get_norma_command(make_args(id=-1))
    assert response == 1


def test_get_norma_success():
    response = bcn_cli.get_norma_command(make_args(id=test_norm_id))
    assert response == 0


def test_stats():
    response = bcn_cli.stats_command(make_args())
    assert response == 0


def test_search():
    response = bcn_cli.search_command(make_args(query=test_query))
    assert response == 0
