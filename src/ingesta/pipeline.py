"""Orquesta la ingesta de la TRM: API -> JSON crudo -> DuckDB.

Este archivo ya está completo; el reto está en client.py, transform.py y
storage.py. Uso:

    python -m ingesta.pipeline              # incremental desde la última fecha
    python -m ingesta.pipeline --full       # todo el histórico
"""

import argparse
import os
from datetime import date

import duckdb
from dotenv import load_dotenv

from ingesta.client import SocrataClient
from ingesta.storage import create_table, get_watermark, save_raw, upsert_trm
from ingesta.transform import to_daily_rows

DOMAIN = "www.datos.gov.co"
DATASET_ID = "32sa-8pi3"  # Tasa de Cambio Representativa del Mercado - Histórico


def run(con, client, raw_dir: str, full: bool = False) -> dict:
    create_table(con)
    watermark = None if full else get_watermark(con)
    # Pedimos lo que TERMINA después de la última fecha cargada: un registro
    # de fin de semana empieza el sábado y termina el lunes. Lo que se repita
    # no hace daño porque la carga es un upsert.
    where = f"vigenciahasta > '{watermark.isoformat()}T00:00:00'" if watermark else None

    today = date.today()
    records = []
    for n, page in enumerate(client.fetch_pages(where=where, order="vigenciadesde"), start=1):
        save_raw(page, raw_dir, today, n)
        records.extend(page)

    rows, rejected = to_daily_rows(records)
    loaded = upsert_trm(con, rows)
    summary = {"desde": watermark, "registros_api": len(records),
               "dias_cargados": loaded, "rechazados": len(rejected)}
    for msg in rejected[:10]:
        print(f"[rechazado] {msg}")
    return summary


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ingesta de la TRM desde datos.gov.co")
    parser.add_argument("--full", action="store_true", help="recarga todo el histórico")
    args = parser.parse_args()

    client = SocrataClient(DOMAIN, DATASET_ID, app_token=os.getenv("SOCRATA_APP_TOKEN"))
    with duckdb.connect(os.getenv("DUCKDB_FILE", "trm.duckdb")) as con:
        summary = run(con, client, os.getenv("RAW_DIR", "data/raw/trm"), full=args.full)
    print(f"[pipeline] {summary}")


if __name__ == "__main__":
    main()
