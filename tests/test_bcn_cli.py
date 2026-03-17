from typer.testing import CliRunner

from bcn_cli import app

runner = CliRunner()

TEST_INST_ID = "1041"
TEST_NORM_ID = "271391"
TEST_QUERY = "minis"

def test_init_managers():
    from cli._internal import init_managers

    managers = init_managers()
    assert managers is not None
    assert isinstance(managers, dict)
    assert managers.get("conn") is not None
    assert managers.get("instituciones") is not None
    assert managers.get("instituciones_loader") is not None
    assert managers.get("tipos") is not None
    assert managers.get("normas") is not None
    assert managers.get("logger") is not None
    managers["conn"].close()

def test_init_db():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

def test_list_normas_fail():
    # Institución 0 no existe en la BCN — debe terminar con error
    result = runner.invoke(app, ["normas", "list", "0"])
    assert result.exit_code != 0

def test_list_normas_success():
    result = runner.invoke(app, ["normas", "list", TEST_INST_ID])
    assert result.exit_code == 0

def test_get_norma_fail():
    # ID negativo no existe — debe terminar con error
    result = runner.invoke(app, ["normas", "get", "-1"])
    assert result.exit_code != 0

def test_get_norma_success():
    result = runner.invoke(app, ["normas", "get", TEST_NORM_ID, "--full"])
    assert result.exit_code == 0

def test_search():
    result = runner.invoke(app, ["normas", "search", TEST_QUERY])
    assert result.exit_code == 0

def test_stats():
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0


def test_stats_errors():
    result = runner.invoke(app, ["stats", "--errors"])
    assert result.exit_code == 0