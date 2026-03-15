import argparse

import institution_cli

test_inst_id = 1041
test_norm_id = 271391
test_query = "minis"


def make_args(**kwargs):
    defaults = {
        "id": test_inst_id,
        "limit": None,
        "verbose": False,
        "force": False,
        "output": None,
        "full": True,
        "query": test_query,
        "errors": False,
        "csv": None,
        "action": "stats",
        "search": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_list_get_all():
    result = institution_cli.list_command(make_args())
    assert result == 0


def test_list_search():
    result = institution_cli.list_command(make_args(search=test_query))
    assert result == 0


def test_get():
    result = institution_cli.get_command(make_args())
    assert result == 0
