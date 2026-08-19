# Controle de Produção — pacote corrigido

Este pacote reúne o frontend, o backend FastAPI, as migrações SQL, a planilha SAP e as configurações necessárias para executar o sistema no Railway.

## Correções incluídas

O backend contém as rotas `POST /api/apontamentos/{id}/retornar` e `GET /api/oee`. Também foram adicionados arquivos de configuração na raiz para que o Railway instale `backend/requirements.txt` e inicie o servidor com `python -m uvicorn`.

## Estrutura principal

| Caminho | Conteúdo |
|---|---|
| `index.html` | Interface web do controle de produção. |
| `backend/app/main.py` | API FastAPI corrigida. |
| `backend/app/motor_producao.py` | Motor de produção. |
| `sql/` | Migrações e esquema do Supabase. |
| `Emissao.XLSX` | Planilha usada na importação SAP. |
| `requirements.txt` | Encaminha para as dependências do backend. |
| `nixpacks.toml` e `Procfile` | Inicialização do serviço na raiz do Railway. |
| `docs/` | Guias das correções aplicadas. |
| `tests/` | Testes locais sem escrita no Supabase. |

## Publicação no Railway

Mantenha o **Root Directory** vazio para que o Railway use a raiz do pacote. O comando configurado é:

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Cadastre no Railway as variáveis `SUPABASE_URL`, `SUPABASE_KEY` e `JWT_SECRET`. A variável `PORT` é fornecida automaticamente.

## Validação local

```bash
pip install -r requirements.txt
PYTHONPATH=. python3 tests/test_rotas_faltantes.py
PYTHONPATH=. python3 tests/test_rotas_faltantes_mock.py
python3 -m py_compile backend/app/main.py
```

Não inclua chaves do Supabase, arquivos `.env` ou tokens no Git ou no frontend.
