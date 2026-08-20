"""
Heringer — Backend FastAPI
Centraliza todas as chamadas ao Supabase. O HTML passa a chamar
/api/... em vez de chamar o Supabase diretamente, mantendo a
chave secreta fora do navegador.
"""

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import httpx, os, jwt, datetime, io, pandas as pd, json
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import asyncio

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]          # service_role key (secreta!)
JWT_SECRET   = os.environ["JWT_SECRET"]            # string aleatória longa
JWT_ALGO     = "HS256"
JWT_EXP_H    = 12                                  # horas até expirar

# ── cliente HTTP reutilizável ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        base_url=SUPABASE_URL,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    yield
    await app.state.http.aclose()

app = FastAPI(title="Heringer Produção API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrinja ao domínio Pages em produção
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ── helpers Supabase ───────────────────────────────────────────────────────────
async def sb_get(http: httpx.AsyncClient, table: str, params: str = "") -> list:
    r = await http.get(f"/rest/v1/{table}{params}")
    r.raise_for_status()
    return r.json()

async def sb_post(http: httpx.AsyncClient, table: str, body: dict) -> list:
    r = await http.post(f"/rest/v1/{table}",
                        json=body,
                        headers={"Prefer": "return=representation"})
    r.raise_for_status()
    return r.json()

async def sb_patch(http: httpx.AsyncClient, table: str, params: str, body: dict):
    r = await http.patch(f"/rest/v1/{table}{params}",
                         json=body,
                         headers={"Prefer": "return=minimal"})
    r.raise_for_status()

async def sb_delete(http: httpx.AsyncClient, table: str, params: str):
    r = await http.delete(f"/rest/v1/{table}{params}")
    r.raise_for_status()

# ── JWT ───────────────────────────────────────────────────────────────────────
def criar_token(payload: dict) -> str:
    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_H)
    return jwt.encode({**payload, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGO)

def verificar_token(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 — LOGIN
# ══════════════════════════════════════════════════════════════════════════════
class LoginPayload(BaseModel):
    usuario: str
    senha: str
    maquina_id: str
    maquina_nome: str
    turno: str
    supervisor_id: str
    supervisor_nome: str

@app.post("/api/login")
async def login(body: LoginPayload):
    http = app.state.http
    rows = await sb_get(
        http, "producao_usuarios",
        f"?usuario=eq.{body.usuario}&senha=eq.{body.senha}&ativo=eq.true"
        "&select=id,usuario,nome_completo,master"
    )
    if not rows:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    user = rows[0]
    session = {
        "usuario_id":    user["id"],
        "usuario":       user["usuario"],
        "nome":          user["nome_completo"],
        "master":        user.get("master") is True,
        "maquina_id":    body.maquina_id,
        "maquina_nome":  body.maquina_nome,
        "turno":         body.turno,
        "supervisor_id": body.supervisor_id,
        "supervisor_nome": body.supervisor_nome,
    }
    token = criar_token(session)
    return {"token": token, "session": session}

# ══════════════════════════════════════════════════════════════════════════════
# DADOS INICIAIS (máquinas, supervisores, produtos)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/init")
async def init_data():
    http = app.state.http
    maquinas, supervisores, produtos = await asyncio.gather(
        sb_get(http, "producao_maquinas",  "?ativo=eq.true&order=nome.asc"),
        sb_get(http, "producao_supervisores", "?ativo=eq.true&order=nome.asc"),
        sb_get(http, "producao_produtos",  "?ativo=eq.true&order=nome.asc"),
    )
    return {"maquinas": maquinas, "supervisores": supervisores, "produtos": produtos}

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — APONTAMENTOS
# ══════════════════════════════════════════════════════════════════════════════
class ApontamentoCreate(BaseModel):
    data: str
    hora_inicio: str
    hora_fim: Optional[str] = None
    ordem_processo: Optional[str] = None
    produto: Optional[str] = None
    placa: Optional[str] = None
    ensaque: Optional[str] = None
    embalagem: Optional[str] = None
    observacao: Optional[str] = None
    cod_parada: Optional[str] = None
    motivo_parada: Optional[str] = None
    classe_parada: Optional[str] = None
    status: str
    tipo_registro: str  # producao | parada_geral | parada_maquina
    retomada_de: Optional[str] = None

class ApontamentoPatch(BaseModel):
    hora_fim: Optional[str] = None
    status: Optional[str] = None
    volume_produzido: Optional[float] = None
    rejeito: Optional[str] = None
    rejeito_ton: Optional[float] = None
    cod_parada: Optional[str] = None
    motivo_parada: Optional[str] = None
    classe_parada: Optional[str] = None
    observacao: Optional[str] = None
    retomada: Optional[bool] = None

class RetornoPayload(BaseModel):
    # O frontend atual envia {}, portanto a API usa a hora do servidor quando omitido.
    hora_fim: Optional[str] = None

class PreSeqPayload(BaseModel):
    # O modal envia estes campos no corpo JSON. `valor` também pode vir na query
    # para manter compatibilidade com o fluxo de início da fila pré-sequenciada.
    valor: Optional[bool] = None
    ensaque_destino: Optional[str] = None
    maquina_destino_id: Optional[str] = None
    maquina_destino_nome: Optional[str] = None

@app.get("/api/apontamentos")
async def get_apontamentos(
    maquina_id: Optional[str] = None,
    data: Optional[str] = None,
    status: Optional[str] = None,
    data_lt: Optional[str] = None,
    tipo_registro: Optional[str] = None,
    retomada: Optional[str] = None,  
    order: str = "data.desc,hora_inicio.desc",
    sess: dict = Depends(verificar_token),
):
    http = app.state.http
    params = f"?order={order}"
    if retomada is not None:
        val = "true" if retomada.lower() == "true" else "false"
        params += f"&retomada=eq.{val}" # fix indentacao

    # Operador só vê sua máquina (a não ser que seja master e não passe maquina_id)
    if not sess["master"] and not maquina_id:
        maquina_id = sess["maquina_id"]

    if maquina_id:   params += f"&maquina_id=eq.{maquina_id}"
    if data:         params += f"&data=eq.{data}"
    if data_lt:      params += f"&data=lt.{data_lt}"
    if tipo_registro: params += f"&tipo_registro=eq.{tipo_registro}"
    if status:
        # suporta "em_producao" ou lista "em_producao,produzido"
        if "," in status:
            params += f"&status=in.({status})"
        else:
            params += f"&status=eq.{status}"

    return await sb_get(http, "producao_apontamentos", params)

@app.post("/api/apontamentos")
async def create_apontamento(
    body: ApontamentoCreate,
    sess: dict = Depends(verificar_token),
):
    http = app.state.http
    payload = body.model_dump(exclude_none=True)
    payload.update({
        "usuario_id":      sess["usuario_id"],
        "maquina_id":      sess["maquina_id"],
        "turno":           sess["turno"],
        "supervisor_id":   sess["supervisor_id"],
        "operador_nome":   sess["nome"],
        "supervisor_nome": sess["supervisor_nome"],
        "maquina_nome":    sess["maquina_nome"],
    })
    result = await sb_post(http, "producao_apontamentos", payload)
    return result[0] if result else {}

@app.patch("/api/apontamentos/{id}")
async def patch_apontamento(
    id: str,
    body: ApontamentoPatch,
    sess: dict = Depends(verificar_token),
):
    http = app.state.http
    await sb_patch(http, "producao_apontamentos", f"?id=eq.{id}",
                   body.model_dump(exclude_none=True))
    return {"ok": True}

@app.get("/api/apontamentos/{id}")
async def get_apontamento(id: str, sess: dict = Depends(verificar_token)):
    http = app.state.http
    rows = await sb_get(http, "producao_apontamentos",
                        f"?id=eq.{id}&select=ordem_processo,produto,placa,ensaque")
    if not rows:
        raise HTTPException(404, "Não encontrado")
    return rows[0]

# ── RETOMADA DE PARADA ─────────────────────────────────────────────────────────
def _normalizar_hora_retorno(valor: Optional[str]) -> str:
    if not valor:
        return datetime.datetime.now().strftime("%H:%M:%S")
    for formato in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.datetime.strptime(valor, formato).strftime("%H:%M:%S")
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail="hora_fim deve estar no formato HH:MM ou HH:MM:SS")


def _id_inteiro(valor: str, campo: str = "id") -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{campo} inválido")
    if numero <= 0:
        raise HTTPException(status_code=422, detail=f"{campo} inválido")
    return numero


async def _buscar_producao_retornada(http: httpx.AsyncClient, parada_id: int):
    rows = await sb_get(
        http,
        "producao_apontamentos",
        "?retomada_de=eq." + str(parada_id)
        + "&tipo_registro=eq.producao&order=id.desc&limit=1",
    )
    return rows[0] if rows else None


@app.post("/api/apontamentos/{id}/retornar")
async def retornar_parada(
    id: str,
    body: RetornoPayload,
    sess: dict = Depends(verificar_token),
):
    """Fecha a parada e reabre a ordem original, quando houver vínculo.

    A operação é idempotente: repetir a chamada para a mesma parada não cria
    uma segunda produção retomada. Para uma parada sem ordem vinculada, apenas
    o registro da parada é encerrado.
    """
    parada_id = _id_inteiro(id)
    hora_fim = _normalizar_hora_retorno(body.hora_fim)
    http = app.state.http

    parada_rows = await sb_get(
        http,
        "producao_apontamentos",
        f"?id=eq.{parada_id}&select=*&limit=1",
    )
    if not parada_rows:
        raise HTTPException(status_code=404, detail="Parada não encontrada")
    parada = parada_rows[0]

    if not sess.get("master") and str(parada.get("maquina_id")) != str(sess.get("maquina_id")):
        raise HTTPException(status_code=403, detail="Parada fora do escopo da máquina selecionada")

    if parada.get("tipo_registro") not in {"parada_maquina", "parada_geral"}:
        raise HTTPException(status_code=409, detail="O registro informado não é uma parada retomável")

    # Primeiro verifica se uma chamada anterior já criou a retomada.
    existente = await _buscar_producao_retornada(http, parada_id)
    if existente:
        return {
            "ok": True,
            "retomada": True,
            "id_parada": parada_id,
            "parada": parada,
            "producao": existente,
        }

    aberta = parada.get("status") == "em_producao" and not parada.get("hora_fim")
    if not aberta:
        return {
            "ok": True,
            "retomada": False,
            "id_parada": parada_id,
            "parada": parada,
            "producao": None,
        }

    ordem = None
    origem_id = parada.get("retomada_de")
    if origem_id is not None:
        origem_id = _id_inteiro(str(origem_id), "retomada_de")
        origem_rows = await sb_get(
            http,
            "producao_apontamentos",
            f"?id=eq.{origem_id}&select=*&limit=1",
        )
        if not origem_rows:
            raise HTTPException(status_code=409, detail="A ordem original da parada não foi encontrada")
        ordem = origem_rows[0]
        if str(ordem.get("maquina_id")) != str(parada.get("maquina_id")):
            raise HTTPException(status_code=409, detail="A ordem original pertence a outra máquina")

    try:
        await sb_patch(
            http,
            "producao_apontamentos",
            f"?id=eq.{parada_id}",
            {"hora_fim": hora_fim, "status": "parada", "retomada": True},
        )

        producao = None
        if ordem:
            payload = {
                "usuario_id": sess["usuario_id"],
                "maquina_id": sess["maquina_id"],
                "turno": sess["turno"],
                "supervisor_id": sess["supervisor_id"],
                "operador_nome": sess["nome"],
                "supervisor_nome": sess["supervisor_nome"],
                "maquina_nome": sess["maquina_nome"],
                "data": parada["data"],
                "hora_inicio": hora_fim,
                "ordem_processo": ordem.get("ordem_processo"),
                "produto": ordem.get("produto"),
                "placa": ordem.get("placa"),
                "ensaque": ordem.get("ensaque"),
                "embalagem": ordem.get("embalagem"),
                "status": "em_producao",
                "tipo_registro": "producao",
                # No modelo real este campo aponta para a parada que está sendo retomada.
                "retomada_de": parada_id,
            }
            producao_rows = await sb_post(http, "producao_apontamentos", payload)
            producao = producao_rows[0] if producao_rows else None

        return {
            "ok": True,
            "retomada": producao is not None,
            "id_parada": parada_id,
            "parada": {**parada, "hora_fim": hora_fim, "status": "parada", "retomada": True},
            "producao": producao,
        }
    except Exception as exc:
        # O Supabase REST não fornece transação entre dois endpoints. Fazemos
        # uma compensação para não deixar a parada fechada sem a retomada.
        try:
            await sb_patch(
                http,
                "producao_apontamentos",
                f"?id=eq.{parada_id}",
                {"hora_fim": None, "status": "em_producao", "retomada": False},
            )
        except Exception:
            pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=502, detail="Não foi possível concluir a retomada da parada") from exc


# ── OEE ───────────────────────────────────────────────────────────────────────
@app.get("/api/oee")
async def get_oee(
    data: Optional[str] = None,
    maquina_id: Optional[str] = None,
    sess: dict = Depends(verificar_token),
):
    """Entrega o envelope esperado pela aba OEE do frontend."""
    if data:
        try:
            datetime.datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="data deve estar no formato YYYY-MM-DD")
    else:
        data = datetime.datetime.now().strftime("%Y-%m-%d")

    # Operador nunca pode escolher outra máquina via query string.
    if not sess.get("master"):
        maquina_id = str(sess.get("maquina_id"))
    elif maquina_id is not None:
        maquina_id = str(_id_inteiro(maquina_id, "maquina_id"))

    filtro_view = f"?data=eq.{data}&order=maquina_nome.asc,turno.asc&limit=1000"
    filtro_rows = (
        "?data=eq." + data
        + "&select=id,maquina_id,maquina_nome,data,turno,hora_inicio,hora_fim,status,"
          "tipo_registro,ordem_processo,volume_produzido,rejeito,rejeito_ton,"
          "cod_parada,motivo_parada,classe_parada,retomada,retomada_de&"
          "order=maquina_id.asc,turno.asc,hora_inicio.asc&limit=1000"
    )
    if maquina_id:
        filtro_view += f"&maquina_id=eq.{maquina_id}"
        filtro_rows += f"&maquina_id=eq.{maquina_id}"

    http = app.state.http
    resumo, rows = await asyncio.gather(
        sb_get(http, "vw_oee_diario", filtro_view),
        sb_get(http, "producao_apontamentos", filtro_rows),
    )

    paradas = [
        row for row in rows
        if row.get("tipo_registro") in {"parada_maquina", "parada_geral"}
        or row.get("status") == "parada"
        or row.get("motivo_parada")
    ]
    return {"resumo": resumo, "paradas": paradas, "rows": rows}


# ══════════════════════════════════════════════════════════════════════════════
# EMISSÕES SAP
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/sap")
async def get_sap(sess: dict = Depends(verificar_token)):
    http = app.state.http
    sap_rows, prod_rows = await asyncio.gather(
        sb_get(http, "sequenciamento_sap", "?order=data_criacao.asc,hora_criacao.asc"),
        sb_get(http, "producao_apontamentos",
               "?status=in.(em_producao,produzido)&select=ordem_processo,status"),
    )
    status_prod = {r["ordem_processo"]: r["status"] for r in prod_rows if r.get("ordem_processo")}

    result = []
    for r in sap_rows:
        op = r.get("ordem_processo")
        sp = status_prod.get(op)
        st = ("produzido"   if sp == "produzido"   else
              "em_producao" if sp == "em_producao" else
              "pre_seq"     if r.get("pre_sequenciamento") else
              "aguardando")
        if st != "produzido":
            result.append({**r, "_status_real": st})
    return result

@app.patch("/api/sap/{id}/pre-seq")
async def toggle_pre_seq(
    id: str,
    body: Optional[PreSeqPayload] = None,
    valor: Optional[bool] = None,
    sess: dict = Depends(verificar_token),
):
    """Ativa ou remove o pré-sequenciamento de uma ordem SAP.

    Aceita tanto o JSON enviado pelo modal de confirmação quanto o formato
    legado `?valor=false` usado ao iniciar uma ordem da fila.
    """
    http = app.state.http
    valor_final = body.valor if body and body.valor is not None else valor
    if valor_final is None:
        raise HTTPException(422, "Informe valor no JSON ou na query string")

    payload = {"pre_sequenciamento": valor_final}
    if valor_final:
        if not body or not body.ensaque_destino or not body.maquina_destino_id:
            raise HTTPException(400, "Informe ensaque_destino e maquina_destino_id")
        payload.update({
            "ensaque_destino": body.ensaque_destino,
            "maquina_destino_id": body.maquina_destino_id,
            "maquina_destino_nome": body.maquina_destino_nome or sess.get("maquina_nome"),
        })
    else:
        # Evita deixar a fila antiga visível caso a ordem seja pré-sequenciada
        # novamente para outra máquina/ensacadeira.
        payload.update({
            "ensaque_destino": None,
            "maquina_destino_id": None,
            "maquina_destino_nome": None,
        })

    await sb_patch(http, "sequenciamento_sap", f"?id=eq.{id}", payload)
    return {"ok": True, "pre_sequenciamento": valor_final}

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — IMPORTAÇÃO SAP VIA UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
def limpar_num_str(valor):
    try:
        if pd.isna(valor): return ""
        return str(int(float(valor)))
    except:
        return str(valor).strip()

def parse_num(valor):
    try:
        v = float(valor)
        return None if pd.isna(v) else v
    except:
        return None

@app.post("/api/sap/importar")
async def importar_sap(
    file: UploadFile = File(...),
    sess: dict = Depends(verificar_token),
):
    if not sess.get("master"):
        raise HTTPException(403, "Apenas usuários master podem importar")

    content = await file.read()
    df = pd.read_excel(io.BytesIO(content), dtype=str)
    df = df[df["Planta"].notna() & (df["Planta"].str.strip() != "nan")]

    registros = []
    for _, row in df.iterrows():
        data_raw = str(row.get("Data da nova criação", "")).strip()
        data_fmt = data_raw[:10] if data_raw and data_raw != "nan" else None
        registros.append({
            "planta":             row.get("Planta", "").strip(),
            "passo":              limpar_num_str(row.get("Passo", "")),
            "status_caminhao":    row.get("Status Caminhão", "").strip(),
            "data_criacao":       data_fmt,
            "hora_criacao":       str(row.get("Hora de criação", "")).strip(),
            "cliente":            row.get("Descrição do Cliente", "").strip(),
            "codigo_material":    limpar_num_str(row.get("Código de Material", "")),
            "descricao_material": row.get("Descrição do Materia", "").strip(),
            "tipo_embalagem":     row.get("Tipo de Emabalagem", "").strip(),
            "ord_proc_qtd":       parse_num(row.get("Ord. Proc. – Qtd", "")),
            "motorista":          row.get("Mot. Caminhão", "").strip(),
            "placa_caminhao":     row.get("Placa do Caminhão", "").strip(),
            "tipo_frete":         row.get("Tipo de Frete", "").strip(),
            "qtd_remessa":        parse_num(row.get("Qtd. da Remessa", "")),
            "contrato_sf":        limpar_num_str(row.get("Contrato SF", "")),
            "ordem_venda":        limpar_num_str(row.get("Ordem de Venda", "")),
            "ordem_processo":     limpar_num_str(row.get("Ordem de Processo", "")),
            "remessa":            limpar_num_str(row.get("Remessa", "")),
        })

    if not registros:
        raise HTTPException(400, "Nenhum registro válido encontrado no arquivo")

    http = app.state.http
    # Apaga os registros da data antes de reinserir
    data_hoje = registros[0]["data_criacao"]
    if data_hoje:
        await sb_delete(http, "sequenciamento_sap", f"?data_criacao=eq.{data_hoje}")

    await sb_post(http, "sequenciamento_sap", registros)
    return {"importados": len(registros), "data": data_hoje}

# ── health check ──────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "app": "Heringer Produção API"}