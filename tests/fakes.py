"""Dobles de prueba: una API falsa para probar sin red.

SocrataClient recibe `session` y `sleep` como parámetros. En producción son
requests.Session() y time.sleep; en las pruebas les pasamos estos objetos.
Eso se llama inyección de dependencias, y es lo que hace testeable el código
que habla con el mundo exterior.
"""

import requests


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    """Devuelve las respuestas en el orden en que se las das, y anota cada
    llamada para que la prueba pueda revisar qué parámetros se enviaron."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "headers": headers})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class SleepRecorder:
    """Reemplaza time.sleep: no espera, solo anota cuánto se pidió esperar."""

    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def trm(desde, hasta, valor="4000.50", unidad="COP"):
    return {"valor": valor, "unidad": unidad,
            "vigenciadesde": f"{desde}T00:00:00.000",
            "vigenciahasta": f"{hasta}T00:00:00.000"}


CONNECTION_ERROR = requests.ConnectionError("sin red")
