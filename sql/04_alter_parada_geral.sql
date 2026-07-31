-- Rode no SQL Editor do Supabase (projeto do controle de produção)

alter table producao_apontamentos
  alter column ordem_processo drop not null;

alter table producao_apontamentos
  add column if not exists tipo_registro text not null default 'producao';
  -- valores: 'producao' (ligado a uma ordem) | 'parada_geral' (almoço, limpeza, etc, sem ordem)

alter table producao_apontamentos
  add column if not exists retomada_de bigint references producao_apontamentos(id);
  -- aponta para o registro de parada que esta ordem está retomando

create index if not exists idx_apontamentos_tipo on producao_apontamentos(tipo_registro);
