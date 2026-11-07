"""Almacenamiento: JSON crudo en disco (bronze) y tabla limpia en DuckDB."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb


def save_raw(page: list[dict], raw_dir, ingest_date: date, page_number: int) -> Path:
    """Guarda la página tal cual llegó (ya resuelto).

    Guardar el crudo te permite reprocesar sin volver a llamar a la API, y
    auditar qué recibiste exactamente. La carpeta ingest_date=AAAA-MM-DD es la
    convención de particionado estilo Hive que usan Spark, Athena y BigQuery.
    """
    folder = Path(raw_dir) / f"ingest_date={ingest_date.isoformat()}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"page_{page_number:04d}.json"
    path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    return path


def create_table(con: duckdb.DuckDBPyConnection) -> None:
    """Ya resuelto."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS trm (
            fecha      DATE PRIMARY KEY,
            valor      DECIMAL(10, 2) NOT NULL,
            loaded_at  TIMESTAMP DEFAULT now()
        )
    """)


def get_watermark(con: duckdb.DuckDBPyConnection) -> date | None:
    """Devuelve la fecha más reciente cargada, o None si la tabla está vacía.

    Esta "marca de agua" es lo que hace incremental la ingesta: solo se piden
    a la API los registros posteriores.

    TODO
    """
    raise NotImplementedError("TODO: watermark")


def upsert_trm(con: duckdb.DuckDBPyConnection, rows: list[tuple[date, Decimal]]) -> int:
    """Inserta las filas; si la fecha ya existe, actualiza el valor. Devuelve
    cuántas filas procesó.

    TODO: usa INSERT ... ON CONFLICT (fecha) DO UPDATE SET ...
    Pista: dentro del DO UPDATE, el valor nuevo se llama excluded.valor, y la
    hora actual se obtiene con now().
    """
    raise NotImplementedError("TODO: upsert")
