"""
Tests de integración para BCNExtractor API.
Requieren PostgreSQL corriendo con datos de prueba.

Uso:
    pytest tests/test_api.py -v
    pytest tests/test_api.py -v -k "normas"   # solo tests de normas
    pytest tests/test_api.py -v -k "instituciones"
"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

NORMA_ID_EXISTENTE = 12  # ID de una norma que existe en la DB
NORMA_ID_INEXISTENTE = 9999999  # ID que no existe
INSTITUCION_ID_EXISTENTE = 17  # ID de institución con normas
INSTITUCION_ID_INEXISTENTE = 9999  # ID que no existe


# /normas


class TestGetNorma:
    def test_retorna_norma_existente(self):
        response = client.get(f"/normas/{NORMA_ID_EXISTENTE}")
        assert response.status_code == 200
        data = response.json()
        assert "norma" in data
        assert "markdown" in data

    def test_retorna_404_si_no_existe(self):
        response = client.get(f"/normas/{NORMA_ID_INEXISTENTE}")
        assert response.status_code == 404

    def test_id_invalido_retorna_422(self):
        response = client.get("/normas/no-es-un-id")
        assert response.status_code == 422


class TestGetNormasBatch:
    def test_retorna_lista_de_normas(self):
        response = client.post("/normas/batch", json=[NORMA_ID_EXISTENTE])
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "norma" in data[0]
        assert "markdown" in data[0]

    def test_lista_vacia_retorna_400(self):
        response = client.post("/normas/batch", json=[])
        assert response.status_code == 400

    def test_id_inexistente_retorna_404(self):
        response = client.post("/normas/batch", json=[NORMA_ID_INEXISTENTE])
        assert response.status_code == 404


class TestGetAllNormas:
    def test_retorna_lista(self):
        response = client.get("/normas/")
        assert response.status_code == 200
        data = response.json()
        assert "normas" in data
        assert isinstance(data["normas"], list)

    def test_paginacion_limit(self):
        response = client.get("/normas/?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["normas"]) <= 5
        assert data["limit"] == 5

    def test_paginacion_offset(self):
        r1 = client.get("/normas/?limit=5&offset=0")
        r2 = client.get("/normas/?limit=5&offset=5")
        ids1 = [n["norma_id"] for n in r1.json()["normas"]]
        ids2 = [n["norma_id"] for n in r2.json()["normas"]]
        assert ids1 != ids2

    def test_limit_invalido_retorna_422(self):
        response = client.get("/normas/?limit=0")
        assert response.status_code == 422

    def test_limit_maximo_retorna_422(self):
        response = client.get("/normas/?limit=9999")
        assert response.status_code == 422


class TestSearchNormas:
    def test_busqueda_retorna_resultados(self):
        response = client.get("/normas/buscar/ley")
        assert response.status_code == 200
        data = response.json()
        assert "normas" in data
        assert len(data["normas"]) > 0

    def test_busqueda_sin_resultados_retorna_404(self):
        response = client.get("/normas/buscar/xyzxyzxyz_termino_inexistente")
        assert response.status_code == 404

    def test_busqueda_respeta_limit(self):
        response = client.get("/normas/buscar/ley?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["normas"]) <= 3

    def test_busqueda_paginacion(self):
        r1 = client.get("/normas/buscar/decreto?limit=5&offset=0")
        r2 = client.get("/normas/buscar/decreto?limit=5&offset=5")
        if r1.status_code == 200 and r2.status_code == 200:
            ids1 = [n["norma_id"] for n in r1.json()["normas"]]
            ids2 = [n["norma_id"] for n in r2.json()["normas"]]
            assert ids1 != ids2


class TestGetNormasByStatus:
    def test_vigentes(self):
        response = client.get("/normas/estado/vigente")
        assert response.status_code == 200
        data = response.json()
        assert all(n["estado"] == "vigente" for n in data["normas"])

    def test_derogadas(self):
        response = client.get("/normas/estado/derogada")
        assert response.status_code == 200
        data = response.json()
        assert all(n["estado"] == "derogada" for n in data["normas"])

    def test_estado_invalido_retorna_422(self):
        response = client.get("/normas/estado/invalido")
        assert response.status_code == 422


class TestGetNormasByType:
    def test_busqueda_por_tipo(self):
        response = client.get("/normas/tipo/ley")
        assert response.status_code == 200
        data = response.json()
        assert "normas" in data
        assert len(data["normas"]) > 0

    def test_tipo_inexistente_retorna_404(self):
        response = client.get("/normas/tipo/tipoinexistentexyz")
        assert response.status_code == 404


class TestGetNormasByDateRange:
    def test_rango_valido(self):
        response = client.get("/normas/rango?start_date=2000-01-01&end_date=2020-12-31")
        assert response.status_code == 200
        data = response.json()
        assert "normas" in data

    def test_por_fecha_promulgacion(self):
        response = client.get("/normas/rango?start_date=2000-01-01&date_type=prom")
        assert response.status_code == 200

    def test_sin_start_date_retorna_422(self):
        response = client.get("/normas/rango?end_date=2020-12-31")
        assert response.status_code == 422

    def test_date_type_invalido_retorna_422(self):
        response = client.get("/normas/rango?start_date=2020-01-01&date_type=invalido")
        assert response.status_code == 422


# /instituciones


class TestGetInstituciones:
    def test_retorna_lista(self):
        response = client.get("/instituciones/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_items_tienen_campos_esperados(self):
        response = client.get("/instituciones/")
        assert response.status_code == 200
        item = response.json()[0]
        assert "id" in item
        assert "nombre" in item


class TestGetInstitucion:
    def test_retorna_institucion_existente(self):
        response = client.get(f"/instituciones/{INSTITUCION_ID_EXISTENTE}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == INSTITUCION_ID_EXISTENTE
        assert "nombre" in data

    def test_retorna_404_si_no_existe(self):
        response = client.get(f"/instituciones/{INSTITUCION_ID_INEXISTENTE}")
        assert response.status_code == 404

    def test_id_invalido_retorna_422(self):
        response = client.get("/instituciones/no-es-un-id")
        assert response.status_code == 422


class TestSearchInstituciones:
    def test_busqueda_retorna_resultados(self):
        response = client.get("/instituciones/buscar/ministerio")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_busqueda_sin_resultados_retorna_404(self):
        response = client.get("/instituciones/buscar/xyzxyzxyz_inexistente")
        assert response.status_code == 404

    def test_busqueda_respeta_limit(self):
        response = client.get("/instituciones/buscar/ministerio?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2


class TestGetStatsInstituciones:
    def test_retorna_stats(self):
        response = client.get("/instituciones/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "con_normas" in data
        assert "sin_normas" in data

    def test_stats_consistentes(self):
        response = client.get("/instituciones/stats")
        data = response.json()
        assert data["con_normas"] + data["sin_normas"] == data["total"]


class TestGetNormasPorInstitucion:
    def test_retorna_normas(self):
        response = client.get(f"/instituciones/{INSTITUCION_ID_EXISTENTE}/normas")
        assert response.status_code == 200
        data = response.json()
        assert "normas" in data
        assert len(data["normas"]) > 0

    def test_paginacion(self):
        r1 = client.get(
            f"/instituciones/{INSTITUCION_ID_EXISTENTE}/normas?limit=5&offset=0"
        )
        r2 = client.get(
            f"/instituciones/{INSTITUCION_ID_EXISTENTE}/normas?limit=5&offset=5"
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        ids1 = [n["id"] for n in r1.json()["normas"]]
        ids2 = [n["id"] for n in r2.json()["normas"]]
        assert ids1 != ids2

    def test_institucion_inexistente_retorna_404(self):
        response = client.get(f"/instituciones/{INSTITUCION_ID_INEXISTENTE}/normas")
        assert response.status_code == 404
