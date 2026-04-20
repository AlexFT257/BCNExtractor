"""
utils/nlp_analyzer.py

Pipeline NLP para normas legales chilenas basado en spaCy.

Estrategia:
  1. EntityRuler  — detecta referencias normativas como entidades NORMA_REF
                    usando patrones de token, antes del NER estadístico.
  2. NER (ner)    — detecta personas, organismos, lugares con es_core_news_lg.
  3. Dependencias — extrae sujeto + plazo de oraciones con verbos de obligación.

El EntityRuler se antepone al NER (before="ner") para que las referencias
normativas no sean sobreescritas por el modelo estadístico.

Instalación:
    pip install spacy
    python -m spacy download es_core_news_lg
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler

# Tipos de datos de salida

@dataclass
class ReferenciaNormativa:
    """Referencia a otra norma detectada en el texto."""

    tipo_norma: str  # "ley", "decreto_supremo", "resolucion", etc.
    numero: Optional[str]  # "19300" normalizado sin puntos — None si no hay número
    anio: Optional[str]  # "1991" — None si no se menciona
    organismo: Optional[str]  # "Ministerio de Salud" — None si no se menciona
    texto_original: str  # span.text tal como aparece en el documento
    resolvida: bool = False  # True cuando se vincula a un id en normas


@dataclass
class EntidadNombrada:
    """Entidad nombrada detectada por el NER estadístico."""

    texto: str
    tipo: str  # "organismo" | "persona" | "lugar" | "fecha" | "monto"
    inicio: int  # char offset en el texto limpio
    fin: int


@dataclass
class ObligacionDetectada:
    """Oración con verbo de obligación o permisión."""

    texto_completo: str
    sujeto: Optional[str]
    verbo: str
    plazo: Optional[str]


@dataclass
class ResultadoNLP:
    """Resultado completo del análisis de una norma."""

    id_norma: int
    referencias: List[ReferenciaNormativa] = field(default_factory=list)
    entidades: List[EntidadNombrada] = field(default_factory=list)
    obligaciones: List[ObligacionDetectada] = field(default_factory=list)
    materias_detectadas: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Patrones del EntityRuler para referencias normativas
#
# Cada patrón es una lista de dicts de atributos de token que spaCy matchea
# secuencialmente. El id es el tipo_norma canónico.
#
# Referencia: https://spacy.io/usage/rule-based-matching#entityruler
# ---------------------------------------------------------------------------

# Variantes de escritura por tipo — el EntityRuler genera un patrón por variante
_VARIANTES_POR_TIPO: Dict[str, List[str]] = {
    "decreto_supremo": ["decreto supremo", "ds"],
    "decreto_con_fuerza_ley": ["decreto con fuerza de ley", "dfl", "d.f.l.", "d.f.l"],
    "decreto_ley": ["decreto ley", "dl", "d.l.", "d.l"],
    "decreto_exento": ["decreto exento"],
    "decreto": ["decreto"],
    "ley": ["ley"],
    "resolucion_exenta": ["resolución exenta", "resolucion exenta"],
    "resolucion": ["resolución", "resolucion"],
    "circular": ["circular"],
    "reglamento": ["reglamento"],
    "instruccion": ["instrucción", "instruccion"],
    "oficio_circular": ["oficio circular"],
    "oficio": ["oficio"],
    "norma_caracter_general": ["norma de carácter general"],
    "auto_acordado": ["auto acordado"],
}

# Token Nº / N° — opcional antes del número
_PAT_N = {"LOWER": {"IN": ["nº", "n°", "n°.", "n°:"]}, "OP": "?"}
# Número de norma: 1-6 dígitos con opcional separador de miles
_PAT_NUM = {"TEXT": {"REGEX": r"[\d]{1,6}(?:[.,]\d{3})?"}}


def _construir_patrones() -> List[Dict]:
    """Genera patrones para EntityRuler desde _VARIANTES_POR_TIPO."""
    patrones = []
    for tipo, variantes in _VARIANTES_POR_TIPO.items():
        for variante in variantes:
            tokens_tipo = [{"LOWER": p} for p in variante.split()]
            # Patrón principal: [tipo_tokens] [Nº?] [número]
            patrones.append(
                {
                    "label": "NORMA_REF",
                    "id": tipo,
                    "pattern": tokens_tipo + [_PAT_N, _PAT_NUM],
                }
            )
            # Patrón compacto para abreviaturas pegadas: "DFL29", "DS12"
            if " " not in variante:
                patrones.append(
                    {
                        "label": "NORMA_REF",
                        "id": tipo,
                        "pattern": [
                            {"TEXT": {"REGEX": rf"(?i){re.escape(variante)}\d+"}}
                        ],
                    }
                )
    return patrones


# Referencias por nombre conocido (sin número explícito en el texto)

_REFERENCIAS_POR_NOMBRE = [
    ("Ley sobre Bases Generales del Medio Ambiente", "ley", "19300"),
    ("Ley Orgánica Constitucional de Municipalidades", "ley", "18695"),
    ("Estatuto Administrativo", "ley", "18834"),
    ("Código Sanitario", "codigo", None),
    ("Código del Trabajo", "codigo", None),
    ("Código Civil", "codigo", None),
]

_PAT_NOMBRES_COMPILADOS = [
    (re.compile(nombre, re.IGNORECASE), tipo, numero)
    for nombre, tipo, numero in _REFERENCIAS_POR_NOMBRE
]


# Verbos de obligación

_VERBOS_OBLIGACION = {
    "deberá",
    "deberán",
    "debe",
    "deben",
    "está obligado",
    "están obligados",
    "queda obligado",
    "quedan obligados",
    "se compromete",
    "se comprometen",
    "se requiere",
    "se requieren",
    "se prohíbe",
    "se prohíben",
    "está prohibido",
    "están prohibidos",
    "queda prohibido",
    "quedan prohibidos",
    "corresponde a",
    "le corresponde",
    "corresponderá a",
    "procederá",
    "procederán",
    "podrá",
    "podrán",
    "puede",
    "pueden",
    "está facultado",
    "están facultados",
}

_PATRONES_PLAZO = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"a\s+más\s+tardar\s+(?:el\s+)?(\d{1,2}\s+de\s+\w+\s+(?:de\s+)?\d{4})",
        r"dentro\s+de\s+(?:un\s+plazo\s+de\s+)?(\w+\s+días(?:\s+hábiles)?)",
        r"dentro\s+de\s+los\s+primeros?\s+(\w+\s+días(?:\s+del\s+mes)?)",
        r"antes\s+del\s+(\d{1,2}\s+de\s+\w+\s+(?:de\s+)?\d{4})",
        r"en\s+un\s+plazo\s+(?:no\s+)?(?:mayor\s+a\s+|de\s+)([^.;]{5,40})",
    ]
]


# Etiquetas NER → tipos internos

_ETIQUETAS_NER = {
    "ORG": "organismo",
    "PER": "persona",
    "LOC": "lugar",
    "GPE": "lugar"
}


# Materias por keywords

_MATERIAS_KEYWORDS: Dict[str, List[str]] = {
    "medio_ambiente": [
        "contaminación",
        "descontaminación",
        "emisiones",
        "medioambiental",
        "impacto ambiental",
        "calidad del aire",
        "residuos",
        "anhídrido sulfuroso",
        "material particulado",
        "arsénico",
    ],
    "mineria": [
        "minería",
        "fundición",
        "enami",
        "yacimiento",
        "mineral",
    ],
    "salud_publica": [
        "salud pública",
        "código sanitario",
        "servicio de salud",
    ],
    "laboral": [
        "trabajadores",
        "remuneración",
        "contrato de trabajo",
        "código del trabajo",
        "sindicato",
        "despido",
    ],
    "tributario": [
        "impuesto",
        "tributario",
        "sii",
        "renta",
        "iva",
        "contribuciones",
    ],
    "financiero": [
        "banco",
        "financiero",
        "cmf",
        "valores",
        "mercado de capitales",
    ],
    "educacion": [
        "educación",
        "establecimiento educacional",
        "docente",
        "mineduc",
    ],
    "vivienda_urbanismo": [
        "urbanismo",
        "construcción",
        "vivienda",
        "minvu",
        "plan regulador",
    ],
}


# Pipeline singleton

_NLP: Optional[Language] = None


def _get_nlp() -> Language:
    global _NLP
    if _NLP is not None:
        return _NLP

    nlp = spacy.load("es_core_news_lg")

    # EntityRuler ANTES del NER para que sus matches no sean sobreescritos
    ruler: EntityRuler = nlp.add_pipe("entity_ruler", before="ner")  # type: ignore
    ruler.add_patterns(_construir_patrones())

    _NLP = nlp
    return _NLP


# Analizador público


class NLPAnalyzer:
    """Extrae referencias, entidades y obligaciones de normas legales chilenas."""

    def analizar(self, id_norma: int, texto: str) -> ResultadoNLP:
        """Analiza el texto Markdown de una norma y retorna ResultadoNLP."""
        texto_limpio = self._limpiar_markdown(texto)
        nlp = _get_nlp()
        doc = nlp(texto_limpio[:900_000])

        resultado = ResultadoNLP(id_norma=id_norma)
        resultado.referencias = self._extraer_referencias(doc, texto_limpio)
        resultado.entidades = self._extraer_entidades(doc)
        resultado.obligaciones = self._extraer_obligaciones(doc)
        resultado.materias_detectadas = self._detectar_materias(texto_limpio)
        return resultado

    # Referencias normativas

    def _extraer_referencias(self, doc, texto_limpio: str) -> List[ReferenciaNormativa]:
        referencias: List[ReferenciaNormativa] = []
        vistas: set = set()

        for ent in doc.ents:
            if ent.label_ != "NORMA_REF":
                continue

            tipo = ent.ent_id_ or "desconocido"
            numero = self._numero_del_span(ent)
            anio = self._anio_siguiente(doc, ent)
            org = self._organismo_siguiente(doc, ent)

            clave = (tipo, numero)
            if clave in vistas:
                continue
            vistas.add(clave)

            referencias.append(
                ReferenciaNormativa(
                    tipo_norma=tipo,
                    numero=numero,
                    anio=anio,
                    organismo=org,
                    texto_original=ent.text,
                )
            )

        # Nombres conocidos sin número explícito
        for patron, tipo, numero in _PAT_NOMBRES_COMPILADOS:
            clave = (tipo, numero)
            if clave in vistas:
                continue
            if patron.search(texto_limpio):
                vistas.add(clave)
                referencias.append(
                    ReferenciaNormativa(
                        tipo_norma=tipo,
                        numero=numero,
                        anio=None,
                        organismo=None,
                        texto_original=patron.pattern,
                    )
                )

        return referencias

    def _numero_del_span(self, ent) -> Optional[str]:
        for token in ent:
            if re.match(r"[\d]{1,6}(?:[.,]\d{3})?$", token.text):
                return token.text.replace(".", "").replace(",", "")
        return None

    def _anio_siguiente(self, doc, ent) -> Optional[str]:
        for token in doc[ent.end : min(ent.end + 6, len(doc))]:
            if re.match(r"^\d{4}$", token.text) and 1800 <= int(token.text) <= 2100:
                return token.text
        return None

    def _organismo_siguiente(self, doc, ent) -> Optional[str]:
        ventana = doc[ent.end : min(ent.end + 12, len(doc))].text
        m = re.search(
            r"del?\s+((?:Ministerio|Servicio|Superintendencia|Contraloría|"
            r"Comisión|Dirección|Subsecretaría)[^,;.\n]{3,40})",
            ventana,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else None

    # Entidades NER estadísticas
    
    def _extraer_entidades(self, doc) -> List[EntidadNombrada]:
        entidades = []
        for ent in doc.ents:
            tipo = _ETIQUETAS_NER.get(ent.label_, "otro")
            if tipo == "otro":
                continue
            texto = ent.text.strip()
            if len(texto) < 3 or texto.isdigit():
                continue
            entidades.append(
                EntidadNombrada(
                    texto=texto,
                    tipo=tipo,
                    inicio=ent.start_char,
                    fin=ent.end_char,
                )
            )
        return entidades

    # Obligaciones

    def _extraer_obligaciones(self, doc) -> List[ObligacionDetectada]:
        obligaciones = []
        for sent in doc.sents:
            sent_lower = sent.text.lower()
            verbo = next((v for v in _VERBOS_OBLIGACION if v in sent_lower), None)
            if not verbo:
                continue
            obligaciones.append(
                ObligacionDetectada(
                    texto_completo=sent.text.strip(),
                    sujeto=self._extraer_sujeto(sent),
                    verbo=verbo,
                    plazo=self._extraer_plazo(sent.text),
                )
            )
        return obligaciones

    def _extraer_sujeto(self, sent) -> Optional[str]:
        for token in sent:
            if token.dep_ in ("nsubj", "nsubjpass") and token.pos_ in ("NOUN", "PROPN"):
                return " ".join(t.text for t in token.subtree if not t.is_punct)[:80]
        return None

    def _extraer_plazo(self, texto: str) -> Optional[str]:
        for patron in _PATRONES_PLAZO:
            m = patron.search(texto)
            if m:
                return m.group(1).strip()
        return None

    # Materias

    def _detectar_materias(self, texto: str) -> List[str]:
        texto_lower = texto.lower()
        scores = {
            materia: sum(texto_lower.count(kw.lower()) for kw in kws)
            for materia, kws in _MATERIAS_KEYWORDS.items()
        }
        scores = {m: s for m, s in scores.items() if s > 0}
        if not scores:
            return []
        umbral = max(scores.values()) * 0.3
        return [
            m
            for m, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if s >= umbral
        ]

    # Limpieza de Markdown

    def _limpiar_markdown(self, texto: str) -> str:
        texto = re.sub(r"^#{1,6}\s+", "", texto, flags=re.MULTILINE)
        texto = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", texto)
        texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
        texto = re.sub(r"```[\s\S]*?```", "", texto)
        texto = re.sub(r"`[^`]+`", "", texto)
        texto = re.sub(r"^[-*_]{3,}\s*$", "", texto, flags=re.MULTILINE)
        return texto.strip()
