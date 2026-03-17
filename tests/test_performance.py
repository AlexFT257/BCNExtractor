import pytest

from bcn_client import BCNClient
from managers.norms import NormsManager
from utils.norm_parser import BCNXMLParser

# ==================== FIXTURES ====================


@pytest.fixture(scope="module")
def client():
    """Cliente BCN reutilizable"""
    client = BCNClient()
    yield client
    client.close()


@pytest.fixture(scope="module")
def parser():
    """Parser reutilizable"""
    return BCNXMLParser()


@pytest.fixture(scope="module")
def norms_manager():
    """Manager de normas reutilizable"""
    manager = NormsManager()
    yield manager
    manager.close()


@pytest.fixture(scope="module")
def sample_xml(client):
    """XML de muestra para tests de parsing"""
    xml = client.get_norma_completa(12)  # Ajusta este ID
    return xml


# ==================== BENCHMARKS ====================


def test_benchmark_api_list_normas(benchmark, client):
    """Benchmark: Listar normas de institución"""
    result = benchmark(client.get_normas_por_institucion, 17)
    assert result is not None
    assert len(result) > 0


def test_benchmark_api_download_full(benchmark, client):
    """Benchmark: Descargar norma completa"""
    result = benchmark(client.get_norma_completa, 12)
    assert result is not None


def test_benchmark_api_download_metadata(benchmark, client):
    """Benchmark: Descargar solo metadatos"""
    result = benchmark(client.get_norma_metadatos, 12)
    assert result is not None


def test_benchmark_parse_xml(benchmark, parser, sample_xml):
    """Benchmark: Parsear XML a Markdown"""
    if not sample_xml:
        pytest.skip("No hay XML de muestra")

    markdown, metadata = benchmark(parser.parse_from_string, sample_xml)
    assert markdown is not None
    assert metadata is not None


def test_benchmark_db_search(benchmark, norms_manager):
    """Benchmark: Búsqueda full-text"""
    results = benchmark(norms_manager.search, "medio ambiente", limit=20)
    assert isinstance(results, list)


def test_benchmark_db_get_stats(benchmark, norms_manager):
    """Benchmark: Obtener estadísticas"""
    stats = benchmark(norms_manager.get_stats)
    assert stats is not None
    assert "total" in stats


def test_benchmark_db_get_norm(benchmark, norms_manager):
    """Benchmark: Obtener norma por ID"""
    # Ajusta este ID por uno que exista en tu DB
    result = benchmark(norms_manager.get_by_id, 12)
