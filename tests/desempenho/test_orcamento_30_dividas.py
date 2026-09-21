"""Orçamento de desempenho — 30 dívidas × 120 meses · RF-05 · RF-07 · T-77.

Marcador PRÓPRIO (`@pytest.mark.desempenho`), fora da suíte padrão (`gabarito`,
`invariante`, `regra`) — não é um gabarito numérico nem uma prova de
invariante, é uma medição de tempo. Dois testes:

1. `test_orcamento_30_dividas_120_meses` — monta uma carteira SINTÉTICA de 30
   dívidas (dado representativo, variado em saldo/taxa/tipo — não um gabarito
   com números publicados na spec) e roda `calcular_plano` ponta a ponta (os
   três métodos mais a derivação de recomendação completa, RF-01..RF-10) sobre
   ela, com `P_HORIZONTE_MAXIMO_SIMULACAO = 10` anos = 120 meses (mesmo
   parâmetro `1.0.1` usado pelos gabaritos, sem override — 120 meses É o
   horizonte-padrão declarado na fonte de parâmetros de referência). Mede o
   tempo total com `time.perf_counter()` e verifica que fica dentro do
   orçamento de 10 s declarado pela NFR (`pyproject.toml`, marcador
   `desempenho`: "orçamento de tempo da NFR de 30 dívidas × 10 anos"). O tempo
   medido é sempre impresso (`print`, capturado por `pytest -s` ou visível no
   relatório de falha) — nunca só comparado e descartado.

2. `test_cache_trajetoria_nao_altera_resultado_GAB_C` — prova que o cache
   `functools.cache` de `simular_trajetoria_isolada` (`engine/trajetoria.py`,
   T-37) é uma otimização pura, sem efeito no resultado: roda `GAB-C` completo
   (a carteira PEQUENA de 3 dívidas — não a sintética de 30 usada no teste de
   orçamento) duas vezes via `calcular_plano`, uma com o cache livre para
   memoizar normalmente, outra forçando recomputação a cada chamada (mesma
   `ChaveTrajetoria` nunca reaproveitada: cache limpo antes de cada simulação
   via monkeypatch em `simular_trajetoria_isolada`, chamando diretamente
   `_simular_trajetoria_isolada_sem_cache`). Compara os `SnapshotOrdem`
   resultantes campo a campo nos campos numericamente relevantes:
   `CUSTO_FUTURO_TOTAL`, `PRAZO_TOTAL` (lidos de
   `cenarios[METODO_RECOMENDADO_PIQ]`), `ORDEM_QUITACAO` (sequência de
   `DIVIDA_ID`) e `METODO_RECOMENDADO_PIQ`.

**Por que a carteira sintética não é uma fixture JSON em `tests/fixtures/`.**
`tests/fixtures/gab_c.json`/`carregar.py` existem para os gabaritos NORMATIVOS
(`GAB-A`, `GAB-B`, `GAB-C`, com números publicados na spec canônica, seção
10). A carteira de 30 dívidas desta tarefa não tem contrapartida na spec — é
puramente sintética, gerada em código com o mesmo padrão de `Divida`/
`EstadoFinanceiro` sintéticos já usado por `tests/regras/test_avalanche.py`/
`test_diagnostico.py` (`_divida`/`_estado` locais), não merece arquivo próprio
em `tests/fixtures/` (que é reservado a dado com proveniência normativa).

REGRAS: RF-05, RF-07
"""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import pytest

from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_RESERVA,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_DIVIDA,
    TIPO_RENDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from engine.tipos import CONFIABILIDADE_DADOS, STATUS_DIVIDA, STATUS_VALIDADE_PROPOSTA, SimNaoTalvez
from engine.trajetoria import (
    ChaveTrajetoria,
    Trajetoria,
    _simular_trajetoria_isolada_sem_cache,
    limpar_cache_trajetoria,
    simular_trajetoria_isolada,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c

ORCAMENTO_SEGUNDOS: Decimal = Decimal("10")  # NFR declarada — pyproject.toml, marcador "desempenho"

_PERFIL_NEUTRO = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)

_SINAIS_NEUTROS = SinaisComportamentais(
    NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
    MECANISMO_DEFICIT=frozenset(),
    HISTORICO_RECAIDA=SimNaoTalvez.NAO,
    NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
    PACTO="ESTABELECIDO",
    RISCO_IMPULSO="NENHUMA",
    LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
    NECESSIDADE_VITORIA=0,  # neutro: não dispara INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE
    HISTORICO_ABANDONO=SimNaoTalvez.NAO,
    JANELA_NOVA_DIVIDA=None,
)

# Rotação de TIPO_DIVIDA para variar o perfil da carteira sintética — domínio
# fechado de engine/estado.py, sem inventar valor fora dele.
_TIPOS_EM_ROTACAO = (
    TIPO_DIVIDA.CONSIGNADO,
    TIPO_DIVIDA.CARTAO_ROTATIVO,
    TIPO_DIVIDA.FIN_VEICULO,
    TIPO_DIVIDA.PESSOAL,
    TIPO_DIVIDA.CHEQUE_ESPECIAL,
)


def _divida_sintetica(indice: int) -> Divida:
    """Uma dívida da carteira sintética de 30, variada em saldo/taxa/tipo por
    `indice` (0..29) — dado representativo, não gabarito com números
    publicados na spec. `QUITACAO_CONSULTADA=SIM`/`STATUS_VALIDADE_PROPOSTA=
    VIGENTE` com `VALOR_QUITACAO_HOJE == SALDO_DEVEDOR_ATUAL` (mesmo padrão de
    `tests/regras/test_avalanche.py::_divida`) para que `VALOR_RELEVANTE_
    PARA_QUITACAO` seja determinístico, sem cair no fallback de §11.2.

    Saldo varia de R$ 1.000 a R$ 14.100 (passo de R$ 500), taxa mensal de
    0,5% a 5,3% (passo de 0,1 p.p.), pagamento mínimo como 5% do saldo
    (arredondado a inteiro de reais) — garante que toda dívida amortiza
    (pagamento sempre cobre os juros do mês, mesmo na taxa mais alta) e
    quita dentro do horizonte de 120 meses.
    """
    saldo = dinheiro(1000 + indice * 500)
    taxa = Decimal("0.005") + Decimal("0.001") * indice
    pagamento = dinheiro(int(saldo) * 5 // 100 + 50)  # >= 5% do saldo + piso fixo
    return Divida(
        DIVIDA_ID=f"D{indice + 1:03d}",
        TIPO_DIVIDA=_TIPOS_EM_ROTACAO[indice % len(_TIPOS_EM_ROTACAO)],
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=taxa,
        CET=taxa,
        PARCELA_CONTRATUAL=pagamento,
        PAGAMENTO_MENSAL_EFETIVO=pagamento,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro(0),
        PESO_EMOCIONAL=indice % 11,  # varia 0..10, cobre toda a escala O-05/H-04
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _carteira_sintetica_30_dividas() -> EstadoFinanceiro:
    """`EstadoFinanceiro` sintético com 30 dívidas variadas — renda e
    capacidade de ataque generosas o bastante para que os três métodos e a
    recomendação completa sejam CALCULÁVEIS (nenhuma dívida cai em déficit
    puro), exercitando o caminho normal do motor ponta a ponta.
    """
    dividas = tuple(_divida_sintetica(i) for i in range(30))
    return EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 9, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("25000"),
        TIPO_RENDA=TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("10000"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("500"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("4000"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=dividas,
        perfil_comportamental=_PERFIL_NEUTRO,
        sinais_comportamentais=_SINAIS_NEUTROS,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=5,
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro("0"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro("0"),
        DINHEIRO_DISPONIVEL=dinheiro("0"),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )


@pytest.mark.desempenho
def test_orcamento_30_dividas_120_meses() -> None:
    """Critérios de aceite 1 e 3 de T-77: 30 dívidas × 120 meses (`P_HORIZONTE_
    MAXIMO_SIMULACAO = 10` anos, parâmetro `1.0.1` sem override) via
    `calcular_plano` ponta a ponta (os três métodos + recomendação, RF-01..
    RF-10) roda em <= 10 s no ambiente de referência — tempo REAL medido e
    IMPRESSO, não apenas comparado internamente.
    """
    estado = _carteira_sintetica_30_dividas()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    assertar_exato(parametros.numero("P_HORIZONTE_MAXIMO_SIMULACAO"), Decimal("10"))  # 120 meses

    inicio = time.perf_counter()
    snapshot = calcular_plano(estado, parametros)
    tempo_decorrido = Decimal(str(time.perf_counter() - inicio))

    mensagem = (
        f"orçamento de desempenho estourado: 30 dívidas × 120 meses levou "
        f"{tempo_decorrido:.3f}s, orçamento declarado é {ORCAMENTO_SEGUNDOS}s"
    )
    print(
        f"\n[T-77] 30 dívidas × 120 meses: {tempo_decorrido:.3f}s "
        f"(orçamento {ORCAMENTO_SEGUNDOS}s)"
    )
    assert tempo_decorrido <= ORCAMENTO_SEGUNDOS, mensagem

    # Prova mínima de que o cálculo real de fato rodou (não um no-op) — o
    # snapshot tem um método recomendado e ao menos uma dívida publicada.
    assert snapshot.METODO_RECOMENDADO_PIQ is not None
    assert snapshot.ORDEM_QUITACAO, (
        "carteira sintética de 30 dívidas não deveria produzir ORDEM_QUITACAO vazia"
    )


@pytest.mark.desempenho
def test_cache_trajetoria_nao_altera_resultado_GAB_C(monkeypatch: pytest.MonkeyPatch) -> None:
    """Critério de aceite 2 de T-77: `GAB-C` (a carteira PEQUENA de 3 dívidas,
    não a sintética de 30) produz o MESMO `SnapshotOrdem` com o cache de
    `simular_trajetoria_isolada` ligado e desligado — a memoização
    (`functools.cache`, T-37) é otimização pura, sem efeito no resultado.

    "Desligado" aqui significa: cada chamada força recomputação chamando
    diretamente `_simular_trajetoria_isolada_sem_cache` (a versão pura sem
    cache) em vez do wrapper memoizado — via monkeypatch de `engine.trajetoria
    .simular_trajetoria_isolada`, que é o único símbolo importado por
    `engine/beneficio_marginal.py` (o único consumidor real da trajetória
    isolada dentro do motor).
    """
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    limpar_cache_trajetoria()
    snapshot_com_cache = calcular_plano(estado, parametros)

    def _sempre_recomputa(chave: ChaveTrajetoria) -> Trajetoria:
        # Nunca consulta nem povoa o cache — cada chamada é uma recomputação
        # completa e independente pela função pura, provando que o resultado
        # não depende de memoização.
        return _simular_trajetoria_isolada_sem_cache(chave)

    monkeypatch.setattr("engine.beneficio_marginal.simular_trajetoria_isolada", _sempre_recomputa)
    limpar_cache_trajetoria()
    snapshot_sem_cache = calcular_plano(estado, parametros)

    _assertar_snapshots_equivalentes(snapshot_com_cache, snapshot_sem_cache)

    # Confirma que o wrapper memoizado real (fora do monkeypatch) segue
    # importável e utilizável — a substituição acima foi só no ponto de
    # consumo, não uma quebra do módulo.
    assert simular_trajetoria_isolada is not None


def _assertar_snapshots_equivalentes(a: SnapshotOrdem, b: SnapshotOrdem) -> None:
    """Compara os campos numericamente relevantes citados no critério de
    aceite 2 de T-77: `CUSTO_FUTURO_TOTAL`, `PRAZO_TOTAL` (do cenário do
    método recomendado), `ORDEM_QUITACAO` (sequência de `DIVIDA_ID`) e
    `METODO_RECOMENDADO_PIQ`. Tolerância ZERO em todos — inclusive no
    monetário: cache ligado/desligado deve produzir o valor IDÊNTICO
    (mesma conta, mesma precisão `Decimal`, nenhuma diferença de
    arredondamento entre os dois caminhos), não apenas "dentro de ± R$
    0,05" (`assertar_monetario` seria tolerância errada aqui — a pergunta
    não é "é o mesmo dentro da tolerância de homologação", é "é o MESMO
    valor").
    """
    assertar_exato(a.METODO_RECOMENDADO_PIQ, b.METODO_RECOMENDADO_PIQ)

    cenario_a = a.cenarios[a.METODO_RECOMENDADO_PIQ]
    cenario_b = b.cenarios[b.METODO_RECOMENDADO_PIQ]
    assertar_exato(cenario_a.PRAZO_TOTAL, cenario_b.PRAZO_TOTAL)
    assertar_exato(cenario_a.CUSTO_FUTURO_TOTAL, cenario_b.CUSTO_FUTURO_TOTAL)

    ordem_a = tuple(posicao.DIVIDA_ID for posicao in a.ORDEM_QUITACAO)
    ordem_b = tuple(posicao.DIVIDA_ID for posicao in b.ORDEM_QUITACAO)
    assertar_exato(ordem_a, ordem_b)
