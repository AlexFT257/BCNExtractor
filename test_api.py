from typing import Dict, List, Optional
from datetime import datetime, date

from fastapi import Body
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from pydantic import BaseModel

from api import app
from utils.norm_types import Norm, NormResponse
from utils.institution_types import Institution

client = TestClient(app)


def test_get_norm():
    norm_id = 17
    response = client.get(f"/normas/{norm_id}")
    assert response.status_code == 200

    data = NormResponse(**response.json())

    assert data.norma.norma_id == norm_id
    assert data.norma.tipo
    assert data.markdown


def test_get_normas_batch():
    norm_list = [17, 12, 14]
    response = client.post("/normas", json=norm_list)
    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == len(norm_list)


def test_search_normas():
    query = "Ley"
    response = client.get(f"/normas/buscar/{query}")
    assert response.status_code == 200
    assert response.json().get("normas")

    data = response.json()
    assert data.get("normas")
    assert isinstance(data["normas"], list)
    assert len(data["normas"]) > 0


def test_get_institucion():
    institution_id = 12
    response = client.get(f"/institucion/{institution_id}")
    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, dict)
    
    institution = Institution(**data)
    
    assert institution.id == institution_id
    assert institution.nombre
    assert institution.fecha_agregada
    assert institution.fecha_actualizada
    
def test_get_instituciones():
    response = client.get("/instituciones")
    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    for institution_data in data:
        institution = Institution(**institution_data)
        assert institution.id
        assert institution.nombre
        assert institution.fecha_agregada
        assert institution.fecha_actualizada

def test_update_normas_por_institucion():
    # Crear mocks
    mock_institucion = Institution(
        id=1,
        nombre="MINISTERIO DE JUSTICIA",
        fecha_agregada=datetime(2026, 1, 1),
        fecha_actualizada=None
    )
    
    mock_normas = [
        {
            'id': 17,
            'tipo': 'Auto Acordado',
            'numero': 'S/N',
            'id_tipo': 1,
            'abreviatura': 'AA'
        }
    ]
    
    mock_metadata = Norm(
        norma_id=17,
        tipo="Auto Acordado",
        numero="S/N",
        titulo="Mock Title",
        fecha_publicacion=datetime(2020, 1, 1),
        fecha_promulgacion=datetime(2020, 1, 1),
        organismos=["CORTE SUPREMA"],
        derogado=False,
        es_tratado=False,
        materias=[]
    )
    
    # Patchear las instancias globales en api.py
    with patch('api.institution_manager') as mock_inst_mgr, \
         patch('api.client') as mock_client, \
         patch('api.parser') as mock_parser, \
         patch('api.norm_manager') as mock_norm_mgr, \
         patch('api.tipos_normas_manager') as mock_tipos_mgr, \
         patch('api.logger') as mock_logger:
        
        # Configurar comportamiento de los mocks
        mock_inst_mgr.get_by_id.return_value = mock_institucion
        mock_client.get_normas_por_institucion.return_value = mock_normas
        mock_client.get_norma_completa.return_value = "<xml>mock</xml>"
        mock_parser.parse_from_string.return_value = ("# Markdown", mock_metadata)
        mock_norm_mgr.save.return_value = 'nueva'
        mock_tipos_mgr.add_batch.return_value = None
        mock_logger.log.return_value = None
        
        # Ejecutar test
        client = TestClient(app)
        response = client.put("/instituciones/1/normas?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["nuevas"] == 1
        assert data["errores"] == 0
        
        # Verificar que se llamaron los métodos correctos
        mock_inst_mgr.get_by_id.assert_called_once_with(1)
        mock_client.get_normas_por_institucion.assert_called_once_with(1)
        mock_norm_mgr.save.assert_called_once()