# Implementação das rotas ausentes da API

## Arquivos entregues

| Arquivo | Finalidade |
|---|---|
| `backend/app/main.py` | Backend completo com as duas rotas implementadas. |
| `rotas_api_corrigidas.patch` | Patch unificado aplicável sobre a versão original do ZIP. |
| `test_rotas_faltantes.py` | Teste local de sintaxe, helpers e registro das rotas. |
| `test_rotas_faltantes_mock.py` | Teste simulado do fluxo de retomada e do envelope OEE, sem acesso ao banco. |

## Rotas implementadas

### `POST /api/apontamentos/{id}/retornar`

A rota recebe o ID de um registro de parada e um corpo opcional no formato `{ "hora_fim": "HH:MM" }`. Como o frontend atual envia `{}`, a API utiliza a hora do servidor como fallback. A rota valida o ID, verifica se a parada existe, impede que um operador acesse uma máquina diferente, confirma que o registro é uma parada retomável, encerra a parada e recria a ordem original em `em_producao` quando existe o vínculo em `retomada_de`.

A implementação também faz uma verificação de retomada já criada antes de inserir outra produção. Se a segunda etapa falhar depois do fechamento da parada, a API tenta compensar o fechamento e reabrir o registro. Essa compensação reduz o risco operacional, mas não substitui uma transação SQL ou uma função RPC no Supabase para garantir atomicidade completa sob chamadas simultâneas.

### `GET /api/oee`

A rota aceita `data` no formato `YYYY-MM-DD` e `maquina_id` opcional. Usuários não master ficam sempre limitados à máquina gravada no JWT; usuários master podem consultar todas as máquinas ou filtrar uma máquina específica.

A resposta é compatível com a aba OEE do frontend:

```json
{
  "resumo": [],
  "paradas": [],
  "rows": []
}
```

`resumo` vem da view `vw_oee_diario`, `rows` contém os apontamentos do dia e `paradas` é filtrado a partir dos registros `parada_maquina`, `parada_geral`, registros com status `parada` ou registros que possuem motivo de parada.

## Validações realizadas

A compilação Python do backend foi concluída sem erros. Um teste local confirmou os helpers de hora e ID, o modelo de payload e a presença das duas rotas. Um segundo teste com cliente Supabase simulado confirmou o fluxo de retomada, a proteção por máquina, a associação pelo campo `retomada_de` e o formato da resposta OEE. Nenhum desses testes escreveu no banco de produção.

Para repetir as validações no ambiente local:

```bash
cd /caminho/Controledeproducao
pip install -r backend/requirements.txt
PYTHONPATH=. python3 test_rotas_faltantes.py
PYTHONPATH=. python3 test_rotas_faltantes_mock.py
python3 -m py_compile backend/app/main.py
```

## Aplicação

A versão modificada já está no arquivo `backend/app/main.py` do diretório de trabalho. Para aplicar apenas a alteração sobre uma cópia limpa do ZIP, use o arquivo `rotas_api_corrigidas.patch` ou copie o `main.py` entregue para `backend/app/main.py`.

A solução não altera migrações nem configurações do Supabase. Antes de colocá-la em produção, recomendo testar com um usuário operador e um usuário master, validar o retorno de uma parada vinculada a uma ordem e confirmar com a área de produção se a hora de retorno deve usar o relógio do servidor ou o horário escolhido na interface. Atualmente, o frontend abre um campo para a hora de retorno, mas envia `{}`; por isso a rota utiliza a hora do servidor até que a interface passe a enviar o valor selecionado.
