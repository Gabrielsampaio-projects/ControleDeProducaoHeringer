# Controle de Produção dos Maquinários — Heringer (VNA)

Plataforma de sequenciamento de produção por máquina, com apuração de
sobra diária acumulada cruzando os dados do SAP com o banco de produção.

## Estrutura

```
/app     -> plataforma web (index.html) — sequenciamento por máquina,
            dashboard e relatório. Conecta direto no Supabase.
/sql     -> scripts SQL, na ordem em que devem ser rodados no
            SQL Editor do Supabase (projeto do controle de produção).
/motor   -> motor Python que cruza o relatório do SAP com o banco,
            calcula a sobra acumulada e gera o relatório Excel diário.
```

## Setup — banco (Supabase)

Rode os scripts da pasta `/sql` **na ordem numérica**, no SQL Editor do
projeto Supabase criado para este sistema:

1. `01_schema_controle_producao.sql` — tabelas base (máquinas, supervisores,
   usuários, sequenciamentos)
2. `02_alter_status.sql` — status do sequenciamento (em produção / produzido / parada)
3. `03_fix_cod_parada.sql` — libera código de parada como texto livre
4. `04_alter_parada_geral.sql` — paradas gerais (sem ordem) e retomada de produção
5. `05_sobras_e_fechamento.sql` — saldo de sobra acumulada e histórico de fechamento diário

## Setup — plataforma web (`/app`)

`index.html` é um arquivo único (sem build, sem dependências de instalação).
Basta abrir no navegador, ou publicar como página estática (GitHub Pages,
Netlify, etc). As chaves do Supabase (URL + chave pública `anon`) estão
embutidas no arquivo — são seguras de expor no front-end porque o acesso
é controlado pelas políticas (RLS) do banco.

## Setup — motor de comparação SAP x Banco (`/motor`)

Requer Python 3 instalado. No Windows, dê duplo clique em
`rodar_motor_producao.bat` — ele instala as dependências (pandas, openpyxl,
requests) na primeira vez, abre uma janela pra você escolher o Excel
exportado do SAP (relatório de emissão com as ordens marcadas), cruza com
os sequenciamentos fechados como "Produzido" no banco, calcula a sobra
acumulada e gera `relatorio_producao_<data>.xlsx` na mesma pasta do
arquivo do SAP.

## Lógica de sobra

Para cada ordem de processo, todo dia:

```
disponível = sobra do dia anterior + quantidade marcada no SAP hoje
sobra_nova = disponível - quantidade produzida hoje
```

A sobra fica salva na tabela `producao_sobras` e é carregada
automaticamente no próximo dia. O histórico de cada fechamento diário
fica em `producao_fechamento_diario`, usado depois para o fechamento
semanal.

## Próximos passos

- Dashboard consolidado (HTML) usando o histórico de `producao_fechamento_diario`
- Fechamento semanal automático
