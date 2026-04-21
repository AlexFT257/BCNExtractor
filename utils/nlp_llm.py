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
        Extrae únicamente las entidades mencionadas en el siguiente párrafo, clasificándolas en las categorías: organismo, persona, lugar.
        Devuelve solo las entidades identificadas y su categoría correspondiente.
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
            },
        )
        
        try:
            data = response.json()
            return json.loads(data["response"])
        except json.JSONDecodeError:
            return None
