-- Rode no SQL Editor do Supabase (projeto do controle de produção)
-- Remove a exigência de o código de parada já existir cadastrado —
-- passa a aceitar texto livre, como no preenchimento do operador.

alter table producao_apontamentos
  drop constraint if exists producao_apontamentos_cod_parada_fkey;
