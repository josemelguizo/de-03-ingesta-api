from datetime import date
from decimal import Decimal

import duckdb
import pytest

from fakes import CONNECTION_ERROR, FakeResponse, FakeSession, SleepRecorder, trm
from ingesta.client import ApiError, SocrataClient
from ingesta.pipeline import run
from ingesta.storage import create_table, get_watermark, save_raw, upsert_trm
from ingesta.transform import to_daily_rows


def make_client(responses, page_size=2, **kwargs):
    session, sleep = FakeSession(responses), SleepRecorder()
    client = SocrataClient("api.example.com", "abcd-1234", session=session,
                           page_size=page_size, sleep=sleep, **kwargs)
    return client, session, sleep


# ---------- client.py: paginación ----------

def test_pagina_hasta_una_pagina_incompleta():
    client, session, _ = make_client([
        FakeResponse(200, [{"a": 1}, {"a": 2}]),
        FakeResponse(200, [{"a": 3}, {"a": 4}]),
        FakeResponse(200, [{"a": 5}]),
    ])
    pages = list(client.fetch_pages())
    assert [len(p) for p in pages] == [2, 2, 1]
    assert [c["params"]["$offset"] for c in session.calls] == [0, 2, 4]
    assert all(c["params"]["$limit"] == 2 for c in session.calls)


def test_se_detiene_con_pagina_vacia():
    client, session, _ = make_client([
        FakeResponse(200, [{"a": 1}, {"a": 2}]),
        FakeResponse(200, []),
    ])
    assert len(list(client.fetch_pages())) == 1
    assert len(session.calls) == 2


def test_envia_filtro_orden_y_url():
    client, session, _ = make_client([FakeResponse(200, [])])
    list(client.fetch_pages(where="vigenciahasta > '2024-01-01'", order="vigenciadesde"))
    call = session.calls[0]
    assert call["url"] == "https://api.example.com/resource/abcd-1234.json"
    assert call["params"]["$where"] == "vigenciahasta > '2024-01-01'"
    assert call["params"]["$order"] == "vigenciadesde"


def test_es_un_generador_perezoso():
    # Si el cliente cargara todo a memoria antes de devolver, no escalaría.
    client, session, _ = make_client([
        FakeResponse(200, [{"a": 1}, {"a": 2}]),
        FakeResponse(200, [{"a": 3}]),
    ])
    pages = client.fetch_pages()
    next(pages)
    assert len(session.calls) == 1


def test_envia_app_token_si_existe():
    client, session, _ = make_client([FakeResponse(200, [])], app_token="secreto")
    list(client.fetch_pages())
    assert session.calls[0]["headers"]["X-App-Token"] == "secreto"


# ---------- client.py: reintentos ----------

def test_reintenta_errores_temporales_con_backoff_exponencial():
    client, session, sleep = make_client([
        FakeResponse(503), FakeResponse(500), FakeResponse(200, [{"a": 1}]),
    ], backoff_base=1.0)
    assert list(client.fetch_pages()) == [[{"a": 1}]]
    assert sleep.waits == [1.0, 2.0]


def test_respeta_retry_after_en_429():
    client, _, sleep = make_client([
        FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, []),
    ])
    list(client.fetch_pages())
    assert sleep.waits == [7.0]


def test_reintenta_errores_de_conexion():
    client, _, sleep = make_client([CONNECTION_ERROR, FakeResponse(200, [])])
    list(client.fetch_pages())
    assert len(sleep.waits) == 1


def test_se_rinde_despues_de_max_reintentos():
    client, session, _ = make_client([FakeResponse(503)] * 4, max_retries=3)
    with pytest.raises(ApiError):
        list(client.fetch_pages())
    assert len(session.calls) == 4  # 1 intento + 3 reintentos


def test_no_reintenta_errores_del_cliente():
    client, session, sleep = make_client([FakeResponse(400, {"message": "consulta mal formada"})])
    with pytest.raises(ApiError):
        list(client.fetch_pages())
    assert len(session.calls) == 1 and sleep.waits == []


# ---------- transform.py ----------

def test_un_dia_por_registro_normal():
    rows, rejected = to_daily_rows([trm("2024-03-05", "2024-03-05", "3900.10")])
    assert rows == [(date(2024, 3, 5), Decimal("3900.10"))]
    assert rejected == []


def test_expande_fin_de_semana_a_cada_dia():
    rows, _ = to_daily_rows([trm("2024-03-09", "2024-03-11")])  # sábado a lunes
    assert [d for d, _ in rows] == [date(2024, 3, 9), date(2024, 3, 10), date(2024, 3, 11)]


def test_rechaza_registros_invalidos_sin_detener_la_carga():
    rows, rejected = to_daily_rows([
        trm("2024-03-05", "2024-03-05"),
        trm("2024-03-06", "2024-03-06", valor="no-es-numero"),
        trm("2024-03-07", "2024-03-07", valor="-5"),
        trm("2024-03-08", "2024-03-08", unidad="USD"),
        trm("2024-03-12", "2024-03-10"),              # termina antes de empezar
        {"valor": "4000"},                            # faltan fechas
    ])
    assert len(rows) == 1
    assert len(rejected) == 5


def test_salida_ordenada_y_sin_fechas_repetidas():
    rows, _ = to_daily_rows([
        trm("2024-03-06", "2024-03-06", "2"),
        trm("2024-03-05", "2024-03-05", "1"),
        trm("2024-03-06", "2024-03-06", "3"),   # repetido: gana el último
    ])
    assert rows == [(date(2024, 3, 5), Decimal("1")), (date(2024, 3, 6), Decimal("3"))]


# ---------- storage.py ----------

@pytest.fixture
def con():
    c = duckdb.connect()
    create_table(c)
    yield c
    c.close()


def test_watermark_vacio_y_luego_maxima_fecha(con):
    assert get_watermark(con) is None
    upsert_trm(con, [(date(2024, 1, 1), Decimal("1")), (date(2024, 1, 3), Decimal("1"))])
    assert get_watermark(con) == date(2024, 1, 3)


def test_upsert_actualiza_sin_duplicar(con):
    upsert_trm(con, [(date(2024, 1, 1), Decimal("4000.00"))])
    upsert_trm(con, [(date(2024, 1, 1), Decimal("4100.00")), (date(2024, 1, 2), Decimal("4050.00"))])
    assert con.execute("SELECT COUNT(*) FROM trm").fetchone()[0] == 2
    assert con.execute("SELECT valor FROM trm WHERE fecha = '2024-01-01'").fetchone()[0] == Decimal("4100.00")


def test_save_raw_particiona_por_fecha_de_ingesta(tmp_path):
    path = save_raw([{"a": 1}], tmp_path, date(2024, 5, 1), 3)
    assert path == tmp_path / "ingest_date=2024-05-01" / "page_0003.json"
    assert path.read_text(encoding="utf-8") == '[{"a": 1}]'


# ---------- pipeline de punta a punta ----------

def test_pipeline_completo_e_incremental(con, tmp_path):
    client, _, _ = make_client([
        FakeResponse(200, [trm("2024-03-08", "2024-03-08", "3900"), trm("2024-03-09", "2024-03-11", "3950")]),
        FakeResponse(200, []),
    ])
    first = run(con, client, tmp_path, full=True)
    assert first["dias_cargados"] == 4

    client2, session2, _ = make_client([FakeResponse(200, [trm("2024-03-12", "2024-03-12", "3980")])])
    second = run(con, client2, tmp_path)
    assert second["desde"] == date(2024, 3, 11)
    assert "2024-03-11" in session2.calls[0]["params"]["$where"]
    assert con.execute("SELECT COUNT(*) FROM trm").fetchone()[0] == 5
