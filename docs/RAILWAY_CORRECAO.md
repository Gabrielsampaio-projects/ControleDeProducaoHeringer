# Correção do deploy no Railway

## Diagnóstico

O log de deploy mostra repetidamente:

```text
/bin/bash: line 1: uvicorn: command not found
```

Isso ocorre antes de o FastAPI carregar. O problema não está nas novas rotas nem no Supabase: o ambiente de execução não recebeu o pacote `uvicorn` ou o executável não está disponível no `PATH`.

No projeto original, `requirements.txt`, `Procfile` e `nixpacks.toml` estavam dentro de `backend/`. Se o serviço Railway estiver usando a raiz do repositório como diretório de trabalho, o instalador não encontra automaticamente `backend/requirements.txt`. A aplicação entra em ciclo de reinicialização, o que explica os `502` e o `499` vistos nos logs de rede.

## Correção incluída

Foram adicionados ou ajustados os seguintes arquivos:

| Arquivo | Alteração |
|---|---|
| `requirements.txt` | Inclui `backend/requirements.txt` a partir da raiz. |
| `nixpacks.toml` | Instala as dependências a partir da raiz e inicia `backend/app/main.py`. |
| `Procfile` | Inicia o backend pelo caminho `cd backend && python -m uvicorn ...`. |
| `backend/nixpacks.toml` | Usa `python -m pip` para instalar e `python -m uvicorn` para iniciar. |
| `backend/Procfile` | Usa `python -m uvicorn` em vez do executável direto. |

A chamada `python -m uvicorn` é intencional: ela usa o mesmo interpretador Python que instalou as dependências e evita problemas de `PATH`.

## Passos para publicar

Faça commit e push desses arquivos junto com o `main.py` atualizado:

```bash
git add main.py requirements.txt nixpacks.toml Procfile backend/nixpacks.toml backend/Procfile
git commit -m "Corrige inicializacao FastAPI no Railway"
git push
```

No Railway, confirme que o serviço está apontando para o repositório correto e deixe o **Root Directory** vazio para usar a raiz do repositório. Depois force um novo deploy. Com os arquivos da raiz, o comando esperado será equivalente a:

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Como alternativa, se preferir manter o Root Directory configurado como `backend`, também é possível usar os arquivos dentro de `backend/`; nesse caso o comando de start deve ser:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Variáveis obrigatórias

Depois de corrigir o instalador, verifique se estas variáveis estão cadastradas no Railway:

| Variável | Valor |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase. |
| `SUPABASE_KEY` | Chave `service_role`, mantida somente no backend. |
| `JWT_SECRET` | String longa e aleatória para assinar os tokens. |

`PORT` é fornecida automaticamente pelo Railway e não deve ser fixada manualmente no comando.

## Validação realizada

Os dois arquivos TOML foram analisados com sucesso, as dependências declaradas foram instaladas localmente e o aplicativo iniciou com `python -m uvicorn` usando variáveis de ambiente de teste. Nenhum dado do Supabase foi alterado.

Após o próximo deploy, o primeiro teste deve ser abrir:

```text
https://SEU-DOMINIO-RAILWAY/
```

A resposta esperada é semelhante a:

```json
{"status":"ok","app":"Heringer Produção API"}
```

Se o erro mudar de `uvicorn: command not found` para uma mensagem sobre `SUPABASE_URL`, `SUPABASE_KEY` ou `JWT_SECRET`, isso significará que a instalação foi corrigida e restará apenas cadastrar ou ajustar as variáveis de ambiente.
