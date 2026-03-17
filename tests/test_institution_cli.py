from typer.testing import CliRunner

from bcn_cli import app

runner = CliRunner()

TEST_INST_ID = "1041"
TEST_QUERY = "minis"


def test_list_get_all():
    result = runner.invoke(app, ["instituciones", "list"])
    assert result.exit_code == 0


def test_list_search():
    result = runner.invoke(app, ["instituciones", "list", "--search", TEST_QUERY])
    assert result.exit_code == 0


def test_get():
    result = runner.invoke(app, ["instituciones", "get", TEST_INST_ID])
    assert result.exit_code == 0


def test_get_not_found():
    # ID inexistente debe terminar con error
    result = runner.invoke(app, ["instituciones", "get", "0"])
    assert result.exit_code != 0