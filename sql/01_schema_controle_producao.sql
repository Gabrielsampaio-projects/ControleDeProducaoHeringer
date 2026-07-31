-- CONTROLE DE PRODUÇÃO DIÁRIA POR MÁQUINA
-- Rode este script no Supabase: Project > SQL Editor > New query > Run

-- Catálogo de máquinas
create table if not exists producao_maquinas (
  id bigint generated always as identity primary key,
  nome text not null unique,
  unidade text, -- VNA, MCU, TCR, CAN, PG2
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

-- Catálogo de supervisores
create table if not exists producao_supervisores (
  id bigint generated always as identity primary key,
  nome text not null unique,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

-- Usuários (operadores de painel)
create table if not exists producao_usuarios (
  id bigint generated always as identity primary key,
  usuario text not null unique,
  senha text not null, -- texto simples por ora; dá para evoluir para hash depois
  nome_completo text not null,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

-- Catálogo de códigos de parada (pode popular depois com os códigos reais do SAP/planta)
create table if not exists producao_cod_parada (
  codigo text primary key,
  descricao text
);

-- Apontamentos de produção (um registro por lançamento do operador)
create table if not exists producao_apontamentos (
  id bigint generated always as identity primary key,
  usuario_id bigint references producao_usuarios(id),
  maquina_id bigint references producao_maquinas(id),
  turno text not null,          -- ex: '1', '2', '3'
  supervisor_id bigint references producao_supervisores(id),
  data date not null,
  hora_inicio time not null,
  hora_fim time not null,
  ordem_processo text not null, -- chave usada para cruzar com o SAP
  produto text,
  placa text,
  volume_produzido numeric,
  rejeito text,
  cod_parada text references producao_cod_parada(codigo),
  observacao text,
  created_at timestamptz not null default now()
);

create index if not exists idx_apontamentos_data on producao_apontamentos(data);
create index if not exists idx_apontamentos_ordem on producao_apontamentos(ordem_processo);
create index if not exists idx_apontamentos_maquina on producao_apontamentos(maquina_id);

-- Habilita acesso via chave anônima (ajustaremos regras de segurança mais à frente se necessário)
alter table producao_maquinas enable row level security;
alter table producao_supervisores enable row level security;
alter table producao_usuarios enable row level security;
alter table producao_cod_parada enable row level security;
alter table producao_apontamentos enable row level security;

create policy "allow all - maquinas" on producao_maquinas for all using (true) with check (true);
create policy "allow all - supervisores" on producao_supervisores for all using (true) with check (true);
create policy "allow all - usuarios" on producao_usuarios for all using (true) with check (true);
create policy "allow all - cod_parada" on producao_cod_parada for all using (true) with check (true);
create policy "allow all - apontamentos" on producao_apontamentos for all using (true) with check (true);

-- Dados de exemplo (pode apagar depois)
insert into producao_maquinas (nome, unidade) values ('M4', 'VNA') on conflict (nome) do nothing;
insert into producao_supervisores (nome) values ('A definir') on conflict (nome) do nothing;
insert into producao_usuarios (usuario, senha, nome_completo) values ('junior', '1234', 'JUNIOR') on conflict (usuario) do nothing;
