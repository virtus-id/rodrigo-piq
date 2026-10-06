"""`T-354` — o que o aluno respondeu sobre atraso, cobrança judicial e garantia
de cada dívida, para o REVISOR enxergar de relance (junto da nota de incômodo).

Só leitura de respostas, com o rótulo da opção do registro: nenhum selo de
"dívida crítica" é decidido aqui — quem julga é o revisor (Lei nº 3: a
aplicação não aplica regra de negócio). Variável sem resposta fica de fora."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from collection.respostas import RespostasCaso
from report.plano import VocabularioDoCaso

#: (variável gravada, rótulo curto na tela do revisor)
_VARIAVEIS: Final[tuple[tuple[str, str], ...]] = (
    ("TEMPO_ATRASO", "Tempo de atraso"),
    ("COBRANCA_JUDICIAL_INFORMADA", "Cobrança judicial"),
    ("POSSUI_GARANTIA", "Possui garantia"),
    ("TIPO_GARANTIA", "Tipo de garantia"),
)


def fatos_de_risco_por_divida(
    respostas: RespostasCaso, vocabulario: VocabularioDoCaso, dividas: Iterable[str]
) -> dict[str, tuple[tuple[str, str], ...]]:
    """`DIVIDA_ID` → pares (rótulo, resposta) das variáveis acima."""
    resultado: dict[str, tuple[tuple[str, str], ...]] = {}
    for divida in dividas:
        fatos: list[tuple[str, str]] = []
        for variavel, rotulo in _VARIAVEIS:
            valor = respostas.valor_no_item(divida, variavel)
            if valor is None:
                continue
            texto = vocabulario.rotulos_de_opcao.get(variavel, {}).get(str(valor), str(valor))
            fatos.append((rotulo, texto))
        resultado[divida] = tuple(fatos)
    return resultado
