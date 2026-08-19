import asyncio
import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-role")
os.environ.setdefault("JWT_SECRET", "test-secret")

from backend.app import main


async def run():
    chamadas = []

    async def fake_patch(_http, table, params, body):
        chamadas.append((table, params, body))

    main.sb_patch = fake_patch
    main.app.state.http = object()
    sess = {"maquina_nome": "M1"}

    resposta_json = await main.toggle_pre_seq(
        "sap-1",
        body=main.PreSeqPayload(
            valor=True,
            ensaque_destino="Ensaque 1",
            maquina_destino_id="maq-1",
            maquina_destino_nome="M1",
        ),
        sess=sess,
    )
    assert resposta_json["pre_sequenciamento"] is True
    assert chamadas[-1][2]["pre_sequenciamento"] is True
    assert chamadas[-1][2]["ensaque_destino"] == "Ensaque 1"

    resposta_query = await main.toggle_pre_seq(
        "sap-1",
        body=None,
        valor=False,
        sess=sess,
    )
    assert resposta_query["pre_sequenciamento"] is False
    assert chamadas[-1][2]["pre_sequenciamento"] is False
    assert chamadas[-1][2]["maquina_destino_id"] is None


asyncio.run(run())
print("OK: pré-sequenciamento validado via JSON e query sem acesso ao Supabase")
