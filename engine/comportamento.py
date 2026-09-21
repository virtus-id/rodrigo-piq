"""Deriva `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS` e
`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` — RF-23, RF-24, RF-27.

Fonte normativa: `specs/piq-definicoes-engine.md` §1, §4 e §5. `NIVEL_CONTROLE`
é a raiz do grafo de derivação da §11.10 da spec do slug — depende apenas de
`PerfilComportamental` (entrada já coletada), nada mais. `CONFIABILIDADE_DADOS`
é o próximo nó do mesmo grafo: depende de `NIVEL_CONTROLE` (já derivado) mais
3 das 8 variáveis do Bloco 2 (§11.10 passo 3b, `plans/motor-calculo.plan.md`
§5). `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` (T-18, `BURACO-05`) é o nó
seguinte (§11.10 passo 3d): depende de `NIVEL_CONTROLE` e `RISCO_RECAIDA`
já derivados, mais `NECESSIDADE_VITORIA`/`HISTORICO_ABANDONO` (entrada
coletada, `engine/estado.py::SinaisComportamentais`).

Domínio de `NIVEL_CONTROLE`: `FORTE` · `PARCIAL` · `FRAGIL`. Domínio de
`CONFIABILIDADE_DADOS`: `ALTA` · `MEDIA` · `BAIXA`. Sem score oculto, sem
média ponderada, sem pesos para calibração (Definições §4/§5) — por isso as
duas regras são puramente categóricas, sem nenhum parâmetro `P_*` envolvido.
`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` é booleana e é a única das três que
lê um parâmetro (`P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA`, Definições §1).

Ordem de avaliação **obrigatória**:
- `NIVEL_CONTROLE` (Definições §4, último parágrafo): `FRAGIL` primeiro; se
  nenhuma condição de `FRAGIL` ocorrer, testar `FORTE`; se `FORTE` não for
  satisfeito integralmente, classificar `PARCIAL`.
- `CONFIABILIDADE_DADOS` (Definições §5, último parágrafo): **`BAIXA` →
  `ALTA` → `MEDIA`** — ordem diferente da de `NIVEL_CONTROLE` (que testa
  FRAGIL→FORTE→PARCIAL). Não inverter.

Essas ordens estão expressas na sequência `if ...: ... elif ...: ... else:
...` de cada função abaixo — não é apenas comentário, é o fluxo de controle.
"""

from __future__ import annotations

from typing import Final

from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    REVISAO_SEMANAL,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.parametros import Parametros
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    SimNaoTalvez,
)

REGRAS: Final[tuple[str, ...]] = (
    "RF-23",
    "RF-24",
    "RF-27",
    "Definições §1",
    "Definições §4",
    "Definições §5",
)


def derivar_NIVEL_CONTROLE(perfil: PerfilComportamental) -> NIVEL_CONTROLE:
    """Definições §4 — domínio `FORTE` · `PARCIAL` · `FRAGIL`.

    Ordem de avaliação obrigatória: `FRAGIL` → `FORTE` → `PARCIAL`. A função
    é total: qualquer combinação das 8 variáveis do Bloco 2 cai em um dos
    três ramos, já que `PARCIAL` é o `else` final, sem condição própria —
    "todos os demais casos" (Definições §4).

    Recebe só `PerfilComportamental`: sem parâmetro extra, sem estado global.
    """
    # 1º — FRAGIL: qualquer (OU) das quatro condições basta.
    fragil = (
        perfil.REGISTRO_GASTOS in (REGISTRO_GASTOS.RARAMENTE, REGISTRO_GASTOS.NAO_REGISTRA)
        or perfil.CONHECIMENTO_GASTO is CONHECIMENTO_GASTO.NAO_SEI
        or perfil.GASTOS_NAO_IDENTIFICADOS
        in (GASTOS_NAO_IDENTIFICADOS.FREQUENTE, GASTOS_NAO_IDENTIFICADOS.NAO_CONFERE)
        or perfil.REVISAO_SEMANAL is REVISAO_SEMANAL.NUNCA
    )
    if fragil:
        return NIVEL_CONTROLE.FRAGIL

    # 2º — FORTE: todas (E) as cinco condições precisam ser satisfeitas.
    forte = (
        perfil.REGISTRO_GASTOS in (REGISTRO_GASTOS.TUDO, REGISTRO_GASTOS.MAIORIA)
        and perfil.FREQUENCIA_REGISTRO
        in (
            FREQUENCIA_REGISTRO.DIARIA,
            FREQUENCIA_REGISTRO.VARIAS_SEMANA,
            FREQUENCIA_REGISTRO.SEMANAL,
        )
        and perfil.CONHECIMENTO_GASTO
        in (CONHECIMENTO_GASTO.BOA_APROXIMACAO, CONHECIMENTO_GASTO.RAZOAVEL)
        and perfil.REVISAO_SEMANAL in (REVISAO_SEMANAL.SEMPRE, REVISAO_SEMANAL.MAIORIA)
        and perfil.GASTOS_NAO_IDENTIFICADOS
        not in (GASTOS_NAO_IDENTIFICADOS.FREQUENTE, GASTOS_NAO_IDENTIFICADOS.NAO_CONFERE)
    )
    if forte:
        return NIVEL_CONTROLE.FORTE

    # 3º — PARCIAL: todos os demais casos (fallback, garante função total).
    # `COBERTURA_PEQUENOS_GASTOS`/`COBERTURA_MEIOS_PAGAMENTO`/`DEFASAGEM_REGISTRO`
    # não entram na fórmula de NIVEL_CONTROLE (Definições §4) — só na de
    # CONFIABILIDADE_DADOS (§5, fora do escopo de T-12). Omissão deliberada,
    # fiel à fonte: ela não cita essas 3 variáveis nesta regra.
    return NIVEL_CONTROLE.PARCIAL


def derivar_CONFIABILIDADE_DADOS(
    nivel_controle: NIVEL_CONTROLE, perfil: PerfilComportamental
) -> CONFIABILIDADE_DADOS:
    """Definições §5 — domínio `ALTA` · `MEDIA` · `BAIXA`.

    Ordem de avaliação obrigatória: `BAIXA` → `ALTA` → `MEDIA` — invertida
    em relação à de `NIVEL_CONTROLE` (que é `FRAGIL` → `FORTE` → `PARCIAL`).
    A função é total: qualquer combinação de `nivel_controle` + as 3
    variáveis do Bloco 2 usadas aqui cai em um dos três ramos, já que
    `MEDIA` é o `else` final, sem condição própria — "todos os demais
    casos" (Definições §5).

    `nivel_controle` é parâmetro **obrigatório e posicional-primeiro**, de
    propósito: não existe sobrecarga nem valor default que permita chamar
    esta função sem primeiro ter derivado `NIVEL_CONTROLE`
    (`derivar_NIVEL_CONTROLE`, T-12) — reforça por assinatura, não por
    convenção, a ordem do grafo da §11.10 (`RF-27`). Uma chamada que
    omita o argumento, ou que o passe na posição errada com tipo
    incompatível (ex.: passar `perfil` como primeiro argumento), é rejeitada
    pelo `mypy --strict` antes de rodar.
    """
    # 1º — BAIXA: qualquer (OU) das quatro condições basta. A primeira delas
    # é o próprio NIVEL_CONTROLE já derivado (Definições §5) — por isso ele
    # entra como parâmetro, não é recalculado aqui.
    baixa = (
        nivel_controle is NIVEL_CONTROLE.FRAGIL
        or perfil.DEFASAGEM_REGISTRO in (DEFASAGEM_REGISTRO.FIM_MES, DEFASAGEM_REGISTRO.SEM_PADRAO)
        or perfil.COBERTURA_PEQUENOS_GASTOS
        in (COBERTURA_PEQUENOS_GASTOS.QUASE_NENHUM, COBERTURA_PEQUENOS_GASTOS.NAO_ENTRAM)
        or perfil.COBERTURA_MEIOS_PAGAMENTO
        in (COBERTURA_MEIOS_PAGAMENTO.PARCIAL, COBERTURA_MEIOS_PAGAMENTO.NAO_SEI)
    )
    if baixa:
        return CONFIABILIDADE_DADOS.BAIXA

    # 2º — ALTA: todas (E) as quatro condições precisam ser satisfeitas.
    alta = (
        nivel_controle is NIVEL_CONTROLE.FORTE
        and perfil.DEFASAGEM_REGISTRO in (DEFASAGEM_REGISTRO.NA_HORA, DEFASAGEM_REGISTRO.MESMO_DIA)
        and perfil.COBERTURA_PEQUENOS_GASTOS
        in (COBERTURA_PEQUENOS_GASTOS.TODOS, COBERTURA_PEQUENOS_GASTOS.MAIORIA)
        and perfil.COBERTURA_MEIOS_PAGAMENTO
        in (COBERTURA_MEIOS_PAGAMENTO.TOTAL, COBERTURA_MEIOS_PAGAMENTO.QUASE_TOTAL)
    )
    if alta:
        return CONFIABILIDADE_DADOS.ALTA

    # 3º — MEDIA: todos os demais casos (fallback, garante função total).
    return CONFIABILIDADE_DADOS.MEDIA


def derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
    nivel_controle: NIVEL_CONTROLE,
    risco_recaida: NIVEL_RISCO,
    sinais: SinaisComportamentais,
    parametros: Parametros,
) -> bool:
    """Definições §1 (`BURACO-05`) — RF-24, AC-34, AC-35.

    ```
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE =
        NECESSIDADE_VITORIA >= P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA
        E
        (HISTORICO_ABANDONO = SIM OU RISCO_RECAIDA = ALTO OU NIVEL_CONTROLE = FRAGIL)
    ```

    Conjunção obrigatória entre dois grupos — nenhum basta sozinho
    (Definições §1): `NECESSIDADE_VITORIA` alta sem nenhum sinal
    comportamental não basta (`AC-35`); sinal comportamental isolado sem
    `NECESSIDADE_VITORIA` alta também não basta.

    `nivel_controle` e `risco_recaida` são parâmetros **obrigatórios e já
    derivados** — mesma trava de assinatura de `derivar_CONFIABILIDADE_DADOS`
    (T-13) e `classificar_RISCO_COMPORTAMENTAL_GERAL` (T-16): reforça por
    tipo, não por convenção, a ordem do grafo da §11.10/`RF-27`
    (`NIVEL_CONTROLE` → ... → `RISCO_RECAIDA` (D.4) → esta função).

    `NECESSIDADE_VITORIA` desconhecida não pode satisfazer `>=` o limiar —
    tratada como abaixo do limiar (RF-16: dado desconhecido não vira
    estimativa nem risco fabricado). O limiar vem de
    `Parametros.numero("P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA")` — nunca
    literal no código (AC-17, trava de implementação da Definições §1).
    """
    limiar = parametros.numero("P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA")
    necessidade_vitoria_alta = (
        sinais.NECESSIDADE_VITORIA is not DESCONHECIDO
        and sinais.NECESSIDADE_VITORIA >= limiar
    )

    algum_sinal_comportamental = (
        sinais.HISTORICO_ABANDONO is SimNaoTalvez.SIM
        or risco_recaida is NIVEL_RISCO.ALTO
        or nivel_controle is NIVEL_CONTROLE.FRAGIL
    )

    return necessidade_vitoria_alta and algum_sinal_comportamental
