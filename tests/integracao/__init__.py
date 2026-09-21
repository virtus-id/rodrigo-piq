"""Testes de integração contra serviços externos reais (Supabase/Postgres).

Diferem de `tests/regras/` por não testarem uma regra normativa isolada, mas
a INTEGRAÇÃO entre dois adaptadores concretos da mesma porta (`FonteParametros`,
`RepositorioSnapshots`) — paridade arquivo × Postgres e round-trip de
persistência (T-76). Todo teste aqui é `@pytest.mark.skipif` sem `DATABASE_URL`
— a suíte de homologação do motor nunca depende do Supabase.
"""
