"""Testes de integração desta feature contra serviços externos reais (Postgres).

Mesmo padrão de `tests/integracao/` do motor: todo teste aqui é marcado
`@pytest.mark.requer_banco` e pulado sem `DATABASE_URL` — a suíte principal
roda com os adaptadores de arquivo de `persistencia/app_aluno/`.
"""
