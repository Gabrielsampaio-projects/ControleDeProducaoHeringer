import asyncio
import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-role")
os.environ.setdefault("JWT_SECRET", "test-secret")

from backend.app import main


STOP = {
    "id": 10,
    "maquina_id": 2,
    "maquina_nome": "M1",
    "usuario_id": 1,
    "supervisor_id": 1,
    "turno": "1",
    "data": "2026-08-19",
    "hora_inicio": "10:00:00",
    "hora_fim": None,
    "status": "em_producao",
    "tipo_registro": "parada_maquina",
    "retomada_de": 20,
    "retomada": False,
    "motivo_parada": "Manutenção",
    "classe_parada": "Não planejada",
}

ORIGIN = {
    "id": 20,
    "maquina_id": 2,
    "maquina_nome": "M1",
    "turno": "1",
    "data": "2026-08-19",
    "hora_inicio": "08:00:00",
    "hora_fim": "10:00:00",
    "ordem_processo": "OP-20",
    "produto": "Produto teste",
    "placa": "ABC1D23",
    "ensaque": "Ensaque 1",
    "embalagem": "25 KG",
    "status": "parada",
    "tipo_registro": "producao",
}


async def fake_get(_http, table, params=""):
    if table == "producao_apontamentos" and "retomada_de=eq.10" in params:
        return []
    if table == "producao_apontamentos" and "id=eq.10" in params:
        return [STOP.copy()]
    if table == "producao_apontamentos" and "id=eq.20" in params:
        return [ORIGIN.copy()]
    if table == "vw_oee_diario":
        return [{"maquina_id": 2, "turno": "1", "oee_pct": "21.6"}]
    if table == "producao_apontamentos":
        return [{"id": 10, "tipo_registro": "parada_maquina", "motivo_parada": "Manutenção"}]
    raise AssertionError(f"consulta inesperada: {table} {params}")


async def fake_patch(_http, table, params, body):
    assert table == "producao_apontamentos"
    assert "id=eq.10" in params
    assert body["status"] in {"parada", "em_producao"}


async def fake_post(_http, table, body):
    assert table == "producao_apontamentos"
    assert body["retomada_de"] == 10
    return [{"id": 30, **body}]


async def run():
    main.sb_get = fake_get
    main.sb_patch = fake_patch
    main.sb_post = fake_post
    main.app.state.http = object()

    session = {
        "master": False,
        "maquina_id": "2",
        "usuario_id": 1,
        "supervisor_id": "1",
        "turno": "1",
        "nome": "Operador teste",
        "supervisor_nome": "Supervisor teste",
        "maquina_nome": "M1",
    }

    retorno = await main.retornar_parada("10", main.RetornoPayload(hora_fim="10:30"), session)
    assert retorno["ok"] is True
    assert retorno["retomada"] is True
    assert retorno["producao"]["id"] == 30

    oee = await main.get_oee(data="2026-08-19", maquina_id="2", sess=session)
    assert set(oee) == {"resumo", "paradas", "rows"}
    assert oee["resumo"][0]["oee_pct"] == "21.6"
    assert oee["paradas"][0]["tipo_registro"] == "parada_maquina"


asyncio.run(run())
print("OK: fluxo simulado de retomada e OEE validado sem acesso ao Supabase")
