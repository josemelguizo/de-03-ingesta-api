"""Cliente para APIs Socrata (la plataforma de datos.gov.co).

Documentación de la API: https://dev.socrata.com/docs/queries/
Socrata pagina con $limit (cuántos registros) y $offset (desde cuál).
"""

import time

import requests


class ApiError(Exception):
    """Error que no vale la pena reintentar, o reintentos agotados."""


class SocrataClient:
    # Errores temporales: vale la pena esperar y volver a intentar.
    RETRY_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, domain, dataset_id, session=None, page_size=1000, max_retries=5,
                 backoff_base=1.0, sleep=time.sleep, app_token=None):
        self.url = f"https://{domain}/resource/{dataset_id}.json"
        self.session = session or requests.Session()
        self.page_size = page_size
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.sleep = sleep            # en las pruebas se reemplaza para no esperar de verdad
        self.headers = {"X-App-Token": app_token} if app_token else {}

    def _get_with_retry(self, params: dict) -> list[dict]:
        """Hace UN GET con reintentos y devuelve el JSON (una lista de registros).

        TODO:
          * Usa self.session.get(self.url, params=params, headers=self.headers, timeout=30)
          * 200 -> devuelve resp.json()
          * Código en RETRY_STATUS -> espera y reintenta, hasta self.max_retries veces.
              - Si la respuesta trae el header "Retry-After", espera esos segundos.
              - Si no, backoff exponencial: backoff_base * 2 ** intento (1s, 2s, 4s...)
              - Usa self.sleep(segundos), NUNCA time.sleep directamente.
          * requests.ConnectionError -> también se reintenta con backoff.
          * Cualquier otro código (400, 404...) -> ApiError de inmediato, sin reintentar.
          * Reintentos agotados -> ApiError.

        Pregunta para el README: ¿por qué no tiene sentido reintentar un 400?
        """
        raise NotImplementedError("TODO: GET con reintentos")

    def fetch_pages(self, where: str | None = None, order: str = ":id"):
        """Genera una página (lista de registros) a la vez.

        TODO:
          * Arma params con "$limit", "$offset", "$order" y, si hay, "$where".
          * Pide páginas con _get_with_retry aumentando $offset en page_size.
          * Para cuando llegue una página vacía o con menos de page_size registros.
          * Usa `yield page`, no acumules todo en una lista: así se pueden
            procesar millones de registros sin llenar la memoria.

        Pregunta para el README: ¿por qué hace falta un $order fijo para que la
        paginación con $offset sea confiable?
        """
        raise NotImplementedError("TODO: paginación")
