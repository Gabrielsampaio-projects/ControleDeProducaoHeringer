-- Rode no SQL Editor do Supabase (projeto do controle de produção)
-- Guarda o saldo de "sobra" acumulada de cada ordem de processo entre um dia e o outro

create table if not exists producao_sobras (
  ordem_processo text primary key,
  produto text,
  sobra_atual numeric not null default 0,
  ultima_atualizacao date,
  updated_at timestamptz not null default now()
);

alter table producao_sobras enable row level security;
create policy "allow all - sobras" on producao_sobras for all using (true) with check (true);

-- Histórico dos relatórios diários gerados (fica registrado o que foi apurado em cada data)
create table if not exists producao_fechamento_diario (
  id bigint generated always as identity primary key,
  data date not null,
  ordem_processo text not null,
  produto text,
  marcado_sap numeric not null default 0,
  sobra_anterior numeric not null default 0,
  disponivel numeric not null default 0,
  produzido numeric not null default 0,
  sobra_nova numeric not null default 0,
  status text,
  created_at timestamptz not null default now(),
  unique (data, ordem_processo)
);

alter table producao_fechamento_diario enable row level security;
create policy "allow all - fechamento" on producao_fechamento_diario for all using (true) with check (true);
