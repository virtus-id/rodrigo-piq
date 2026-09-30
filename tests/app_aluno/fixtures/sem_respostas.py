"""Caso sem respostas nem itens — para as rotas que leem respostas ATUAIS ao
lado do snapshot (`T-267`: a fonte de comprovação do plano) em testes que
não exercitam esse dado. Sem isto, a rota abriria conexão Supabase real."""

from __future__ import annotations

from fastapi import FastAPI

from app.http.rotas_coleta import obter_repositorio_itens, obter_repositorio_respostas


class RepositorioVazio:
    """`listar_do_caso` de respostas e de itens: nada gravado."""

    def listar_do_caso(self, *_args: object, **_kwargs: object) -> tuple[()]:
        return ()


def sem_respostas_nem_itens(aplicacao: FastAPI) -> None:
    aplicacao.dependency_overrides[obter_repositorio_respostas] = RepositorioVazio
    aplicacao.dependency_overrides[obter_repositorio_itens] = RepositorioVazio
