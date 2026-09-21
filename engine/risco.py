"""Classifica `RISCO_RECAIDA` e `RISCO_COMPORTAMENTAL_GERAL` pela regra D.4 —
RF-18 · §11.4.

Fonte normativa: `specs/motor-calculo.spec.md` §11.4 (regra D.4). Contagem de
1 sinal por condição ativa entre os 5 sinais de `RISCO_RECAIDA`:

1. `NOVA_DIVIDA_PREVISTA` = SIM ou TALVEZ
2. `MECANISMO_DEFICIT` inclui cartão, cheque especial, empréstimo ou
   parcelamento para fechar o mês
3. `HISTORICO_RECAIDA` = SIM
4. `NOVO_PARCELAMENTO_PREVISTO` = SIM ou TALVEZ
5. `PACTO` = `EM_CONSTRUCAO` ou `NAO_ESTABELECIDO`

E entre os 6 sinais de `RISCO_COMPORTAMENTAL_GERAL` (§11.4):

1. Crédito usado para fechar o mês
2. `RISCO_IMPULSO` = duas ou mais compras não planejadas nos últimos 30 dias
3. Alguma linha reutilizável ainda usada frequentemente ou às vezes
4. `HISTORICO_RECAIDA` = SIM
5. `NOVO_PARCELAMENTO_PREVISTO` = SIM ou TALVEZ
6. `NIVEL_CONTROLE` = `FRAGIL`

Classificação (§11.4, comum às duas contagens da regra D.4): `0` = BAIXO ·
`1–2` = MODERADO · `3+` = ALTO.

**Trava (AC-25).** Dado desconhecido não conta artificialmente como risco
positivo: um sinal cujo dado de origem é `DESCONHECIDO` tem `ativo=False`,
mesmo que "talvez fosse" se soubéssemos. O campo `desconhecido=True` só existe
para rastreabilidade — quem consome `ClassificacaoRisco` (ex.: redução de
`CONFIABILIDADE_DADOS` quando material) decide o que fazer com isso, não esta
função.

`SinalD4` e `ClassificacaoRisco` são compartilhados entre
`classificar_RISCO_RECAIDA` (5 sinais) e `classificar_RISCO_COMPORTAMENTAL_GERAL`
(T-16, 6 sinais) — não são reescritos.

REGRAS: Final[tuple[str, ...]] = ("RF-18", "§11.4")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from engine.estado import SinaisComportamentais
from engine.tipos import DESCONHECIDO, NIVEL_CONTROLE, NIVEL_RISCO, SimNaoTalvez

REGRAS: Final[tuple[str, ...]] = ("RF-18", "§11.4")

# B1.09 (`specs/piq-app-spec.md`): valores de `MECANISMO_DEFICIT` que
# caracterizam o sinal 2 de RISCO_RECAIDA — crédito ou parcelamento usado
# para fechar o mês. Os demais valores do domínio (CORTE, RESERVA, ATRASO,
# TERCEIRO, RENDA_EXTRA, NAO_OCORRE, OUTRA) não disparam o sinal.
#
# É o MESMO campo coletado (B1.09) usado pelo sinal 1 de
# RISCO_COMPORTAMENTAL_GERAL ("crédito usado para fechar o mês",
# `engine/estado.py::SinaisComportamentais`) — a canônica não modela duas
# variáveis distintas para os dois enunciados; reaproveitado abaixo em
# `classificar_RISCO_COMPORTAMENTAL_GERAL`, não duplicado.
MECANISMOS_DEFICIT_DE_RISCO: Final[frozenset[str]] = frozenset(
    {"CARTAO", "CHEQUE_ESPECIAL", "EMPRESTIMO", "PARCELAMENTO"}
)

# B2.11 (`specs/piq-app-spec.md`): valores de `RISCO_IMPULSO` que
# caracterizam "duas ou mais compras não planejadas nos últimos 30 dias"
# (sinal 2 de RISCO_COMPORTAMENTAL_GERAL). `NAO_SEI` é resposta coletada
# ("não consigo avaliar"), não desconhecimento de dado — não dispara o
# sinal, mas também não é o caso `desconhecido=True` do `SinalD4` (ver
# `Desconhecido`/`DESCONHECIDO` em `engine/tipos.py` para esse outro caso).
RISCO_IMPULSO_DE_RISCO: Final[frozenset[str]] = frozenset({"DUAS_TRES", "QUATRO_MAIS"})

# B5.C07 (`specs/piq-app-spec.md`): valores de `LINHA_CONTINUA_SENDO_UTILIZADA`
# que caracterizam "linha reutilizável ainda usada frequentemente ou às vezes"
# (sinal 3 de RISCO_COMPORTAMENTAL_GERAL). O domínio da variável não tem um
# valor "FREQUENTEMENTE" — a pergunta oferece "Sim, com frequência." que é
# mapeada para `SIM` (ver linha "Valor interno / mapeamento" de B5.C07);
# "às vezes" mapeia para `AS_VEZES`. `NAO`/`NAO_APLICA` não disparam o sinal.
LINHA_CONTINUA_DE_RISCO: Final[frozenset[str]] = frozenset({"SIM", "AS_VEZES"})


@dataclass(frozen=True, slots=True)
class SinalD4:
    """Um sinal individual da regra D.4, com `ativo` e `desconhecido`
    registrados separadamente — auditabilidade (AC-24) e trava de
    AC-25 (desconhecido não é risco positivo)."""

    nome: str
    ativo: bool
    desconhecido: bool  # AC-25: desconhecido NÃO conta como risco positivo,
    # mas alimenta a redução de confiabilidade se material


@dataclass(frozen=True, slots=True)
class ClassificacaoRisco:
    """Resultado da regra D.4: os sinais individuais (para o revisor refazer
    a conta) mais a contagem e o nível já classificado."""

    sinais: tuple[SinalD4, ...]  # auditabilidade: o revisor refaz a conta
    contagem: int  # 0=BAIXO · 1–2=MODERADO · 3+=ALTO
    nivel: NIVEL_RISCO


def _classificar_por_contagem(contagem: int) -> NIVEL_RISCO:
    """§11.4: `0` = BAIXO · `1–2` = MODERADO · `3+` = ALTO. Comum às duas
    contagens da regra D.4 (RISCO_RECAIDA e RISCO_COMPORTAMENTAL_GERAL)."""
    if contagem == 0:
        return NIVEL_RISCO.BAIXO
    if contagem <= 2:
        return NIVEL_RISCO.MODERADO
    return NIVEL_RISCO.ALTO


def classificar_RISCO_RECAIDA(sinais: SinaisComportamentais) -> ClassificacaoRisco:
    """§11.4 — 5 sinais de `RISCO_RECAIDA`. Recebe só `SinaisComportamentais`
    (entradas coletadas): sem parâmetro extra, sem estado global."""
    sinal_1 = SinalD4(
        nome="NOVA_DIVIDA_PREVISTA",
        ativo=sinais.NOVA_DIVIDA_PREVISTA in (SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ),
        desconhecido=False,  # SimNaoTalvez não tem membro DESCONHECIDO.
    )

    mecanismo_desconhecido = sinais.MECANISMO_DEFICIT is DESCONHECIDO
    sinal_2 = SinalD4(
        nome="MECANISMO_DEFICIT",
        ativo=(
            not mecanismo_desconhecido
            and bool(MECANISMOS_DEFICIT_DE_RISCO & sinais.MECANISMO_DEFICIT)  # type: ignore[operator]
        ),
        desconhecido=mecanismo_desconhecido,
    )

    sinal_3 = SinalD4(
        nome="HISTORICO_RECAIDA",
        ativo=sinais.HISTORICO_RECAIDA is SimNaoTalvez.SIM,
        desconhecido=False,
    )

    sinal_4 = SinalD4(
        nome="NOVO_PARCELAMENTO_PREVISTO",
        ativo=sinais.NOVO_PARCELAMENTO_PREVISTO in (SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ),
        desconhecido=False,
    )

    sinal_5 = SinalD4(
        nome="PACTO",
        ativo=sinais.PACTO in ("EM_CONSTRUCAO", "NAO_ESTABELECIDO"),
        desconhecido=False,
    )

    todos = (sinal_1, sinal_2, sinal_3, sinal_4, sinal_5)
    contagem = sum(1 for sinal in todos if sinal.ativo)
    return ClassificacaoRisco(
        sinais=todos, contagem=contagem, nivel=_classificar_por_contagem(contagem)
    )


def classificar_RISCO_COMPORTAMENTAL_GERAL(
    sinais: SinaisComportamentais, nivel_controle: NIVEL_CONTROLE
) -> ClassificacaoRisco:
    """§11.4 — 6 sinais de `RISCO_COMPORTAMENTAL_GERAL`.

    `nivel_controle` é parâmetro **obrigatório**, de propósito: o sexto sinal
    ("`NIVEL_CONTROLE` = `FRAGIL`") depende de um valor já derivado por
    `derivar_NIVEL_CONTROLE` (`engine/comportamento.py`, T-12) — esta função
    não rederiva `NIVEL_CONTROLE` a partir de `PerfilComportamental`, só
    compara o resultado já pronto. Reforça por assinatura, não por
    convenção, a ordem do grafo da §11.10 (`RF-27`): `NIVEL_CONTROLE` precisa
    existir antes desta chamada.
    """
    mecanismo_desconhecido = sinais.MECANISMO_DEFICIT is DESCONHECIDO
    sinal_1 = SinalD4(
        nome="MECANISMO_DEFICIT",  # "crédito usado para fechar o mês"
        ativo=(
            not mecanismo_desconhecido
            and bool(MECANISMOS_DEFICIT_DE_RISCO & sinais.MECANISMO_DEFICIT)  # type: ignore[operator]
        ),
        desconhecido=mecanismo_desconhecido,
    )

    impulso_desconhecido = sinais.RISCO_IMPULSO is DESCONHECIDO
    sinal_2 = SinalD4(
        nome="RISCO_IMPULSO",
        ativo=(
            not impulso_desconhecido and sinais.RISCO_IMPULSO in RISCO_IMPULSO_DE_RISCO
        ),
        desconhecido=impulso_desconhecido,
    )

    linha_desconhecida = sinais.LINHA_CONTINUA_SENDO_UTILIZADA is DESCONHECIDO
    sinal_3 = SinalD4(
        nome="LINHA_CONTINUA_SENDO_UTILIZADA",
        ativo=(
            not linha_desconhecida
            and sinais.LINHA_CONTINUA_SENDO_UTILIZADA in LINHA_CONTINUA_DE_RISCO
        ),
        desconhecido=linha_desconhecida,
    )

    sinal_4 = SinalD4(
        nome="HISTORICO_RECAIDA",
        ativo=sinais.HISTORICO_RECAIDA is SimNaoTalvez.SIM,
        desconhecido=False,
    )

    sinal_5 = SinalD4(
        nome="NOVO_PARCELAMENTO_PREVISTO",
        ativo=sinais.NOVO_PARCELAMENTO_PREVISTO in (SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ),
        desconhecido=False,
    )

    sinal_6 = SinalD4(
        nome="NIVEL_CONTROLE",
        ativo=nivel_controle is NIVEL_CONTROLE.FRAGIL,
        desconhecido=False,  # NIVEL_CONTROLE é sempre derivado (função total, T-12).
    )

    todos = (sinal_1, sinal_2, sinal_3, sinal_4, sinal_5, sinal_6)
    contagem = sum(1 for sinal in todos if sinal.ativo)
    return ClassificacaoRisco(
        sinais=todos, contagem=contagem, nivel=_classificar_por_contagem(contagem)
    )
