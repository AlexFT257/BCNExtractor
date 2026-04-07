from typing import Dict, List

from dotenv import load_dotenv

from managers.nlp import NLPManager

load_dotenv()

metadata_manager = NLPManager()
test_norm_id = 271391
test_clave = "materia"
test_valor = "medio"
test_solo_resueltas = False


def test_get_referencias(
    id_norma: int = test_norm_id, solo_resueltas: bool = test_solo_resueltas
):
    referencias = metadata_manager.get_referencias(
        id_norma=id_norma, solo_resueltas=solo_resueltas
    )
    assert isinstance(referencias, list)
    for ref in referencias:
        assert isinstance(ref, dict)
        assert ref.get("id")
        assert ref.get("texto_original")
        if ref.get("resolvida"):
            assert ref.get("id_norma_ref")


def test_get_normas_que_referencian(
    id_norma: int = test_norm_id, limit: int = 50, offset: int = 0
):
    referenciantes = metadata_manager.get_normas_que_referencian(
        id_norma=id_norma, limit=limit, offset=offset
    )
    assert isinstance(referenciantes, list)
    for ref in referenciantes:
        assert isinstance(ref, dict)
        assert ref.get("id")
        assert ref.get("texto_original")


def test_get_entidades(id_norma: int = test_norm_id):
    entidades = metadata_manager.get_entidades(id_norma=id_norma)
    assert isinstance(entidades, list)
    for ent in entidades:
        assert isinstance(ent, dict)
        assert ent.get("texto")
        assert ent.get("tipo")
        assert ent.get("frecuencia")


def test_get_obligaciones(id_norma: int = test_norm_id):
    obligaciones = metadata_manager.get_obligaciones(id_norma=id_norma)
    assert isinstance(obligaciones, list)
    for obligacion in obligaciones:
        assert isinstance(obligacion, dict)
        assert obligacion.get("texto_completo")
        assert obligacion.get("verbo")


def test_get_stats_globales():
    stats = metadata_manager.get_stats_globales()
    assert isinstance(stats, dict)
    assert stats.get("total_referencias")
    assert stats.get("referencias_resueltas")
    assert stats.get("referencias_pendientes")
    assert stats.get("total_obligaciones")
    assert isinstance(stats.get("por_tipo_norma"), list)
    
def test_build_context_for_llm(id_norma: int = test_norm_id):
    context = metadata_manager.build_context_for_llm(id_norma=id_norma)
    assert isinstance(context, str)
    assert context.strip()
