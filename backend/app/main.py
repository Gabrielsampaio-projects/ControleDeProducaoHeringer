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
    maquinas, supervisores, produtos = await __import__("asyncio").gather(
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
    ordem_processo: Optional[str] = None
    produto: Optional[str] = None
    placa: Optional[str] = None
    ensaque: Optional[str] = None
    embalagem: Optional[str] = None
    observacao: Optional[str] = None
    cod_parada: Optional[str] = None
    status: str
    tipo_registro: str
    retomada_de: Optional[str] = None

class ApontamentoPatch(BaseModel):
    hora_fim: Optional[str] = None
    status: Optional[str] = None
    volume_produzido: Optional[float] = None
    rejeito: Optional[str] = None
    cod_parada: Optional[str] = None
    observacao: Optional[str] = None
    retomada: Optional[bool] = None  

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

    params += f"&retomada=eq.{val}"

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

# ══════════════════════════════════════════════════════════════════════════════
# EMISSÕES SAP
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/sap")
async def get_sap(sess: dict = Depends(verificar_token)):
    http = app.state.http
    sap_rows, prod_rows = await __import__("asyncio").gather(
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
async def toggle_pre_seq(id: str, valor: bool, sess: dict = Depends(verificar_token)):
    http = app.state.http
    await sb_patch(http, "sequenciamento_sap", f"?id=eq.{id}",
                   {"pre_sequenciamento": valor})
    return {"ok": True}

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
