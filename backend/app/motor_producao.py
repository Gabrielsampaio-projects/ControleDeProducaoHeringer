# -*- coding: utf-8 -*-
"""
MOTOR DE COMPARAÇÃO — CONTROLE DE PRODUÇÃO DOS MAQUINÁRIOS
=============================================================
O que este script faz, todo dia:

1. Abre uma janela para você escolher o arquivo do SAP (Emissao.xlsx)
2. Soma, por Ordem de Processo, a quantidade marcada no SAP no dia
   (uma ordem pode aparecer em várias linhas/remessas — soma tudo)
3. Busca no Supabase os sequenciamentos fechados como "Produzido" no dia
4. Pega a sobra que ficou acumulada do dia anterior (tabela producao_sobras)
5. Calcula:
       disponível     = sobra_anterior + marcado_no_sap_hoje
       sobra_nova     = disponível - produzido_hoje
6. Salva a sobra_nova no banco (fica pronta pra amanhã)
7. Grava o histórico do dia (producao_fechamento_diario)
8. Gera um Excel com o relatório do dia, na mesma pasta do arquivo do SAP

Não precisa mexer em nada dentro do código — só rodar o .bat.
"""

import sys
import datetime
import requests
import pandas as pd
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    HAS_GUI = True
except Exception:
    HAS_GUI = False

# =========================================================
# CONFIGURAÇÃO — dados do projeto Supabase do controle de produção
# =========================================================
SUPABASE_URL = "https://ovwcukyrunkhtcunyhsi.supabase.co"
SUPABASE_KEY = "sb_publishable_9A9pHfRkaAWvc2kToA6RVA_yE-TnCa9"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

COL_ORDEM = "Ordem de Processo"
COL_QTD = "Ord. Proc. – Qtd"
COL_PRODUTO = "Descrição do Materia"
COL_DATA = "Data da nova criação"


def escolher_arquivo_sap():
    if HAS_GUI:
        root = tk.Tk()
        root.withdraw()
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo do SAP (Emissao.xlsx)",
            filetypes=[("Excel", "*.xlsx *.xls")]
        )
        root.destroy()
        return caminho
    else:
        return input("Caminho do arquivo do SAP: ").strip('"')


def avisar(titulo, msg, erro=False):
    print(f"\n{titulo}\n{msg}\n")
    if HAS_GUI:
        root = tk.Tk()
        root.withdraw()
        if erro:
            messagebox.showerror(titulo, msg)
        else:
            messagebox.showinfo(titulo, msg)
        root.destroy()


def ler_sap(caminho):
    df = pd.read_excel(caminho)
    faltando = [c for c in [COL_ORDEM, COL_QTD, COL_PRODUTO] if c not in df.columns]
    if faltando:
        raise ValueError(
            f"O arquivo do SAP não tem as colunas esperadas: {faltando}. "
            f"Colunas encontradas: {list(df.columns)}"
        )
    df[COL_ORDEM] = df[COL_ORDEM].astype(str).str.strip()
    marcado = (
        df.groupby(COL_ORDEM)
        .agg(marcado_sap=(COL_QTD, "sum"), produto=(COL_PRODUTO, "first"))
        .reset_index()
        .rename(columns={COL_ORDEM: "ordem_processo"})
    )
    return marcado


def buscar_produzido_hoje(data_str):
    """Soma o volume_produzido por ordem, só dos sequenciamentos fechados como 'Produzido' no dia."""
    url = f"{SUPABASE_URL}/rest/v1/producao_apontamentos"
    params = {
        "data": f"eq.{data_str}",
        "status": "eq.produzido",
        "tipo_registro": "eq.producao",
        "select": "ordem_processo,volume_produzido",
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return pd.DataFrame(columns=["ordem_processo", "produzido"])
    df = pd.DataFrame(rows)
    df["ordem_processo"] = df["ordem_processo"].astype(str).str.strip()
    df["volume_produzido"] = pd.to_numeric(df["volume_produzido"], errors="coerce").fillna(0)
    return df.groupby("ordem_processo").agg(produzido=("volume_produzido", "sum")).reset_index()


def buscar_sobras_existentes(ordens):
    """Busca a sobra_atual de cada ordem que já existe na tabela producao_sobras."""
    if not ordens:
        return {}
    url = f"{SUPABASE_URL}/rest/v1/producao_sobras"
    # PostgREST: filtro "in.(a,b,c)"
    lista = ",".join(ordens)
    params = {"ordem_processo": f"in.({lista})", "select": "ordem_processo,sobra_atual"}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return {row["ordem_processo"]: row["sobra_atual"] for row in r.json()}


def salvar_sobra(ordem_processo, produto, sobra_nova, data_str):
    url = f"{SUPABASE_URL}/rest/v1/producao_sobras"
    body = {
        "ordem_processo": ordem_processo,
        "produto": produto,
        "sobra_atual": sobra_nova,
        "ultima_atualizacao": data_str,
    }
    r = requests.post(
        url,
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=body,
    )
    r.raise_for_status()


def salvar_fechamento(linha, data_str):
    url = f"{SUPABASE_URL}/rest/v1/producao_fechamento_diario"
    body = {
        "data": data_str,
        "ordem_processo": linha["ordem_processo"],
        "produto": linha["produto"],
        "marcado_sap": linha["marcado_sap"],
        "sobra_anterior": linha["sobra_anterior"],
        "disponivel": linha["disponivel"],
        "produzido": linha["produzido"],
        "sobra_nova": linha["sobra_nova"],
        "status": linha["status"],
    }
    r = requests.post(
        url,
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=body,
    )
    r.raise_for_status()


def classificar(disponivel, produzido):
    if produzido <= 0:
        return "Não produzido"
    if produzido >= disponivel:
        return "Produzido"
    return "Parcial"


def main():
    print("=" * 60)
    print("MOTOR DE COMPARAÇÃO — CONTROLE DE PRODUÇÃO DOS MAQUINÁRIOS")
    print("=" * 60)

    caminho = escolher_arquivo_sap()
    if not caminho:
        print("Nenhum arquivo selecionado. Encerrando.")
        return

    data_str = datetime.date.today().isoformat()

    try:
        print(f"\nLendo arquivo do SAP: {caminho}")
        marcado = ler_sap(caminho)
        print(f"  -> {len(marcado)} ordens distintas marcadas no arquivo.")

        print("Buscando sequenciamentos 'Produzido' de hoje no banco...")
        produzido = buscar_produzido_hoje(data_str)
        print(f"  -> {len(produzido)} ordens com produção registrada hoje.")

        todas_ordens = sorted(
            set(marcado["ordem_processo"]) | set(produzido["ordem_processo"])
        )
        print("Buscando sobras acumuladas de dias anteriores...")
        sobras_anteriores = buscar_sobras_existentes(todas_ordens)

        marcado_map = marcado.set_index("ordem_processo").to_dict("index")
        produzido_map = produzido.set_index("ordem_processo").to_dict("index")

        linhas = []
        for ordem in todas_ordens:
            marc = marcado_map.get(ordem, {}).get("marcado_sap", 0)
            produto = marcado_map.get(ordem, {}).get("produto", "")
            prod = produzido_map.get(ordem, {}).get("produzido", 0)
            sobra_ant = sobras_anteriores.get(ordem, 0) or 0

            disponivel = sobra_ant + marc
            sobra_nova = disponivel - prod

            linha = {
                "ordem_processo": ordem,
                "produto": produto,
                "marcado_sap": round(marc, 3),
                "sobra_anterior": round(sobra_ant, 3),
                "disponivel": round(disponivel, 3),
                "produzido": round(prod, 3),
                "sobra_nova": round(sobra_nova, 3),
                "status": classificar(disponivel, prod),
            }
            linhas.append(linha)

        print("Salvando sobra atualizada e histórico no banco...")
        for linha in linhas:
            salvar_sobra(linha["ordem_processo"], linha["produto"], linha["sobra_nova"], data_str)
            salvar_fechamento(linha, data_str)

        df_final = pd.DataFrame(linhas).rename(columns={
            "ordem_processo": "Ordem de Processo",
            "produto": "Produto",
            "marcado_sap": "Marcado no SAP (hoje)",
            "sobra_anterior": "Sobra do dia anterior",
            "disponivel": "Disponível",
            "produzido": "Produzido (hoje)",
            "sobra_nova": "Nova sobra",
            "status": "Status",
        })

        pasta_saida = Path(caminho).parent
        nome_saida = pasta_saida / f"relatorio_producao_{data_str}.xlsx"
        with pd.ExcelWriter(nome_saida, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="Fechamento do dia", index=False)
            resumo = pd.DataFrame([{
                "Data": data_str,
                "Ordens marcadas no SAP": len(marcado),
                "Ordens com produção": len(produzido),
                "Total marcado (SAP)": round(marcado["marcado_sap"].sum(), 3),
                "Total produzido": round(produzido["produzido"].sum() if not produzido.empty else 0, 3),
                "Total em sobra (fim do dia)": round(sum(l["sobra_nova"] for l in linhas), 3),
            }])
            resumo.to_excel(writer, sheet_name="Resumo", index=False)

        print(f"\nRelatório gerado em: {nome_saida}")
        avisar(
            "Concluído",
            f"Relatório do dia {data_str} gerado com sucesso:\n\n{nome_saida}\n\n"
            f"{len(linhas)} ordens processadas."
        )

    except Exception as e:
        avisar("Erro", str(e), erro=True)
        raise


if __name__ == "__main__":
    main()
