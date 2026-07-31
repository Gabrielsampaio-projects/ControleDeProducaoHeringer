-- Rode no SQL Editor do Supabase (projeto do controle de produção)

alter table producao_apontamentos
  alter column hora_fim drop not null;

alter table producao_apontamentos
  add column if not exists status text not null default 'em_producao';
  -- valores possíveis: 'em_producao', 'produzido', 'parada'

create index if not exists idx_apontamentos_status on producao_apontamentos(status);
