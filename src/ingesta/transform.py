"""Valida los registros de la API y los convierte en una fila por día."""

from datetime import date
from decimal import Decimal


class RecordError(ValueError):
    pass


def parse_record(rec: dict) -> tuple[Decimal, date, date]:
    """Convierte un registro crudo en (valor, desde, hasta) o lanza RecordError.

    Un registro de la API se ve así (¡todo llega como texto!):
        {"valor": "3792.98", "unidad": "COP",
         "vigenciadesde": "2020-08-05T00:00:00.000",
         "vigenciahasta": "2020-08-05T00:00:00.000"}

    TODO: lanza RecordError si
      * falta algún campo o no se puede convertir (Decimal, date.fromisoformat),
      * la unidad no es "COP",
      * el valor no es positivo,
      * vigenciahasta es anterior a vigenciadesde.

    Usa Decimal y no float para dinero: prueba en Python 0.1 + 0.2 y verás por qué.
    """
    raise NotImplementedError("TODO: validar un registro")


def to_daily_rows(records: list[dict]) -> tuple[list[tuple[date, Decimal]], list[str]]:
    """Devuelve (filas, rechazados).

    filas: lista de (fecha, valor) con UNA fila por día, ordenada por fecha.
      La TRM del viernes por la tarde rige sábado, domingo y lunes, así que un
      registro con vigenciadesde=sábado y vigenciahasta=lunes debe producir 3 filas.
      Si una fecha aparece en dos registros, gana el último.

    rechazados: un mensaje por cada registro inválido. Un registro malo NO
      debe detener la carga de los demás.

    TODO: implementa usando parse_record.
    """
    raise NotImplementedError("TODO: expandir a filas diarias")
