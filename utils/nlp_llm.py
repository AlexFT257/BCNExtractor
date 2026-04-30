import json
from typing import List, Optional

import requests
from catalogue import Dict


class NLPLLM:
    """Clase para interactuar con el modelo de lenguaje natural (NLP) local."""

    base = "http://localhost:11434/api"
    list_model = "/tags"
    generate = "/generate"

    def __init__(
        self, model: Optional[str] = "gemma4:latest", format: Optional[Dict] = None
    ) -> None:
        """
        Inicializa la clase NLPLLM.

        Args:
            model (Optional[str]): El nombre del modelo a utilizar. Por defecto es "gemma4:latest".
            format (Optional[Dict]): El formato de salida esperado. Por defecto es None.
        """
        self.models = self.get_models()

        if not self.models:
            raise ValueError("No models available")

        self.model = model
        self.format = format
        self.prompt = """
        Eres un procesador NLP y categorizador de entidades.
        Tu única tarea es extraer Entidades Nombradas (NER) del texto proporcionado.
        
        Debes extraer entidades que pertenezcan EXCLUSIVAMENTE a estas tres categorías:
        1. "organismo": Instituciones gubernamentales, empresas, ministerios, municipalidades, etc.
        2. "persona": Nombres de individuos.
        3. "lugar": Ciudades, regiones, países, direcciones geográficas.
        
        REGLAS:
        - Ignora nombres de leyes, decretos o articulos(ej. Ley 19.300, D.F.L).
        - Debes apegarte estrictamente al esquema JSON proporcionado.
        """

        if self.model not in [model["name"] for model in self.models]:
            raise ValueError(f"Model {self.model} not found")

        if self.format is None:
            self.format = {
                "type": "object",
                "properties": {
                    "entidades": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": "string"},
                                "tipo": {"type": "string"},
                            },
                        },
                        "required": ["nombre", "tipo"],
                    }
                },
            }

    def get_models(self) -> List[dict | None]:
        response = requests.get(f"{self.base}{self.list_model}")
        data = response.json()

        if data.get("models") is None:
            return []

        return data["models"]

    def generate_response(self, text: str) -> dict | None:
        # print(f"Generating response for: {text}")
        response = requests.post(
            f"{self.base}{self.generate}",
            json={
                "model": self.model,
                "stream": False,
                # "options": {
                # "temperature": 0.1,
                # },
                "prompt": self.prompt + "\n\n" + text,
                "format": self.format,
                "options": {
                    # "temperature": 0.1,
                    "num_ctx": 32768  # context window size
                },
            },
        )

        try:
            data = response.json()
            return json.loads(data["response"])
        except json.JSONDecodeError:
            return None
