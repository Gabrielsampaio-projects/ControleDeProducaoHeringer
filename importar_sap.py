import pandas as pd
import json
import urllib.request
import sys

SUPABASE_URL = "https://ovwcukyrunkhtcunyhsi.supabase.co"   # ← troque
SUPABASE_KEY = "sb_publishable_9A9pHfRkaAWvc2kToA6RVA_yE-TnCa9"              # ← troque

def limpar_num_str(valor):
    """Converte 1010001068.0 → '1010001068' (remove o .0 desnecessário)"""
    if pd.isna(valor):
        return ""
    try:
        return str(int(float(valor)))
    except:
        return str(valor).strip()

def parse_num(valor):
    """Converte para float, retorna None se inválido"""
    try:
        v = float(valor)
        return None if pd.isna(v) else v
    except:
        return None

def importar(arquivo):
    df = pd.read_excel(arquivo, dtype=str)

    # Remove a última linha de totais (onde Planta é NaN)
    df = df[df['Planta'].notna() & (df['Planta'].str.strip() != 'nan')]

    registros = []
    for _, row in df.iterrows():
        data_raw = str(row.get('Data da nova criação', '')).strip()
        data_fmt = data_raw[:10] if data_raw and data_raw != 'nan' else None

        registros.append({
            "planta":             row.get('Planta', '').strip(),
            "passo":              limpar_num_str(row.get('Passo', '')),
            "status_caminhao":    row.get('Status Caminhão', '').strip(),
            "data_criacao":       data_fmt,
            "hora_criacao":       str(row.get('Hora de criação', '')).strip(),
            "cliente":            row.get('Descrição do Cliente', '').strip(),
            "codigo_material":    limpar_num_str(row.get('Código de Material', '')),
            "descricao_material": row.get('Descrição do Materia', '').strip(),
            "tipo_embalagem":     row.get('Tipo de Emabalagem', '').strip(),
            "ord_proc_qtd":       parse_num(row.get('Ord. Proc. – Qtd', '')),
            "motorista":          row.get('Mot. Caminhão', '').strip(),
            "placa_caminhao":     row.get('Placa do Caminhão', '').strip(),
            "tipo_frete":         row.get('Tipo de Frete', '').strip(),
            "qtd_remessa":        parse_num(row.get('Qtd. da Remessa', '')),
            "contrato_sf":        limpar_num_str(row.get('Contrato SF', '')),
            "ordem_venda":        limpar_num_str(row.get('Ordem de Venda', '')),
            "ordem_processo":     limpar_num_str(row.get('Ordem de Processo', '')),
            "remessa":            limpar_num_str(row.get('Remessa', '')),
        })

    if not registros:
        print("⚠️ Nenhum registro encontrado.")
        return

    # Apaga registros do dia antes de reinserir (evita duplicatas)
    data_hoje = registros[0]['data_criacao']
    if data_hoje:
        del_req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/sequenciamento_sap?data_criacao=eq.{data_hoje}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            method="DELETE"
        )
        urllib.request.urlopen(del_req)
        print(f"🗑️ Registros de {data_hoje} removidos antes da reimportação.")

    # Insere os novos registros
    body = json.dumps(registros).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/sequenciamento_sap",
        data=body,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"✅ {len(registros)} registros importados. Status: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"❌ Erro HTTP {e.code}: {e.read().decode()}")

if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "Emissao.XLSX"
    importar(arquivo)