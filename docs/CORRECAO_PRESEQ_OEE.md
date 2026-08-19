# Correção do pré-sequenciamento e do OEE

## Pré-sequenciamento

O modal de confirmação do `index.html` envia `valor`, `ensaque_destino`, `maquina_destino_id` e `maquina_destino_nome` no corpo JSON de `PATCH /api/sap/{id}/pre-seq`. A versão anterior do backend declarava `valor` apenas como parâmetro de query; por isso o FastAPI retornava `loc: ["query", "valor"]`.

A rota corrigida usa o modelo `PreSeqPayload`, aceita o corpo JSON do modal e também mantém compatibilidade com o fluxo legado `?valor=false` usado ao remover uma ordem da fila. Quando a ordem é pré-sequenciada, a API grava o destino da máquina e da ensacadeira. Quando é removida, limpa os campos de destino.

## OEE

O frontend chama `GET /api/oee`. A rota já está implementada no `backend/app/main.py` corrigido e consulta a view `vw_oee_diario` do Supabase. A resposta contém `resumo`, `paradas` e `rows`.

A verificação ao vivo do domínio do Railway mostrou que a raiz está ativa, mas `/api/oee` ainda retornava HTTP 404. Isso significa que o serviço publicado estava executando uma versão anterior do backend, ou estava apontando para outro arquivo/serviço. Depois de publicar este pacote, o deploy deve ser refeito e o serviço deve usar o comando:

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

O **Root Directory** do Railway deve ficar vazio quando o repositório contém os arquivos de deploy na raiz.

## Validação executada

Foram validados localmente, sem acesso de escrita ao Supabase:

```text
PATCH /api/sap/{id}/pre-seq via corpo JSON
PATCH /api/sap/{id}/pre-seq via query ?valor=false
GET /api/oee registrado no FastAPI
POST /api/apontamentos/{id}/retornar
```
