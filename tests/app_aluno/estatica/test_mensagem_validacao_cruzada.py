"""Auditoria estática: toda `validacoes_cruzadas` do registro tem `mensagem`
não vazia — `T-209`, `EC-02`, `AC-06`.

A recusa de validação cruzada mostra ao aluno só a `mensagem` do registro
(os nomes das variáveis vão para o log). Mensagem vazia viraria recusa muda.

REGRAS: EC-02
"""

from __future__ import annotations

from collection.carga import carregar_registros


def test_toda_validacao_cruzada_tem_mensagem() -> None:
    violacoes = [
        f"{registro.ID}: {validacao.variavel_esquerda} {validacao.operador} "
        f"{validacao.variavel_direita}"
        for registro in carregar_registros(incluir_casos_de_prova=True).registros
        for validacao in registro.validacoes_cruzadas
        if not validacao.mensagem.strip()
    ]

    assert not violacoes, "validação cruzada sem mensagem:\n" + "\n".join(violacoes)
