"""Camada de aplicação do PIQ: sessão, autenticação, máquina de estados do caso,
montagem do estado a partir das respostas e invocação do motor.

Não é `collection/` nem `report/` — divergência declarada em
plans/app-aluno.plan.md §3 (`RF-01`). Importa de `engine/` e `persistencia/`;
a recíproca nunca ocorre.
"""
