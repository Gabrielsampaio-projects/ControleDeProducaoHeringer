import urllib.request
import urllib.parse
import sys
import os
import json
import getpass

API_URL = "https://controledeproducaoheringer-production.up.railway.app"

def fazer_login():
    print("🔐 Login necessário para importar")
    usuario = input("👤 Usuário: ")
    senha   = getpass.getpass("🔑 Senha: ")

    # Busca máquinas para selecionar
    req = urllib.request.Request(f"{API_URL}/api/init")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    maquinas = data["maquinas"]
    print("\nMáquinas disponíveis:")
    for i, m in enumerate(maquinas):
        print(f"  {i+1}. {m['nome']}")
    idx = int(input("Selecione a máquina (número): ")) - 1
    maquina = maquinas[idx]

    supervisores = data["supervisores"]
    print("\nSupervisores disponíveis:")
    for i, s in enumerate(supervisores):
        print(f"  {i+1}. {s['nome']}")
    idx = int(input("Selecione o supervisor (número): ")) - 1
    supervisor = supervisores[idx]

    payload = json.dumps({
        "usuario":        usuario,
        "senha":          senha,
        "maquina_id":     str(maquina["id"]),
        "maquina_nome":   maquina["nome"],
        "turno":          "Administrativo",
        "supervisor_id":  str(supervisor["id"]),
        "supervisor_nome":supervisor["nome"],
    }).encode()

    req = urllib.request.Request(
        f"{API_URL}/api/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"✅ Login realizado como {result['session']['nome']}\n")
            return result["token"]
    except urllib.error.HTTPError as e:
        print(f"❌ Login falhou: {e.read().decode()}")
        sys.exit(1)

def importar(arquivo, token):
    print(f"📂 Enviando {arquivo} para o backend...")

    with open(arquivo, "rb") as f:
        conteudo = f.read()

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    filename  = os.path.basename(arquivo)

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
    ).encode() + conteudo + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{API_URL}/api/sap/importar",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ {data['importados']} registros importados para {data['data']}.")
    except urllib.error.HTTPError as e:
        print(f"❌ Erro HTTP {e.code}: {e.read().decode()}")

if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "Emissao.XLSX"
    token   = fazer_login()
    importar(arquivo, token)