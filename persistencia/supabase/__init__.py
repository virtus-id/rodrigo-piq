"""Adaptador Supabase/Postgres do PIQ — `FonteParametros` e `RepositorioSnapshots`
em execução real, opcional (`plans/motor-calculo.plan.md` §2.1, §3, §6).

Todas as tabelas vivem no schema dedicado `motor_calculo` (nunca em `public`
nem em qualquer schema de outro sistema que compartilhe o mesmo banco — ver
`persistencia/supabase/migracoes/001_inicial.sql`). `engine/` não importa
nada deste pacote (lei nº 1 da §1 do plano); só quem monta a aplicação
(fora deste slug) escolhe entre este adaptador e `persistencia/arquivo/`.
"""
