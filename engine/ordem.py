"""Publicação de `ORDEM_QUITACAO` com `JUSTIFICATIVA_POSICAO` — RF-09 ·
`Q-01..Q-05` · §7 · AC-18 · T-63.

Fórmula normativa (§7 da spec do slug, `RF-09`):

```
ORDEM_QUITACAO = sequência PROJETADA do Cenario do método RECOMENDADO
                 (METODO_RECOMENDADO_PIQ, T-61), NUNCA um ranqueamento
                 recalculado à parte por este módulo (Q-01, Q-04).
```

**Q-03/Q-04 — a ordem NÃO é recalculada aqui.** `Cenario.ORDEM_QUITACAO`
(`engine/ciclo_mensal.py::simular_cenario`, T-46) já é a sequência de
`DIVIDA_ID` efetivamente quitados, mês a mês, pelo `SelecionarAlvo` do
método recomendado (Avalanche/Bola de Neve/Híbrido — `T-49`/`T-51`/`T-53`).
`publicar_ORDEM_QUITACAO` apenas **envelopa** essa tupla já pronta em
`PosicaoOrdem`, uma por posição, na mesma ordem — nunca reordena, nunca
re-simula, nunca chama `calcular_beneficio_marginal`/
`compor_VALOR_RELEVANTE_PARA_QUITACAO` para DECIDIR a posição (só para
LER o número que já a explica, ver `_valores_de_apoio` abaixo). `Q-02`: o
rótulo "projetada" é vocabulário do `report/` (fora deste slug); a
variável interna permanece `ORDEM_QUITACAO`, sem renomear.

**Q-05 — `JUSTIFICATIVA_POSICAO` obrigatória, nunca vazia.** Cada
`PosicaoOrdem` carrega uma string técnica explicando por que aquela dívida
está naquela posição, de acordo com o critério do MÉTODO recomendado —
Avalanche ordena por maior `BENEFICIO_MARGINAL_AMORTIZACAO` (`O-01`),
Bola de Neve por menor `VALOR_RELEVANTE_PARA_QUITACAO` (`O-04`), Híbrido
por `D*` seguida de Avalanche event-driven das restantes (`H-05`..`H-07`).
A justificativa é para AUDITORIA INTERNA do revisor humano — texto
técnico/estruturado citando o ID normativo, nunca prosa polida de usuário
final (critério de aceite 5 de `T-63`; redigir para o usuário é escopo de
um módulo `relatorio/` futuro, ainda não implementado neste projeto).

**`valores_de_apoio` — os números que produziram a posição, para o
revisor refazer a conta manualmente (critério de aceite 2).** Não é só
texto: são os campos `Decimal`/`Dinheiro` REAIS já modelados em `Divida`
que alimentam o critério do método — `SALDO_DEVEDOR_ATUAL`,
`VALOR_RELEVANTE_PARA_QUITACAO` (lido via
`compor_VALOR_RELEVANTE_PARA_QUITACAO`, T-27 — mesma função pura que
qualquer um dos três métodos já usa para SABER o valor, não para ordenar)
e, para a Avalanche, também `TAXA_EFETIVA_MENSAL_NORMALIZADA`/`CET` (as
duas grandezas de que `BENEFICIO_MARGINAL_AMORTIZACAO` deriva, §11.1).
Valor `DESCONHECIDO` nunca entra em `valores_de_apoio` (RF-16: não
inventar dado) — apenas os campos efetivamente conhecidos daquela dívida
são incluídos no mapa.

**Critério de aceite 4 — dívida bloqueada por gate não aparece em
`ORDEM_QUITACAO`.** `Cenario.ORDEM_QUITACAO` (a sequência simulada) já é
produzida por `simular_cenario` a partir do inventário FILTRADO para
elegíveis (`ParticaoElegibilidade.elegiveis`, `engine/gates.py`, T-32) —
uma dívida bloqueada nunca entra nessa simulação, então nunca aparece na
tupla de origem. Este módulo reforça a garantia com uma checagem
defensiva: se algum `DIVIDA_ID` do cenário coincidir com um `DIVIDA_ID`
de `particao.bloqueadas`, é erro do motor (`ErroOrdemInconsistente`),
nunca publicado silenciosamente. `ORDEM_ACOES` é repassada tal como
`particionar_elegibilidade` (T-32) a produziu — fila PARALELA, nunca a
`ORDEM_QUITACAO` (§11.3: "`ORDEM_ACOES` é fila PARALELA. Nunca é a
`ORDEM_QUITACAO`.").

**`consolidar_ORDEM_STATUS` — T-64, RF-21, RF-16, AC-09, AC-33.** A
`ORDEM_QUITACAO` publicada só é `ORDEM_STATUS.DEFINITIVA_NA_DATA` quando
TODAS as condições da descrição de `T-64` são verdadeiras simultaneamente:

1. `INVENTARIO_COMPLETO = True` — nenhum dado faltante na carteira
   (`AC-09`, `RF-16`). "Dado material pendente que possa alterar a
   decisão" (terceira condição da descrição de `T-64`) É a mesma condição:
   `INVENTARIO_COMPLETO` já é o booleano que resume, para o snapshot
   inteiro, se existe dívida com `DIVIDA_STATUS_ESTRATEGICO =
   INFORMACAO_PENDENTE` (§6/Definições §1, `engine/estado.py`,
   `EstadoFinanceiro.INVENTARIO_COMPLETO`) — não há uma terceira fonte de
   dado distinta a consultar aqui; duplicar o cálculo seria recalcular uma
   regra que já pertence a outro módulo (mesma trava de composição de
   `derivar_STATUS_METODO`/`AC-09`, `engine/status_metodo.py`, T-60).
2. Nenhuma dívida presente na ordem publicada usa fallback de benefício
   marginal — TODA dívida tem `BeneficioMarginal.origem == "SIMULACAO"`
   (`AC-33`). A regra UNITÁRIA (dado o `origem` de UMA dívida, qual
   `ORDEM_STATUS` ela sozinha implicaria) já está pronta em
   `determinar_ordem_status_por_origem` (`engine/beneficio_marginal.py`,
   T-40) — `consolidar_ORDEM_STATUS` não a duplica, apenas ITERA os
   benefícios recebidos e reusa aquela função por dívida, agregando pelo
   pior caso (qualquer `origem != "SIMULACAO"` contamina a ordem inteira).

Consolidação = pior caso entre as duas causas, nunca cumulativa em um
terceiro nível: não existe status "mais rebaixado que `PROVISORIA`" nesta
tarefa (mesmo espírito de `AC-09` em `derivar_STATUS_METODO`). Cada causa
de rebaixamento gera um motivo textual nomeado em
`ResultadoConsolidacaoOrdemStatus.motivos_rebaixamento` — nunca um
rebaixamento silencioso (critério de aceite 4 de `T-64`), mesmo padrão de
`ResultadoStatusMetodo.motivos` (`engine/status_metodo.py`, T-60).
`consolidar_ORDEM_STATUS` é uma função dedicada, separada de
`publicar_ORDEM_QUITACAO` (que não recebe `INVENTARIO_COMPLETO` nem
benefícios marginais e não deveria passar a receber só para isso) —
mesma decisão de composição já tomada em `ResultadoMetodoRecomendado`
sobre `ResultadoStatusMetodo` (T-60→T-61): um dataclass novo que
representa uma consolidação adicional, não uma extensão do dataclass que
já existia com outro propósito (`ResultadoOrdemPublicada` é o ENVELOPE da
ordem — Q-01..Q-05 — e continua sem saber nada de `ORDEM_STATUS`).

REGRAS: RF-09, RF-21, RF-16, Q-01, Q-02, Q-03, Q-04, Q-05, AC-09, AC-18, AC-33
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.beneficio_marginal import BeneficioMarginal, determinar_ordem_status_por_origem
from engine.ciclo_mensal import Cenario
from engine.estado import Divida
from engine.gates import AcaoRequerida, ParticaoElegibilidade
from engine.tipos import DESCONHECIDO, METODO, ORDEM_STATUS, Dinheiro
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO

REGRAS: Final[tuple[str, ...]] = (
    "RF-09",
    "RF-21",
    "RF-16",
    "Q-01",
    "Q-02",
    "Q-03",
    "Q-04",
    "Q-05",
    "AC-09",
    "AC-18",
    "AC-33",
)

_DESCRICAO_CRITERIO: Final[Mapping[METODO, str]] = {
    METODO.AVALANCHE: (
        "maior BENEFICIO_MARGINAL_AMORTIZACAO entre as dívidas elegíveis "
        "restantes no momento em que esta dívida foi selecionada (O-01)"
    ),
    METODO.BOLA_DE_NEVE: (
        "menor VALOR_RELEVANTE_PARA_QUITACAO entre as dívidas elegíveis "
        "restantes no momento em que esta dívida foi selecionada, com "
        "desempate O-05 (O-04)"
    ),
    METODO.HIBRIDO: (
        "seleção do método Híbrido: D_ESTRELA prioritária seguida de "
        "Avalanche event-driven das restantes (H-05, H-06, H-07)"
    ),
}


class ErroOrdemInconsistente(Exception):
    """Levantado quando `Cenario.ORDEM_QUITACAO` contém um `DIVIDA_ID`
    também presente em `ParticaoElegibilidade.bloqueadas` — critério de
    aceite 4 de `T-63`: dívida bloqueada por gate nunca pode aparecer na
    ordem publicada. Não deveria ser alcançável em uso normal (`simular_
    cenario` já opera só sobre `elegiveis`), mas o motor não publica uma
    inconsistência em silêncio — mesmo espírito de `engine/ciclo_mensal.
    py::ErroInvariante`.
    """


@dataclass(frozen=True, slots=True)
class PosicaoOrdem:
    """Um item de `ORDEM_QUITACAO` publicada — §4 do plano técnico, `Q-05`.

    `JUSTIFICATIVA_POSICAO` é OBRIGATÓRIA e nunca vazia (critério de
    aceite 1). `valores_de_apoio` traz os números `Decimal`/`Dinheiro`
    reais que sustentam a posição, não apenas texto (critério de aceite
    2) — chaves em pt-BR, mesmas variáveis da spec canônica.
    """

    posicao: int
    DIVIDA_ID: str
    JUSTIFICATIVA_POSICAO: str
    valores_de_apoio: Mapping[str, Dinheiro | Decimal]


@dataclass(frozen=True, slots=True)
class ResultadoOrdemPublicada:
    """Saída de `publicar_ORDEM_QUITACAO` — `T-63`.

    `ORDEM_QUITACAO` é a sequência projetada do cenário recomendado,
    envelopada em `PosicaoOrdem`. `ORDEM_ACOES` é repassada tal como
    `ParticaoElegibilidade` a produziu — fila paralela, nunca fundida com
    `ORDEM_QUITACAO` (critério de aceite 4, §11.3).
    """

    ORDEM_QUITACAO: tuple[PosicaoOrdem, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]


def _valores_de_apoio(divida: Divida, metodo: METODO) -> dict[str, Dinheiro | Decimal]:
    """Números concretos que sustentam a posição desta dívida, para o
    revisor refazer a conta manualmente (critério de aceite 2). Só LÊ
    campos já existentes em `Divida` (mais `VALOR_RELEVANTE_PARA_QUITACAO`,
    via a mesma função pura que os três métodos usam para conhecer o
    valor) — nunca decide ou recalcula a posição (`Q-04`). `DESCONHECIDO`
    nunca entra no mapa (RF-16).
    """
    valores: dict[str, Dinheiro | Decimal] = {}

    if divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO:
        valores["SALDO_DEVEDOR_ATUAL"] = divida.SALDO_DEVEDOR_ATUAL

    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    if resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO is not DESCONHECIDO:
        valores["VALOR_RELEVANTE_PARA_QUITACAO"] = (
            resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO
        )

    if metodo is METODO.AVALANCHE:
        # §11.1: BENEFICIO_MARGINAL_AMORTIZACAO deriva da taxa efetiva (ou,
        # em fallback, do CET) — os dois números que o revisor precisa para
        # refazer a comparação entre dívidas concorrentes.
        if divida.TAXA_EFETIVA_MENSAL_NORMALIZADA is not DESCONHECIDO:
            valores["TAXA_EFETIVA_MENSAL_NORMALIZADA"] = divida.TAXA_EFETIVA_MENSAL_NORMALIZADA
        if divida.CET is not DESCONHECIDO:
            valores["CET"] = divida.CET

    if metodo is METODO.BOLA_DE_NEVE:
        # O-05: cadeia de desempate — valores concretos, mesma leitura já
        # adotada por engine/metodos/bola_de_neve.py (PAGAMENTO_MENSAL_
        # EFETIVO como VALOR_FLUXO_LIBERADO da dívida, TAXA como custo
        # financeiro).
        if divida.PAGAMENTO_MENSAL_EFETIVO is not DESCONHECIDO:
            valores["PAGAMENTO_MENSAL_EFETIVO"] = divida.PAGAMENTO_MENSAL_EFETIVO
        if divida.TAXA_EFETIVA_MENSAL_NORMALIZADA is not DESCONHECIDO:
            valores["TAXA_EFETIVA_MENSAL_NORMALIZADA"] = divida.TAXA_EFETIVA_MENSAL_NORMALIZADA
        if divida.PESO_EMOCIONAL is not DESCONHECIDO:
            valores["PESO_EMOCIONAL"] = Decimal(divida.PESO_EMOCIONAL)

    return valores


def _justificativa(posicao: int, divida_id: str, metodo: METODO) -> str:
    """`Q-05`: string técnica, sempre não vazia. Cita a posição, o
    `DIVIDA_ID` e o critério normativo do método recomendado — texto de
    auditoria interna, não prosa de usuário final (critério de aceite 5).
    """
    criterio = _DESCRICAO_CRITERIO[metodo]
    return (
        f"Posição {posicao}: {divida_id} — método {metodo.value}, critério: "
        f"{criterio}."
    )


def publicar_ORDEM_QUITACAO(
    cenario_recomendado: Cenario,
    metodo_recomendado: METODO,
    dividas: Mapping[str, Divida],
    particao: ParticaoElegibilidade,
) -> ResultadoOrdemPublicada:
    """`RF-09` · `Q-01..Q-05` — publica `ORDEM_QUITACAO` a partir da
    sequência JÁ PROJETADA de `cenario_recomendado.ORDEM_QUITACAO`
    (`Cenario` do método `METODO_RECOMENDADO_PIQ`, `T-61`).

    **Nunca recalcula um ranqueamento à parte (critério de aceite 3).**
    `cenario_recomendado` é recebido pronto — produzido por
    `simular_cenario` (`engine/ciclo_mensal.py`, T-46) com o
    `SelecionarAlvo` do método recomendado já injetado por quem chama esta
    função. Este módulo apenas itera `cenario_recomendado.ORDEM_QUITACAO`
    na mesma ordem e monta uma `PosicaoOrdem` por item.

    `dividas` é o inventário completo indexado por `DIVIDA_ID` (mesmo
    padrão de `engine/ciclo_mensal.py`/`engine/metodos/*`), usado só para
    LER os campos que compõem `valores_de_apoio` — nunca para decidir
    posição. `particao` é a saída de `particionar_elegibilidade`
    (`engine/gates.py`, T-32): `particao.ORDEM_ACOES` é repassada tal
    como veio (fila paralela) e `particao.bloqueadas` alimenta a checagem
    defensiva de `ErroOrdemInconsistente` (critério de aceite 4).
    """
    ids_bloqueados = {resultado.DIVIDA_ID for resultado in particao.bloqueadas}

    posicoes: list[PosicaoOrdem] = []
    for indice, divida_id in enumerate(cenario_recomendado.ORDEM_QUITACAO, start=1):
        if divida_id in ids_bloqueados:
            # Critério de aceite 4: nunca publicar uma dívida bloqueada por
            # gate dentro de ORDEM_QUITACAO — falha ruidosa, não silenciosa
            # (mesmo espírito de ErroInvariante em engine/ciclo_mensal.py).
            raise ErroOrdemInconsistente(
                f"{divida_id}: presente em Cenario.ORDEM_QUITACAO e também em "
                "ParticaoElegibilidade.bloqueadas — dívida bloqueada por gate "
                "não pode ser publicada na ordem de ataque (critério de "
                "aceite 4 de T-63)."
            )

        divida = dividas[divida_id]
        posicoes.append(
            PosicaoOrdem(
                posicao=indice,
                DIVIDA_ID=divida_id,
                JUSTIFICATIVA_POSICAO=_justificativa(indice, divida_id, metodo_recomendado),
                valores_de_apoio=_valores_de_apoio(divida, metodo_recomendado),
            )
        )

    return ResultadoOrdemPublicada(
        ORDEM_QUITACAO=tuple(posicoes),
        ORDEM_ACOES=particao.ORDEM_ACOES,
    )


@dataclass(frozen=True, slots=True)
class ResultadoConsolidacaoOrdemStatus:
    """Saída de `consolidar_ORDEM_STATUS` — `T-64`, `RF-21`, `RF-16`,
    `AC-09`, `AC-33`.

    `ORDEM_STATUS` é o resumo final para a `ORDEM_QUITACAO` inteira;
    `motivos_rebaixamento` é a tupla de auditoria de todo rebaixamento
    aplicado — mesmo padrão de `ResultadoStatusMetodo.motivos`
    (`engine/status_metodo.py`, T-60). Vazia quando `ORDEM_STATUS =
    DEFINITIVA_NA_DATA`: nada rebaixou. `frozen=True, slots=True` — sem
    setter, sem campo mutável, `ORDEM_STATUS` sempre DERIVADO (mesma trava
    estrutural de `ResultadoStatusMetodo`/`ResultadoOrdemPublicada`).
    """

    ORDEM_STATUS: ORDEM_STATUS
    motivos_rebaixamento: tuple[str, ...]


def consolidar_ORDEM_STATUS(
    *,
    INVENTARIO_COMPLETO: bool,
    beneficios_marginais: Mapping[str, BeneficioMarginal],
) -> ResultadoConsolidacaoOrdemStatus:
    """`T-64` · `RF-21` · `RF-16` · `AC-09` · `AC-33` — consolida
    `ORDEM_STATUS` para a `ORDEM_QUITACAO` inteira a partir de duas causas
    independentes de rebaixamento. Função pura: sempre recalcula do zero a
    partir das entradas, nunca um valor atribuído por fora.

    `ORDEM_STATUS = DEFINITIVA_NA_DATA` exige TODAS as condições
    simultaneamente:

    1. `INVENTARIO_COMPLETO = True` (`AC-09`, `RF-16`) — nenhum dado
       faltante na carteira. Cobre também "dado material pendente que
       possa alterar a decisão" (terceira condição da descrição de
       `T-64`): é a MESMA condição, não uma checagem adicional — ver
       docstring do módulo.
    2. Nenhuma dívida em `beneficios_marginais` usa fallback: TODA dívida
       tem `origem == "SIMULACAO"` (`AC-33`). A regra unitária por dívida
       é reusada de `determinar_ordem_status_por_origem`
       (`engine/beneficio_marginal.py`, T-40) — esta função não a
       duplica, apenas agrega pelo pior caso entre todas as dívidas: UMA
       única dívida com `origem != "SIMULACAO"` já contamina a ordem
       inteira (a consolidação é o PIOR caso, nunca uma média ou maioria).

    Se qualquer condição falhar, `ORDEM_STATUS = PROVISORIA` e cada causa
    de rebaixamento entra como uma string nomeada em
    `motivos_rebaixamento` — nunca um rebaixamento silencioso (critério de
    aceite 4 de `T-64`). `beneficios_marginais` é o mapa `DIVIDA_ID ->
    BeneficioMarginal` de TODAS as dívidas efetivamente presentes na
    `ORDEM_QUITACAO` publicada (tipicamente `ResultadoOrdemPublicada.
    ORDEM_QUITACAO`, uma entrada por `PosicaoOrdem.DIVIDA_ID`) — dívida
    bloqueada por gate não entra aqui pelo mesmo motivo por que não entra
    em `ORDEM_QUITACAO` (critério de aceite 4 de `T-63`).
    """
    motivos: list[str] = []

    if not INVENTARIO_COMPLETO:
        # AC-09/RF-16: carteira com dado faltante em algum ponto impede
        # DEFINITIVA_NA_DATA, mesmo que toda dívida da ordem tenha
        # BeneficioMarginal.origem == SIMULACAO.
        motivos.append(
            "INVENTARIO_COMPLETO = False — carteira de dívidas com informação "
            "faltante em algum ponto (dado material pendente); ORDEM_STATUS "
            "rebaixado a PROVISORIA (AC-09, RF-16)."
        )

    for divida_id, beneficio in beneficios_marginais.items():
        if determinar_ordem_status_por_origem(beneficio.origem) is ORDEM_STATUS.PROVISORIA:
            # AC-33: origem != SIMULACAO em QUALQUER dívida da ordem
            # contamina o resultado inteiro — reusa a regra unitária de
            # T-40, não a recalcula.
            motivos.append(
                f"{divida_id}: BeneficioMarginal.origem = {beneficio.origem!r} "
                "(!= SIMULACAO) — fallback de benefício marginal usado nesta "
                "dívida rebaixa a ORDEM_QUITACAO inteira a PROVISORIA (AC-33)."
            )

    if motivos:
        return ResultadoConsolidacaoOrdemStatus(
            ORDEM_STATUS=ORDEM_STATUS.PROVISORIA,
            motivos_rebaixamento=tuple(motivos),
        )

    return ResultadoConsolidacaoOrdemStatus(
        ORDEM_STATUS=ORDEM_STATUS.DEFINITIVA_NA_DATA,
        motivos_rebaixamento=(),
    )
