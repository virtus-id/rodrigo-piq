"""Benefício marginal de amortização — RF-05, RF-21 · §11.1 · AC-19, AC-33.

Fórmula normativa (§11.1 da spec do slug):

```
DELTA_TESTE_AVALANCHE = MIN(CAPACIDADE_ATAQUE_CONSERVADORA,
                            VALOR_RELEVANTE_PARA_QUITACAO)
```

Para cada dívida elegível, simular isoladamente duas trajetórias: **A** sem
pagamento extraordinário; **B** com `DELTA_TESTE_AVALANCHE` aplicado agora.
Então:

```
BENEFICIO_MARGINAL_AMORTIZACAO = (DESEMBOLSO_FUTURO_SEM_DELTA
                               −  DESEMBOLSO_FUTURO_COM_DELTA)
                               ÷  DELTA_REALMENTE_APLICADO
```

**Esta função é genérica — T-39.** `calcular_beneficio_marginal` recebe
`delta_disponivel` como parâmetro externo; ela NUNCA deriva
`CAPACIDADE_ATAQUE_CONSERVADORA` nem lê `Diagnostico` por conta própria. Quem
decide qual delta usar é o CHAMADOR:

- Ranqueamento normal da Avalanche (T-49, `engine/metodos/avalanche.py`):
  `delta_disponivel = MIN(CAPACIDADE_ATAQUE_CONSERVADORA,
  VALOR_RELEVANTE_PARA_QUITACAO)` — o `DELTA_TESTE_AVALANCHE` da fórmula
  acima.
- Reranqueamento intramês do resíduo (T-43, "Exceção intramês" da §11.1,
  `AC-14`): `delta_disponivel = MIN(RESIDUO_ATAQUE_M,
  VALOR_RELEVANTE_PARA_QUITACAO)` — NUNCA a capacidade cheia (`A-03`).

O nome do campo `BeneficioMarginal.DELTA_TESTE_AVALANCHE` reflete o USO mais
comum (ranqueamento normal da Avalanche) — mas o valor armazenado é sempre o
parâmetro `delta_disponivel` recebido, seja ele o delta normal ou o delta de
resíduo. Não há um segundo campo para o caso de resíduo: o mesmo dataclass
serve aos dois chamadores, com o mesmo nome.

**Horizonte da simulação.** `ChaveTrajetoria.HORIZONTE` é derivado aqui, o
único lugar autorizado, a partir de `Parametros.numero(
"P_HORIZONTE_MAXIMO_SIMULACAO")` (anos) × 12 — nunca um valor fixo embutido
(RF-13/AC-17). A conversão `Decimal → int` usa `int(Decimal)` (truncamento
exato, nunca passa por `float`) porque `ChaveTrajetoria.HORIZONTE: Meses` é
`int` por contrato (`engine/trajetoria.py`).

**Detecção de insimulabilidade e fallback (§11.1 "Fallback", RF-21, AC-33).**
Se `SALDO_DEVEDOR_ATUAL`, `TAXA_EFETIVA_MENSAL_NORMALIZADA` ou
`PAGAMENTO_MENSAL_EFETIVO` for `DESCONHECIDO`, a simulação nem pode começar —
`ChaveTrajetoria` exige os três como `Dinheiro`/`Taxa` concretos. Se os três
estiverem presentes mas uma das duas trajetórias (A ou B) estourar o
horizonte (`ESTOUROU_HORIZONTE=True` — dívida que não amortiza
deterministicamente dentro de `P_HORIZONTE_MAXIMO_SIMULACAO`), o resultado
também não é confiável como benefício marginal. Em ambos os casos:
`BENEFICIO_MARGINAL_AMORTIZACAO = DESCONHECIDO` e aplica-se o fallback: 1º
`TAXA_EFETIVA_MENSAL_NORMALIZADA` (`origem="FALLBACK_TAXA"`); 2º `CET`
comparável (`origem="FALLBACK_CET"`).

**Uso da taxa como substituto do benefício marginal — decisão de
implementação, fonte ambígua.** A §11.1 diz apenas "aplica-se o fallback: 1º
TAXA_EFETIVA_MENSAL_NORMALIZADA; 2º CET comparável", sem prescrever se o
valor numérico da taxa substitui diretamente `BENEFICIO_MARGINAL_AMORTIZACAO`
(que é R$ retornado por R$ investido, não uma taxa percentual) ou se serve
apenas para ORDENAR as dívidas em fallback. As duas grandezas são
conceitualmente distintas — a fonte não resolve essa distinção. Decisão
adotada aqui: `BENEFICIO_MARGINAL_AMORTIZACAO` recebe o valor NUMÉRICO da
taxa (`Decimal`) diretamente como proxy ordenável. Justificativa: (a) a
Avalanche ordena "do maior benefício marginal para o menor" — uma taxa mais
alta represents mais custo evitado por real amortizado, então preserva a
mesma direção de ordenação que o benefício marginal genuíno; (b) não introduz
um segundo campo/contrato que o plano (`§4`, bloco `BeneficioMarginal`) não
previu — `BENEFICIO_MARGINAL_AMORTIZACAO: Decimal | Desconhecido` já
comporta um `Decimal` de qualquer origem; (c) o valor não é reportado como
R$/R$ genuíno em nenhum lugar que dependa de proporção monetária exata —
`origem != "SIMULACAO"` já sinaliza ao consumidor (e ao `ORDEM_STATUS =
PROVISORIA`, AC-33) que o número é um substituto, não uma simulação
completa. Se esta leitura divergir da intenção do especialista, é uma
decisão registrada aqui, não definitiva — reportar para confirmação segue a
trava da §6 do `sdd.config.md` ("metodologia não se decide implementando").

**Caso extremo sem fallback possível — extensão do `Literal`.** Se
`TAXA_EFETIVA_MENSAL_NORMALIZADA` e `CET` também forem `DESCONHECIDO`, a
dívida fica sem benefício marginal algum: nenhum número, simulado ou
substituto, pode ser produzido (RF-16: nunca estimar). O plano (§4) fecha
`origem: Literal["SIMULACAO", "FALLBACK_TAXA", "FALLBACK_CET"]`, sem prever
esse caso. Adicionado um quarto valor, `"INDISPONIVEL"`, para tornar esse
estado representável sem forçar um dos três valores existentes a mentir sobre
a origem do (não-)cálculo. Esta função apenas sinaliza `origem="INDISPONIVEL"`
com `BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO` — não decide o que
acontece a seguir. Documentado (fora do escopo desta função): uma dívida
nesse estado provavelmente deveria ser desviada para `INFORMACAO_PENDENTE`
via Gate 1 (`engine/gates.py`, já implementado em T-29 — "a falta apenas da
simulação marginal não bloqueia, SE o fallback for possível"; aqui o
fallback NÃO é possível, então o Gate 1 é o mecanismo natural de bloqueio,
mas aplicá-lo é responsabilidade do chamador de gates, não desta função).

**`DELTA_REALMENTE_APLICADO` — pode ser menor que `delta_disponivel`.**
`simular_trajetoria_isolada` já limita, internamente, o pagamento efetivo do
primeiro mês a `min(PAGAMENTO_MENSAL_EFETIVO + DELTA, saldo_apos_juros)`
(`engine/trajetoria.py`): se `delta_disponivel` for maior que o saldo restante
da dívida (após o juro do primeiro mês), não faz sentido dizer que todo o
delta foi "aplicado" — o excedente nunca chegou a sair do caixa dentro desta
trajetória. Como `Trajetoria` não expõe o pagamento do primeiro mês
isoladamente, esta função replica o mesmo cálculo (saldo × (1+taxa), depois
`min` contra o pagamento nominal) só para DERIVAR `DELTA_REALMENTE_APLICADO`
— não para simular; a simulação em si continua inteiramente dentro de
`simular_trajetoria_isolada`. `DELTA_REALMENTE_APLICADO = max(0,
pagamento_efetivo_mes1_B − PAGAMENTO_MENSAL_EFETIVO)`, nunca negativo (se o
pagamento normal sozinho já bastava para quitar a dívida no primeiro mês, o
delta não contribuiu em nada).

**Divisão por zero.** Se `DELTA_REALMENTE_APLICADO == 0` (tipicamente porque
`delta_disponivel` era zero — nenhuma capacidade de ataque disponível para
testar), a fórmula normativa não pode ser avaliada: dividir por zero é
indefinido, e inventar um benefício marginal fabricado violaria a trava
"não inventar dado" (§4 do `sdd.config.md`, RF-16). Decisão: quando isso
ocorre e as duas trajetórias fecharam (nenhuma estourou horizonte, dados
completos), `origem` permanece `"SIMULACAO"` — a simulação em si funcionou
perfeitamente, só não há divisor válido — e
`BENEFICIO_MARGINAL_AMORTIZACAO = DESCONHECIDO`. Esse caso é distinto do
fallback por insuficiência de DADO (RF-21/§11.1): aqui o dado está completo,
só não há capacidade de ataque a testar. Não é o caso coberto por
`AC-33`/`ORDEM_STATUS = PROVISORIA` (esse cobre insuficiência de dado, não
ausência de capacidade), então manter `origem="SIMULACAO"` evita rebaixar a
ordem por um motivo que a `§11.1`/`AC-33` não previu.

**`ORDEM_STATUS = PROVISORIA` quando `origem != SIMULACAO` — T-40.** AC-33
fecha a regra em uma frase: "a ordem fica `PROVISORIA`" sempre que o
fallback (taxa ou `CET`) foi usado em vez da simulação. `ORDEM_STATUS` é
campo de `Cenario`/`SnapshotOrdem` (plano `§4`), que ainda não existem
(`T-46`, `T-67`) — o mesmo vale para a consolidação entre `ORDEM_STATUS` e
`INVENTARIO_COMPLETO` sobre a ordem inteira, que é escopo de `T-64`
("Consolidar `ORDEM_STATUS` entre `DEFINITIVA_NA_DATA` e `PROVISORIA`",
`engine/ordem.py`). O que **esta** tarefa isola é só a metade que já é
decidível com a informação que `calcular_beneficio_marginal` produz: dado o
`origem` de UM `BeneficioMarginal`, ele por si só já basta para rebaixar a
ordem inteira a `PROVISORIA` (AC-33 não exige nenhuma outra condição além de
"o fallback foi usado"). `determinar_ordem_status_por_origem` abaixo
encapsula exatamente essa regra unitária — pura função de `origem`, sem
acessar `Cenario` nem iterar dívidas. Agregar sobre uma coleção de
`BeneficioMarginal` (ou combinar com `INVENTARIO_COMPLETO`, que é uma causa
DIFERENTE de rebaixamento — `AC-09`, T-64) é responsabilidade do chamador em
T-64: com `any(b.origem != "SIMULACAO" for b in beneficios)` mais
`determinar_ordem_status_por_origem`, ou equivalente, ele monta o resultado
final sem que este módulo precise saber o que é um `Cenario`.

REGRAS: RF-05, RF-21, AC-19, AC-33, §11.1
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final, Literal

from engine.estado import Divida
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import DESCONHECIDO, ORDEM_STATUS, Desconhecido, Dinheiro
from engine.trajetoria import ChaveTrajetoria, simular_trajetoria_isolada

REGRAS: Final[tuple[str, ...]] = ("RF-05", "RF-21", "AC-19", "AC-33", "§11.1")

# AC-33 fecha o domínio em três valores; "INDISPONIVEL" é extensão desta
# implementação para o caso extremo em que nem simulação nem fallback são
# possíveis (ver docstring do módulo, "Caso extremo sem fallback possível").
OrigemBeneficioMarginal = Literal["SIMULACAO", "FALLBACK_TAXA", "FALLBACK_CET", "INDISPONIVEL"]


@dataclass(frozen=True, slots=True)
class BeneficioMarginal:
    """Saída de `calcular_beneficio_marginal` — §4 do plano, §11.1, AC-19, AC-33.

    Carrega os dois desembolsos (`DESEMBOLSO_FUTURO_SEM_DELTA`,
    `DESEMBOLSO_FUTURO_COM_DELTA`) para que o revisor humano refaça a conta
    da fórmula sem precisar rodar a simulação de novo (NFR "Auditabilidade").
    """

    DIVIDA_ID: str
    DELTA_TESTE_AVALANCHE: Dinheiro  # = delta_disponivel recebido (ver docstring do módulo)
    DELTA_REALMENTE_APLICADO: Dinheiro
    DESEMBOLSO_FUTURO_SEM_DELTA: Dinheiro
    DESEMBOLSO_FUTURO_COM_DELTA: Dinheiro
    BENEFICIO_MARGINAL_AMORTIZACAO: Decimal | Desconhecido
    origem: OrigemBeneficioMarginal  # AC-33


def _horizonte_em_meses(p: Parametros) -> int:
    """`P_HORIZONTE_MAXIMO_SIMULACAO` está em ANOS na fonte de parâmetros —
    converte para meses (×12). `int(Decimal)` trunca exato, sem passar por
    `float` (RF-12): o parâmetro é um inteiro de anos por natureza (10), a
    conversão nunca perde precisão.
    """
    anos = p.numero("P_HORIZONTE_MAXIMO_SIMULACAO")
    return int(anos) * 12


def _pagamento_efetivo_mes1(
    saldo_inicial: Dinheiro, taxa: Dinheiro, pagamento_nominal: Dinheiro
) -> Dinheiro:
    """Replica o cálculo do primeiro mês de `simular_trajetoria_isolada`
    (`engine/trajetoria.py::_simular_trajetoria_isolada_sem_cache`) só para
    DERIVAR quanto do pagamento nominal foi de fato absorvido — não para
    simular. Ver docstring do módulo, "DELTA_REALMENTE_APLICADO".
    """
    with localcontext(CONTEXTO_MOTOR):
        saldo_apos_juros = saldo_inicial * (dinheiro(1) + taxa)
        pagamento_efetivo = min(pagamento_nominal, saldo_apos_juros)
        if pagamento_efetivo < dinheiro(0):
            pagamento_efetivo = dinheiro(0)
        return pagamento_efetivo


def _delta_realmente_aplicado(
    saldo_inicial: Dinheiro,
    taxa: Dinheiro,
    pagamento_mensal_efetivo: Dinheiro,
    delta_disponivel: Dinheiro,
) -> Dinheiro:
    """`DELTA_REALMENTE_APLICADO = max(0, pagamento_efetivo_mes1_B −
    PAGAMENTO_MENSAL_EFETIVO)` — nunca maior que `delta_disponivel` (a
    trajetória nunca absorve mais do que o nominal oferecido) e nunca
    negativo (ver docstring do módulo).
    """
    with localcontext(CONTEXTO_MOTOR):
        pagamento_nominal_b = pagamento_mensal_efetivo + delta_disponivel
        efetivo_b = _pagamento_efetivo_mes1(saldo_inicial, taxa, pagamento_nominal_b)
        aplicado = efetivo_b - pagamento_mensal_efetivo
        if aplicado < dinheiro(0):
            aplicado = dinheiro(0)
        return aplicado


def _fallback(
    d: Divida,
    delta_disponivel: Dinheiro,
    desembolso_sem_delta: Dinheiro,
    desembolso_com_delta: Dinheiro,
    delta_aplicado: Dinheiro,
) -> BeneficioMarginal:
    """RF-21/§11.1: 1º `TAXA_EFETIVA_MENSAL_NORMALIZADA`; 2º `CET`; senão
    `"INDISPONIVEL"` (extensão desta implementação — ver docstring do
    módulo). Os desembolsos simulados (quando existirem) continuam sendo
    carregados no resultado para auditoria, mesmo quando não sustentam a
    fórmula — eles são o que motivou o fallback (ex.: estouro de horizonte).
    """
    if d.TAXA_EFETIVA_MENSAL_NORMALIZADA is not DESCONHECIDO:
        return BeneficioMarginal(
            DIVIDA_ID=d.DIVIDA_ID,
            DELTA_TESTE_AVALANCHE=delta_disponivel,
            DELTA_REALMENTE_APLICADO=delta_aplicado,
            DESEMBOLSO_FUTURO_SEM_DELTA=desembolso_sem_delta,
            DESEMBOLSO_FUTURO_COM_DELTA=desembolso_com_delta,
            BENEFICIO_MARGINAL_AMORTIZACAO=d.TAXA_EFETIVA_MENSAL_NORMALIZADA,
            origem="FALLBACK_TAXA",
        )
    if d.CET is not DESCONHECIDO:
        return BeneficioMarginal(
            DIVIDA_ID=d.DIVIDA_ID,
            DELTA_TESTE_AVALANCHE=delta_disponivel,
            DELTA_REALMENTE_APLICADO=delta_aplicado,
            DESEMBOLSO_FUTURO_SEM_DELTA=desembolso_sem_delta,
            DESEMBOLSO_FUTURO_COM_DELTA=desembolso_com_delta,
            BENEFICIO_MARGINAL_AMORTIZACAO=d.CET,
            origem="FALLBACK_CET",
        )
    # Nem simulação, nem taxa, nem CET: caso extremo — ver docstring do
    # módulo, "Caso extremo sem fallback possível".
    return BeneficioMarginal(
        DIVIDA_ID=d.DIVIDA_ID,
        DELTA_TESTE_AVALANCHE=delta_disponivel,
        DELTA_REALMENTE_APLICADO=delta_aplicado,
        DESEMBOLSO_FUTURO_SEM_DELTA=desembolso_sem_delta,
        DESEMBOLSO_FUTURO_COM_DELTA=desembolso_com_delta,
        BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO,
        origem="INDISPONIVEL",
    )


def calcular_beneficio_marginal(
    d: Divida, delta_disponivel: Dinheiro, p: Parametros
) -> BeneficioMarginal:
    """§11.1 · AC-19 · AC-33 · RF-05 · RF-21.

    `delta_disponivel` é sempre parâmetro do CHAMADOR — esta função NUNCA lê
    `CAPACIDADE_ATAQUE_CONSERVADORA` nem qualquer outra capacidade por conta
    própria (ver docstring do módulo). No ranqueamento normal da Avalanche
    (T-49), o chamador passa `MIN(CAPACIDADE_ATAQUE_CONSERVADORA,
    VALOR_RELEVANTE_PARA_QUITACAO)`; no reranqueamento intramês do resíduo
    (T-43, AC-14), passa `MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE_PARA_QUITACAO)`.
    """
    saldo = d.SALDO_DEVEDOR_ATUAL
    taxa = d.TAXA_EFETIVA_MENSAL_NORMALIZADA
    pagamento = d.PAGAMENTO_MENSAL_EFETIVO

    # Insimulabilidade por dado ausente: `ChaveTrajetoria` exige os três
    # campos como Dinheiro/Taxa concretos — sem eles, a simulação nem começa.
    if saldo is DESCONHECIDO or taxa is DESCONHECIDO or pagamento is DESCONHECIDO:
        return _fallback(
            d,
            delta_disponivel,
            desembolso_sem_delta=dinheiro(0),
            desembolso_com_delta=dinheiro(0),
            delta_aplicado=dinheiro(0),
        )

    horizonte = _horizonte_em_meses(p)

    chave_a = ChaveTrajetoria(
        DIVIDA_ID=d.DIVIDA_ID,
        SALDO_DEVEDOR_ATUAL=saldo,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=taxa,
        PAGAMENTO_MENSAL_EFETIVO=pagamento,
        DELTA=dinheiro(0),
        HORIZONTE=horizonte,
    )
    chave_b = ChaveTrajetoria(
        DIVIDA_ID=d.DIVIDA_ID,
        SALDO_DEVEDOR_ATUAL=saldo,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=taxa,
        PAGAMENTO_MENSAL_EFETIVO=pagamento,
        DELTA=delta_disponivel,
        HORIZONTE=horizonte,
    )

    trajetoria_a = simular_trajetoria_isolada(chave_a)
    trajetoria_b = simular_trajetoria_isolada(chave_b)

    # Insimulabilidade por estouro de horizonte: dívida que não amortiza
    # deterministicamente dentro de P_HORIZONTE_MAXIMO_SIMULACAO (EC-13,
    # OQ-19). Aplica-se o fallback com os desembolsos parciais para
    # auditoria (o quanto foi simulado até o estouro).
    if trajetoria_a.ESTOUROU_HORIZONTE or trajetoria_b.ESTOUROU_HORIZONTE:
        delta_aplicado = _delta_realmente_aplicado(saldo, taxa, pagamento, delta_disponivel)
        return _fallback(
            d,
            delta_disponivel,
            desembolso_sem_delta=trajetoria_a.DESEMBOLSO_FUTURO,
            desembolso_com_delta=trajetoria_b.DESEMBOLSO_FUTURO,
            delta_aplicado=delta_aplicado,
        )

    # As duas trajetórias fecharam: origem = SIMULACAO (AC-33).
    delta_aplicado = _delta_realmente_aplicado(saldo, taxa, pagamento, delta_disponivel)

    if delta_aplicado == dinheiro(0):
        # Divisão por zero indefinida — ver docstring do módulo. A
        # simulação em si é válida; só não há divisor. Não é o caso de
        # AC-33 (insuficiência de DADO), então origem permanece SIMULACAO.
        return BeneficioMarginal(
            DIVIDA_ID=d.DIVIDA_ID,
            DELTA_TESTE_AVALANCHE=delta_disponivel,
            DELTA_REALMENTE_APLICADO=delta_aplicado,
            DESEMBOLSO_FUTURO_SEM_DELTA=trajetoria_a.DESEMBOLSO_FUTURO,
            DESEMBOLSO_FUTURO_COM_DELTA=trajetoria_b.DESEMBOLSO_FUTURO,
            BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO,
            origem="SIMULACAO",
        )

    with localcontext(CONTEXTO_MOTOR):
        # AC-19: fórmula normativa exata.
        beneficio = (
            trajetoria_a.DESEMBOLSO_FUTURO - trajetoria_b.DESEMBOLSO_FUTURO
        ) / delta_aplicado

    return BeneficioMarginal(
        DIVIDA_ID=d.DIVIDA_ID,
        DELTA_TESTE_AVALANCHE=delta_disponivel,
        DELTA_REALMENTE_APLICADO=delta_aplicado,
        DESEMBOLSO_FUTURO_SEM_DELTA=trajetoria_a.DESEMBOLSO_FUTURO,
        DESEMBOLSO_FUTURO_COM_DELTA=trajetoria_b.DESEMBOLSO_FUTURO,
        BENEFICIO_MARGINAL_AMORTIZACAO=beneficio,
        origem="SIMULACAO",
    )


def determinar_ordem_status_por_origem(origem: OrigemBeneficioMarginal) -> ORDEM_STATUS:
    """AC-33 · RF-21 · T-40: `origem != "SIMULACAO"` ⇒ `ORDEM_STATUS =
    PROVISORIA`.

    Escopo desta função — ver docstring do módulo, "`ORDEM_STATUS =
    PROVISORIA`...". Ela decide a regra unitária a partir do `origem` de UMA
    dívida; não agrega uma coleção de `BeneficioMarginal` nem conhece
    `INVENTARIO_COMPLETO` (`AC-09`) — a consolidação sobre a ordem inteira,
    combinando as duas causas de rebaixamento, é `T-64`
    (`engine/ordem.py`). `"INDISPONIVEL"` (extensão desta implementação,
    ver "Caso extremo sem fallback possível") também rebaixa: é ainda mais
    distante de `"SIMULACAO"` do que qualquer fallback, então cai no mesmo
    ramo `!= "SIMULACAO"` sem necessidade de caso especial.
    """
    if origem != "SIMULACAO":
        return ORDEM_STATUS.PROVISORIA
    return ORDEM_STATUS.DEFINITIVA_NA_DATA
