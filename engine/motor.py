"""Ponto de entrada único do motor — `calcular_plano` · RF-01, RF-10, RF-12,
RF-27, RF-33 · §5 do plano técnico (`plans/motor-calculo.plan.md`) · T-68,
T-88.

`calcular_plano(estado, parametros, anterior, evento, motivo)` é a ÚNICA
função pública que um chamador externo (CLI, API, `collection/`, `report/`)
precisa invocar para rodar o motor do início ao fim. Ela orquestra os 11
passos do fluxo de dados da §5 do plano, na ordem exata ali descrita — nenhum
passo é pulado, nenhuma ordem é inventada:

```
1.  Carga de parâmetros — já responsabilidade do CHAMADOR: a assinatura
    recebe `parametros: Parametros` pronto (§4 do plano: `FonteParametros.
    carregar(versao)` acontece FORA desta função — ErroParametros é erro de
    carga, não de cálculo). Esta função não lê arquivo nem rede.
2.  Validação estrutural do EstadoFinanceiro — já garantida por construção:
    `EstadoFinanceiro`/`Divida` são `frozen=True, slots=True` (T-08) e
    tipados por `mypy --strict`; não há ponto de entrada que produza um
    `EstadoFinanceiro` com `float` ou tipo incoerente sem falhar antes de
    chegar aqui. Nada a repetir nesta função.
3.  Derivações comportamentais, em ordem obrigatória (RF-23, RF-24, RF-27,
    §11.10) — dentro de `calcular_diagnostico` (engine/diagnostico.py,
    T-24), que já implementa o grafo `NIVEL_CONTROLE -> CONFIABILIDADE_DADOS
    -> RISCO_RECAIDA/RISCO_COMPORTAMENTAL_GERAL -> INCOMPATIBILIDADE_
    COMPORTAMENTAL_GRAVE -> FATOR_SEGURANCA -> capacidades`.
4.  Diagnóstico e capacidade (RF-14, RF-25, RF-26) — mesma chamada acima.
5.  Modo estabilização (RF-15) — já embutido em `Diagnostico.
    MODO_ESTABILIZACAO`; o motor CONTINUA e devolve os cenários mesmo em
    déficit (marcados condicionais é responsabilidade do `report/`, fora
    deste slug).
6.  Gates 1-4 (RF-17) — `particionar_elegibilidade` (engine/gates.py, T-32),
    produzindo `elegiveis`, `ORDEM_ACOES` e `bloqueadas`. Em seguida, RF-33
    (T-88): quando `estado.ECONOMIA_POTENCIAL_IMEDIATA > 0`, a `AcaoRequerida`
    de economia (`TIPO_ACAO="ECONOMIA"`, `DIVIDA_ID=None`) é concatenada a
    `ORDEM_ACOES`, fora do fluxo de gates — `gates.py` opera por `Divida` e
    não recebe `EstadoFinanceiro` (§R2.5/§R2.6 do plano); emissão
    independente do estado dos gates de qualquer dívida (`EC-20`).
7.  Três cenários — `simular_cenario` (engine/ciclo_mensal.py, T-46) uma vez
    por método, com a `SelecionarAlvo` de cada fábrica (Avalanche T-49, Bola
    de Neve T-51, Híbrido T-53/T-54). Híbrido `NAO_APLICAVEL` (H-08/EC-03)
    não entra no mapa de cenários calculáveis — não rebaixa `STATUS_METODO`
    (S-02).
8.  Eventos futuros previstos (RF-22) — `NOVA_DIVIDA_PREVISTA` já é filtrado
    por construção: nenhuma função do motor promove a previsão a `Divida`
    (engine/eventos.py, ver docstring daquele módulo, "garantia dupla").
    Nada a fazer ativamente aqui além de não desviar desse contrato.
9.  Comparação (RF-19, RF-20) e status do método (RF-08) — `comparar_
    cenarios` (engine/comparacao.py, T-57/T-58) seguido de `derivar_
    METODO_RECOMENDADO_PIQ` (engine/status_metodo.py, T-61), que já compõe
    S-01/S-02/S-04/S-05/AC-09 sem duplicar lógica.
10. Ordem publicada (RF-09) — `publicar_ORDEM_QUITACAO` (engine/ordem.py,
    T-63) sobre o `Cenario` do método recomendado, seguida de `consolidar_
    ORDEM_STATUS` (T-64) a partir do benefício marginal real de cada dívida
    publicada.
11. Snapshot (RF-10) — `avaliar_gatilho_recalculo` (engine/eventos.py, T-66)
    decide `MOTIVO_RECALCULO`/auditoria do evento, e `montar_SnapshotOrdem`
    (engine/snapshot.py, T-67) carimba `ENGINE_VERSION`/`PARAMETROS_VERSION`
    (V-03, AC-16) e encadeia `snapshot_anterior_id`/`versao` (V-01).
```

**Fronteira de precisão (critério de aceite 1).** `localcontext(CONTEXTO_
MOTOR)` é aberto uma única vez, envolvendo TODA a execução — nunca herdado
do ambiente (§7 do plano, "State Management": "nunca herdado do ambiente (é
thread-local) — condição do determinismo"). Cada módulo interno já abre seu
próprio `localcontext(CONTEXTO_MOTOR)` pontualmente (`engine/precisao.py`,
`engine/ciclo_mensal.py`, ...), mas isso não é redundante nem contraditório:
`localcontext` é reentrante (um bloco aninhado dentro de outro com o MESMO
contexto não muda nada), e a fronteira externa aqui garante que MESMO
código que ainda não abrisse seu próprio bloco (ex.: a leitura de
`parametros.numero()` fora de qualquer `localcontext` interno) rode sob
`CONTEXTO_MOTOR`, nunca sob o contexto decimal padrão do processo/thread
chamador.

**Cache de trajetória (critério de aceite 3).** `limpar_cache_trajetoria()`
(engine/trajetoria.py, T-37) é chamada no INÍCIO desta função — antes de
qualquer simulação —, para que o cache `functools.cache` de `simular_
trajetoria_isolada` nunca carregue resíduo de uma chamada anterior de
`calcular_plano` no mesmo processo (mesma garantia de isolamento do
`localcontext`, ver docstring de `limpar_cache_trajetoria`). Chamar no
início (em vez de só no fim) também garante que uma execução que levante
`ErroInvariante` a meio caminho não deixe cache contaminado para trás.

**Pureza — sem relógio, sem rede, sem escrita em disco (critério de aceite
4).** `DATA_REFERENCIA` nunca é lida de `date.today()`: vem de `estado.
DATA_REFERENCIA`, repassada até o snapshot por `montar_SnapshotOrdem`. Esta
função não importa `RepositorioSnapshots`/`persistencia`, não chama
`anexar()` — persistência é responsabilidade exclusiva do CHAMADOR de
`calcular_plano` (T-69, fora do escopo desta tarefa), que decide se e quando
grava o `SnapshotOrdem` devolvido.

**Invariante violado propaga (critério de aceite 5).** `ErroInvariante`
(engine/ciclo_mensal.py, levantado dentro de `executar_mes`) nunca é
capturado por este módulo — nenhum `try/except` envolve as chamadas a
`simular_cenario`. Um invariante quebrado é bug do motor, não situação de
negócio a degradar silenciosamente: a exceção atravessa `calcular_plano`
inteira até o chamador.

REGRAS: RF-01, RF-10, RF-12, RF-27
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from decimal import localcontext
from typing import Final

from engine.ataque_imediato import (
    calcular_ATAQUE_IMEDIATO_RECOMENDADO,
    calcular_ATIVOS_RECOMENDADOS,
    calcular_CAIXA_RECOMENDADO,
    calcular_EXTRAORDINARIOS_RECOMENDADOS,
    calcular_INVESTIMENTOS_RECOMENDADOS,
    calcular_NECESSIDADE_RESIDUAL,
    derivar_RESERVA_RECOMENDADA,
)
from engine.beneficio_marginal import BeneficioMarginal, calcular_beneficio_marginal
from engine.ciclo_mensal import Cenario, simular_cenario
from engine.comparacao import comparar_cenarios
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.eventos import avaliar_gatilho_recalculo
from engine.gates import (
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
    AcaoRequerida,
    _compor_ACAO_ID,
    particionar_elegibilidade,
)
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido
from engine.ordem import consolidar_ORDEM_STATUS, publicar_ORDEM_QUITACAO
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.snapshot import SnapshotOrdem, montar_SnapshotOrdem
from engine.status_metodo import derivar_METODO_RECOMENDADO_PIQ
from engine.tipos import (
    CLASSIFICACAO_CENARIO,
    DESCONHECIDO,
    EVENTO_RECALCULO,
    METODO,
    Dinheiro,
    DinheiroTalvez,
)
from engine.trajetoria import limpar_cache_trajetoria
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO

REGRAS: Final[tuple[str, ...]] = (
    "RF-01",
    "RF-10",
    "RF-12",
    "RF-27",
    "RF-33",
    "RF-66",
    "RF-67",
    "RF-68",
    "§14.2.4",
)


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Inventário completo indexado por `DIVIDA_ID` — mesmo padrão já
    exercitado por `tests/gabaritos/test_gabarito_c_recomendacao.py` (T-65)
    e `tests/regras/test_snapshot.py` (T-67), agora dentro do próprio motor.
    Dívida sem `SALDO_DEVEDOR_ATUAL` conhecido não pode entrar em `simular_
    cenario` (RF-16, `ValueError` de `engine/ciclo_mensal.py`) — a triagem
    formal desse caso é Gate 1 (`INFORMACAO_PENDENTE`), não este helper.
    """
    return {
        divida.DIVIDA_ID: divida
        for divida in estado.dividas
        if divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
    }


def _beneficios_marginais_da_ordem(
    dividas: Mapping[str, Divida],
    cenario_recomendado: Cenario,
    capacidade_ataque_conservadora: Dinheiro,
    parametros: Parametros,
) -> dict[str, BeneficioMarginal]:
    """`BeneficioMarginal` real de cada dívida publicada em `ORDEM_QUITACAO`
    — insumo de `consolidar_ORDEM_STATUS` (T-64, AC-33). Mesmo `DELTA_TESTE_
    AVALANCHE = MIN(CAPACIDADE_ATAQUE_CONSERVADORA, VALOR_RELEVANTE_PARA_
    QUITACAO)` do ranqueamento normal da Avalanche (§11.1) — não é um delta
    de resíduo (que só existe intramês, dentro de `executar_mes`), porque
    aqui a pergunta é "essa dívida tem benefício marginal simulável?", não
    "quanto sobra para ela nesta rodada de cascata".

    Dívida cujo `VALOR_RELEVANTE_PARA_QUITACAO` é `DESCONHECIDO` não tem
    delta de teste computável — RF-16 proíbe estimar um substituto — e por
    isso não recebe entrada aqui; ela também nunca deveria estar publicada
    em `ORDEM_QUITACAO` nesse estado (Gate 1 já a desviaria antes).
    """
    beneficios: dict[str, BeneficioMarginal] = {}
    for divida_id in cenario_recomendado.ORDEM_QUITACAO:
        divida = dividas[divida_id]
        resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
        valor_relevante = resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO
        if valor_relevante is DESCONHECIDO:
            continue
        delta_teste = min(capacidade_ataque_conservadora, valor_relevante)
        beneficios[divida_id] = calcular_beneficio_marginal(divida, delta_teste, parametros)
    return beneficios


def _acao_economia_se_houver(estado: EstadoFinanceiro) -> AcaoRequerida | None:
    """RF-33, AC-53, AC-54, EC-20 · plano §R2.5 item 4 / §R2.6 — ponto de
    emissão da `AcaoRequerida` de economia, fora do fluxo de gates.

    `engine/gates.py` avalia gates por `Divida` e não recebe
    `EstadoFinanceiro`; a ação de economia não é sobre dívida nenhuma
    (`DIVIDA_ID=None`) e depende de `estado.ECONOMIA_POTENCIAL_IMEDIATA`, um
    campo de `EstadoFinanceiro` — por isso o ponto de emissão vive aqui, não
    em `particionar_elegibilidade`/`aplicar_gates_1_a_4` (`gates.py`), cuja
    assinatura não muda.

    `ECONOMIA_POTENCIAL_IMEDIATA > 0` emite a ação (`AC-53`); `= 0` é o caso
    comum, não uma falha, e não emite nada (`AC-54`), devolvendo `None`. A
    emissão é independente do estado dos gates de qualquer dívida (`EC-20`):
    esta função só lê `estado`, nunca `ParticaoElegibilidade`.
    """
    if estado.ECONOMIA_POTENCIAL_IMEDIATA <= dinheiro(0):
        return None
    tipo_acao = "ECONOMIA"
    motivo = (
        "ECONOMIA_POTENCIAL_IMEDIATA > 0 — há economia potencial imediata "
        "identificada fora do fluxo de dívidas (gastos fantasmas, B2.10A), "
        "ainda não capturada no orçamento (RF-33)."
    )
    return AcaoRequerida(
        ACAO_ID=_compor_ACAO_ID(divida_id=None, tipo_acao=tipo_acao),
        DIVIDA_ID=None,
        TIPO_ACAO=tipo_acao,
        descricao=motivo,
        gate_origem=None,
        # T-133 (RF-61/RF-62 · §14.2.1): TIPO_ACAO="ECONOMIA" não é ação de
        # dívida — a economia é comportamental, não uma compra, sem
        # desembolso.
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
        CAMPO_PENDENTE=None,
    )


def _compor_ATAQUE_IMEDIATO_RECOMENDADO(
    *,
    estado: EstadoFinanceiro,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,  # já calculada por calcular_diagnostico
    # (RF-43) — não recalcula.
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: DinheiroTalvez,  # fatia 4B — pode
    # ser DESCONHECIDO (EC-48/AC-108).
    RESULTADO_MENSAL_ATUAL: Dinheiro,  # já calculado por calcular_diagnostico.
) -> Dinheiro:
    """RF-66 · RF-67 · RF-68 · §14.2.4 · §13.3 · §13.9 — composição do
    `ATAQUE_IMEDIATO_RECOMENDADO` REAL, publicado no `Diagnostico` final do
    `SnapshotOrdem` (segunda passada, `T-142`). Esta função NÃO implementa
    nenhuma fórmula nova: só orquestra, na ordem do plano R4C.4.1, as sete
    funções já existentes de `engine/ataque_imediato.py` — `calcular_
    CAIXA_RECOMENDADO`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_
    EXTRAORDINARIOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS`, `calcular_
    NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`, `calcular_ATAQUE_
    IMEDIATO_RECOMENDADO`.

    `RESERVA_MOBILIZAVEL`/`RESULTADO_MENSAL_ATUAL` chegam POR PARÂMETRO, lidos
    de `diagnostico_pre` no ponto de chamada em `calcular_plano` — recomputá-
    los aqui chamando `calcular_diagnostico` de novo duplicaria trabalho puro
    sem necessidade e criaria uma segunda fonte de verdade (plano R4C.4.1,
    nota "Por que RESERVA_MOBILIZAVEL e RESULTADO_MENSAL_ATUAL entram por
    parâmetro").

    `verificar_hierarquia_ataque_imediato` NÃO é chamada aqui — mesma razão já
    documentada em `calcular_diagnostico` (T-114): exige `ATAQUE_IMEDIATO_
    POTENCIAL`, que não é campo de `Diagnostico` nesta rodada. Fora de escopo
    desta fatia.

    Pureza (spec §5): as quatro entradas chegam por parâmetro; nada é lido de
    `Diagnostico`, relógio, arquivo ou global.
    """
    # EC-48 — trava de propagação, avaliada PRIMEIRO: se
    # NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO, devolve
    # dinheiro(0) — mesmo padrão já usado por derivar_RESERVA_RECOMENDADA/
    # derivar_RESERVA_MOBILIZAVEL para "decisão/dado adiado ⇒ 0 documentado,
    # nunca fabricado como certeza". NÃO é EC-49 (elegível=0 real, soma
    # vazia) — a distinção entre "sei que é zero" (EC-49, Dinheiro) e "não
    # sei quanto é" (EC-48, DESCONHECIDO) é preservada até aqui; só a partir
    # deste ramo ela colapsa em 0, porque o tipo de saída (Dinheiro) não
    # admite propagar o desconhecido adiante. Nenhuma das demais seis
    # funções é chamada neste ramo.
    if NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO:
        return dinheiro(0)

    elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL

    CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=estado.DINHEIRO_DISPONIVEL)
    INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(
        investimentos=estado.investimentos
    )
    EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=estado.recursos_extraordinarios
    )
    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=estado.ativos)

    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
    )

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=RESULTADO_MENSAL_ATUAL,
    )

    return calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )


def calcular_plano(
    estado: EstadoFinanceiro,
    parametros: Parametros,
    anterior: SnapshotOrdem | None = None,
    evento: EVENTO_RECALCULO | None = None,
    motivo: str = "",
) -> SnapshotOrdem:
    """Ponto de entrada único do motor — §5 do plano, os 11 passos (ver
    docstring do módulo para o detalhamento passo a passo). Devolve o
    `SnapshotOrdem` calculado; NUNCA grava em disco, NUNCA chama `anexar()`
    (T-69, fora do escopo desta tarefa) — persistência é do chamador.

    `evento`/`motivo` são repassados tal como o chamador os obteve
    externamente (ex.: confirmação de quitação, evento material observado)
    — `avaliar_gatilho_recalculo` (engine/eventos.py, T-66) só AUDITA a
    decisão (R-05/EC-09: com evento, sempre versiona, mesmo que nada mude);
    ela não impede esta função de calcular — R-02/R-04 (não chamar sem
    evento e sem quitação) é responsabilidade do CHAMADOR, não desta função,
    que sempre calcula e devolve um snapshot quando invocada.
    """
    # Fronteira de precisão (critério de aceite 1) — todo o cálculo, do
    # início ao fim, roda sob CONTEXTO_MOTOR, nunca herdado do ambiente.
    with localcontext(CONTEXTO_MOTOR):
        # Cache de trajetória limpo ANTES de qualquer simulação (critério de
        # aceite 3) — nunca vaza resíduo de uma execução anterior no mesmo
        # processo, e uma falha a meio caminho não deixa cache contaminado.
        limpar_cache_trajetoria()

        # Passos 3-5: derivações comportamentais (RF-23, RF-24, RF-27,
        # §11.10) + diagnóstico/capacidade (RF-14, RF-25, RF-26) + modo
        # estabilização (RF-15) — tudo dentro de calcular_diagnostico.
        #
        # `diagnostico_pre` (RF-66/RF-68, OQ-44 decisão (2), T-142): ainda
        # carrega o placeholder de ATAQUE_IMEDIATO_RECOMENDADO — é
        # exatamente esse valor pré-composição que os passos 7-10
        # (simular_cenario × 3, comparar_cenarios, derivar_METODO_
        # RECOMENDADO_PIQ, publicar_ORDEM_QUITACAO, consolidar_ORDEM_STATUS)
        # consomem, sem reordenação: nenhum deles lê ATAQUE_IMEDIATO_
        # RECOMENDADO (R4C.1.2), então recompor o campo antes deles não
        # muda nenhum resultado que produzem — só adiaria sem necessidade
        # a segunda passada, que depende de particao/ORDEM_ACOES (abaixo).
        diagnostico_pre = calcular_diagnostico(estado, parametros)

        dividas = _inventario(estado)

        # Passo 6: Gates 1-4 (RF-17) — elegíveis, ORDEM_ACOES, bloqueadas.
        particao = particionar_elegibilidade(estado.dividas)

        # RF-33/AC-53/AC-54/EC-20: ação de economia, fora do fluxo de gates
        # (§R2.5 item 4 / §R2.6 do plano) — concatenada a particao.ORDEM_ACOES
        # antes de repassar para publicar_ORDEM_QUITACAO. Emissão
        # independente do estado dos gates de qualquer dívida (EC-20): esta
        # dataclasses.replace só acrescenta um item, nunca reordena nem
        # remove os já produzidos pelos gates.
        acao_economia = _acao_economia_se_houver(estado)
        if acao_economia is not None:
            particao = dataclasses.replace(
                particao, ORDEM_ACOES=(*particao.ORDEM_ACOES, acao_economia)
            )

        # Passo 7: os três cenários. Híbrido pode ser NAO_APLICAVEL (H-08/
        # EC-03) — nesse caso não entra no mapa de calculáveis (S-02: não
        # rebaixa STATUS_METODO). ErroInvariante de qualquer executar_mes()
        # PROPAGA sem ser capturado (critério de aceite 5) — nenhum
        # try/except envolve estas três chamadas.
        sel_avalanche = criar_selecionar_alvo_avalanche(dividas, parametros)
        cenario_avalanche = dataclasses.replace(
            simular_cenario(estado, diagnostico_pre, dividas, sel_avalanche, parametros),
            metodo=METODO.AVALANCHE,
        )

        sel_bola_de_neve = criar_selecionar_alvo_bola_de_neve(dividas, parametros)
        cenario_bola_de_neve = dataclasses.replace(
            simular_cenario(estado, diagnostico_pre, dividas, sel_bola_de_neve, parametros),
            metodo=METODO.BOLA_DE_NEVE,
        )

        resultado_hibrido = criar_selecionar_alvo_hibrido(
            estado, dividas, diagnostico_pre, parametros
        )
        cenarios_rotulados: tuple[Cenario, ...] = (cenario_avalanche, cenario_bola_de_neve)
        if (
            resultado_hibrido.classificacao is CLASSIFICACAO_CENARIO.CALCULAVEL
            and resultado_hibrido.selecionar_alvo is not None
        ):
            cenario_hibrido = dataclasses.replace(
                simular_cenario(
                    estado, diagnostico_pre, dividas, resultado_hibrido.selecionar_alvo, parametros
                ),
                metodo=METODO.HIBRIDO,
            )
            cenarios_rotulados = (*cenarios_rotulados, cenario_hibrido)

        cenarios_por_metodo = {
            cenario.metodo: cenario for cenario in cenarios_rotulados if cenario.metodo is not None
        }

        # Passo 8: NOVA_DIVIDA_PREVISTA já filtrada por construção (RF-22) —
        # nenhuma Divida hipotética chega a `dividas`/`cenarios_por_metodo`
        # acima; nada a fazer ativamente aqui (ver docstring do módulo).

        # Passo 9: comparação (RF-19, RF-20) + status/recomendação (RF-08).
        comparacao = comparar_cenarios(cenarios_rotulados, parametros)
        resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
            cenarios_por_metodo,
            comparacao,
            INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=diagnostico_pre.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
            INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
            parametros=parametros,
        )

        # Passo 10: ordem publicada (RF-09) sobre o cenário RECOMENDADO,
        # seguida da consolidação de ORDEM_STATUS (T-64, AC-33).
        cenario_recomendado = cenarios_por_metodo[resultado_recomendacao.METODO_RECOMENDADO_PIQ]
        ordem_publicada = publicar_ORDEM_QUITACAO(
            cenario_recomendado, resultado_recomendacao.METODO_RECOMENDADO_PIQ, dividas, particao
        )
        beneficios_marginais = _beneficios_marginais_da_ordem(
            dividas,
            cenario_recomendado,
            diagnostico_pre.CAPACIDADE_ATAQUE_CONSERVADORA,
            parametros,
        )
        resultado_status_ordem = consolidar_ORDEM_STATUS(
            INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
            beneficios_marginais=beneficios_marginais,
        )

        # Segunda passada de Diagnostico (RF-66/RF-68, OQ-44 decisão (2),
        # T-142, plano R4C.1/R4C.5) — posicionada DEPOIS da montagem final
        # de particao.ORDEM_ACOES (já inclui a ação de economia, se houver)
        # e ANTES de montar_SnapshotOrdem, nunca antes de particionar_
        # elegibilidade. acoes_por_divida filtra DIVIDA_ID is not None
        # (RF-68) — a ação de economia (DIVIDA_ID=None) não entra no
        # mapeamento por-dívida.
        acoes_por_divida = {
            acao.DIVIDA_ID: acao for acao in particao.ORDEM_ACOES if acao.DIVIDA_ID is not None
        }
        elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
            particao=particao, acoes_por_divida=acoes_por_divida
        )
        ataque_imediato_recomendado = _compor_ATAQUE_IMEDIATO_RECOMENDADO(
            estado=estado,
            RESERVA_MOBILIZAVEL=diagnostico_pre.RESERVA_MOBILIZAVEL,
            NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
            RESULTADO_MENSAL_ATUAL=diagnostico_pre.RESULTADO_MENSAL_ATUAL,
        )
        diagnostico = dataclasses.replace(
            diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=ataque_imediato_recomendado
        )

        # Passo 11: gatilho de recálculo (auditoria do evento, T-66) +
        # snapshot final carimbado e encadeado (RF-10, V-01..V-03, AC-16).
        gatilho = avaliar_gatilho_recalculo(evento)
        motivo_final = motivo if motivo else gatilho.motivo

        return montar_SnapshotOrdem(
            estado=estado,
            parametros=parametros,
            diagnostico=diagnostico,
            cenarios=cenarios_por_metodo,
            comparacao=comparacao,
            resultado_metodo=resultado_recomendacao,
            ordem_status=resultado_status_ordem.ORDEM_STATUS,
            ordem_publicada=ordem_publicada,
            evento=evento,
            motivo=motivo_final,
            anterior=anterior,
        )
