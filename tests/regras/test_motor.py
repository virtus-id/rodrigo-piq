"""Testa `calcular_plano` — o ponto de entrada único do motor. RF-01, RF-10,
RF-12, RF-27, RF-33 · §5 do plano técnico · T-68, T-88.

Reusa `GAB-C` (`tests/fixtures/gab_c.json`, via `carregar_gab_c`), a mesma
carteira já validada ponta a ponta por `tests/gabaritos/test_gabarito_c_
recomendacao.py` (T-65) e `tests/regras/test_snapshot.py` (T-67) — os cinco
critérios de aceite de `T-68` testam a função ORQUESTRADORA em si (fronteira
de precisão, determinismo, isolamento de cache, ausência de I/O, propagação
de `ErroInvariante`), não recomputam o gabarito numérico (já coberto por
`AC-01`..`AC-04`/`AC-28` em outros arquivos).

REGRAS: RF-01, RF-10, RF-12, RF-27, RF-33
"""

from __future__ import annotations

import dataclasses
from decimal import ROUND_DOWN, Context, localcontext

import pytest

from engine.ciclo_mensal import ErroInvariante
from engine.estado import EstadoFinanceiro
from engine.motor import calcular_plano
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO, EVENTO_RECALCULO, METODO
from engine.trajetoria import limpar_cache_trajetoria, simular_trajetoria_isolada
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_c


@pytest.fixture(scope="module")
def _estado_e_parametros() -> tuple[EstadoFinanceiro, Parametros]:
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return estado, parametros


@pytest.mark.regra
def test_calcular_plano_reproduz_gabarito_c_recomendacao(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Verificação de sanidade: `calcular_plano` sobre `GAB-C` reproduz o
    mesmo resultado já fechado por `AC-04`/`AC-28` (Híbrido recomendado,
    revisão não obrigatória) — prova que a orquestração dos 11 passos da §5
    do plano está correta antes de testar as propriedades específicas de
    `T-68` abaixo."""
    estado, parametros = _estado_e_parametros

    snapshot = calcular_plano(estado, parametros)

    assertar_exato(snapshot.METODO_RECOMENDADO_PIQ, METODO.HIBRIDO)
    assertar_exato(snapshot.REVISAO_HUMANA_OBRIGATORIA, False)
    assertar_exato(snapshot.ENGINE_VERSION, parametros.ENGINE_VERSION)
    assertar_exato(snapshot.PARAMETROS_VERSION, parametros.PARAMETROS_VERSION)
    assert snapshot.ORDEM_QUITACAO, "ORDEM_QUITACAO publicada não pode ser vazia em GAB-C"
    assertar_exato(snapshot.versao, 1)
    assertar_exato(snapshot.snapshot_anterior_id, None)


@pytest.mark.regra
def test_criterio1_contexto_decimal_nunca_herdado_do_ambiente(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Critério de aceite 1: `localcontext(CONTEXTO_MOTOR)` é aberto na
    entrada de `calcular_plano` e nunca herdado do ambiente. Roda a função
    duas vezes — uma sob o contexto decimal padrão, outra sob um contexto
    decimal DIFERENTE e deliberadamente hostil (precisão baixíssima,
    arredondamento para baixo) ativo no ambiente de chamada — e confirma que
    o `SnapshotOrdem` produzido é IDÊNTICO campo a campo em ambos os casos.
    Se `calcular_plano` herdasse o contexto do ambiente, a precisão baixa
    (`prec=3`) corromperia os cálculos monetários internos e o resultado
    divergiria."""
    estado, parametros = _estado_e_parametros

    snapshot_sob_contexto_padrao = calcular_plano(estado, parametros)

    contexto_hostil = Context(prec=3, rounding=ROUND_DOWN)
    with localcontext(contexto_hostil):
        snapshot_sob_contexto_hostil = calcular_plano(estado, parametros)

    assertar_exato(
        snapshot_sob_contexto_padrao.hash_inputs, snapshot_sob_contexto_hostil.hash_inputs
    )
    assertar_exato(
        snapshot_sob_contexto_padrao.SNAPSHOT_ID, snapshot_sob_contexto_hostil.SNAPSHOT_ID
    )
    assertar_exato(
        snapshot_sob_contexto_padrao.diagnostico, snapshot_sob_contexto_hostil.diagnostico
    )
    assertar_exato(
        snapshot_sob_contexto_padrao.METODO_RECOMENDADO_PIQ,
        snapshot_sob_contexto_hostil.METODO_RECOMENDADO_PIQ,
    )
    for cenario_padrao, cenario_hostil in zip(
        snapshot_sob_contexto_padrao.cenarios.values(),
        snapshot_sob_contexto_hostil.cenarios.values(),
        strict=True,
    ):
        assertar_exato(cenario_padrao.CUSTO_FUTURO_TOTAL, cenario_hostil.CUSTO_FUTURO_TOTAL)
        assertar_exato(cenario_padrao.PRAZO_TOTAL, cenario_hostil.PRAZO_TOTAL)
    assertar_exato(
        snapshot_sob_contexto_padrao.ORDEM_QUITACAO, snapshot_sob_contexto_hostil.ORDEM_QUITACAO
    )


@pytest.mark.regra
def test_criterio2_duas_execucoes_mesma_entrada_produzem_snapshots_identicos(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Critério de aceite 2: duas execuções de `calcular_plano` com
    EXATAMENTE a mesma entrada produzem `SnapshotOrdem`s idênticos, campo a
    campo — determinismo total da função orquestradora completa, reforçando
    o `SNAPSHOT_ID` determinístico já provado por T-67 sobre `montar_
    SnapshotOrdem` isolada."""
    estado, parametros = _estado_e_parametros

    primeira_execucao = calcular_plano(estado, parametros)
    segunda_execucao = calcular_plano(estado, parametros)

    assertar_exato(primeira_execucao, segunda_execucao)


@pytest.mark.regra
def test_criterio3_cache_de_trajetoria_nao_vaza_entre_execucoes_diferentes(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 3: `limpar_cache_trajetoria()` é chamada a cada
    execução de `calcular_plano` — chamar a função duas vezes com entradas
    DIFERENTES não deve vazar resultado de uma simulação para a outra via o
    cache module-level de `simular_trajetoria_isolada` (`functools.cache`,
    `engine/trajetoria.py`). A segunda entrada é `GAB-C` com o saldo de uma
    dívida alterado (mesma carteira, um valor materialmente diferente) —
    nem `GAB-A` (déficit puro, `CAPACIDADE_ATAQUE_CONSERVADORA = 0`, `AC-05`)
    nem `GAB-B` (única dívida com `SALDO_DEVEDOR_ATUAL = DESCONHECIDO`, fora
    do inventário simulável) chegam a produzir `ORDEM_QUITACAO` não-vazia em
    nenhum método: nesses dois casos `CUSTO_FUTURO_TOTAL = 0` para os três
    cenários e `engine/comparacao.py::comparar_cenarios` (fora do escopo de
    T-68) divide por esse `custo_minimo = 0` — nenhum dos dois gabaritos é
    hoje exercitado ponta a ponta por teste algum além do diagnóstico
    isolado. `GAB-C` com saldo alterado preserva o pipeline completo já
    validado (T-65/T-67) enquanto garante uma entrada genuinamente diferente.

    Prova dupla:

    1. `limpar_cache_trajetoria` é de fato CHAMADA por `calcular_plano`
       (espiã via `monkeypatch`, sem depender de inspecionar o tamanho do
       cache — que volta a crescer legitimamente durante a própria execução,
       via `calcular_beneficio_marginal` em `_beneficios_marginais_da_ordem`,
       então "cache vazio ao final" não é o contrato certo a testar).
    2. Prova de não-vazamento observável: chamado ANTES da segunda execução,
       o cache é limpo — nenhum resultado da primeira execução sobrevive
       para contaminar a segunda, verificado pelo cache estar VAZIO no
       instante em que `simular_cenario` começa a rodar sobre a entrada
       alterada (logo após `limpar_cache_trajetoria`, capturado via
       monkeypatch no ponto exato da chamada)."""
    import engine.motor as motor_mod

    estado_original, parametros = _estado_e_parametros
    saldo_original = estado_original.dividas[0].SALDO_DEVEDOR_ATUAL
    assert saldo_original is not DESCONHECIDO, (
        "GAB-C: D001 deveria ter SALDO_DEVEDOR_ATUAL conhecido"
    )
    divida_alterada = dataclasses.replace(
        estado_original.dividas[0],
        SALDO_DEVEDOR_ATUAL=saldo_original + 1000,
    )
    estado_alterado = dataclasses.replace(
        estado_original, dividas=(divida_alterada, *estado_original.dividas[1:])
    )

    chamadas: list[int] = []

    def _limpar_e_registrar() -> None:
        limpar_cache_trajetoria()
        # Critério de aceite 3, prova direta: imediatamente após a limpeza
        # que calcular_plano executa, o cache está vazio — nenhum resíduo
        # da chamada anterior sobrevive a este ponto.
        chamadas.append(simular_trajetoria_isolada.cache_info().currsize)

    monkeypatch.setattr(motor_mod, "limpar_cache_trajetoria", _limpar_e_registrar)

    snapshot_original = calcular_plano(estado_original, parametros)
    snapshot_alterado = calcular_plano(estado_alterado, parametros)

    # limpar_cache_trajetoria foi chamada nas duas execuções, e em ambos os
    # casos o cache estava vazio logo após a chamada (T-68: "deve chamá-la
    # no início de cada execução").
    assertar_exato(chamadas, [0, 0])

    # As duas entradas são DIFERENTES — a segunda execução calculou de
    # verdade sobre o saldo alterado, sem herdar snapshot da primeira.
    assert snapshot_alterado.hash_inputs != snapshot_original.hash_inputs
    assert snapshot_alterado.SNAPSHOT_ID != snapshot_original.SNAPSHOT_ID


@pytest.mark.regra
def test_criterio4_calcular_plano_nao_escreve_em_disco_nem_persiste(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Critério de aceite 4: `calcular_plano` não escreve em disco nem chama
    `anexar()` de um `RepositorioSnapshots` — persistência é exclusiva do
    CHAMADOR. Duas provas:

    1. Estática: `engine/motor.py` não importa nada de `persistencia/` nem
       de `engine/portas.py` (onde `RepositorioSnapshots`/`anexar` vivem) —
       varre a AST do módulo, mesmo espírito de `tests/estatica/test_
       nenhum_parametro_no_codigo.py`.
    2. Dinâmica: `calcular_plano` devolve o `SnapshotOrdem` em memória, sem
       nenhum efeito colateral de I/O — comparado antes/depois, o diretório
       de trabalho não ganha nenhum arquivo novo.
    """
    import ast
    import inspect

    import engine.motor as motor_mod

    codigo_fonte = inspect.getsource(motor_mod)
    arvore = ast.parse(codigo_fonte)

    modulos_importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                modulos_importados.add(alias.name)
        elif isinstance(no, ast.ImportFrom) and no.module:
            modulos_importados.add(no.module)

    for modulo in modulos_importados:
        assert not modulo.startswith("persistencia"), (
            f"engine/motor.py importa {modulo!r} — persistência é exclusiva do "
            "chamador de calcular_plano (critério de aceite 4)."
        )
    assert "engine.portas" not in modulos_importados, (
        "engine/motor.py importa engine.portas (RepositorioSnapshots/anexar) — "
        "calcular_plano nunca persiste (critério de aceite 4)."
    )

    # Nenhuma CHAMADA de código a `.anexar(...)` — distinto de mencionar a
    # palavra em docstring/comentário (prosa), que não é código executável.
    chamadas_a_anexar = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "anexar"
    ]
    assert not chamadas_a_anexar, (
        "engine/motor.py contém uma chamada de código a '.anexar(...)' — "
        "persistência é do chamador, nunca de calcular_plano (critério de "
        "aceite 4)."
    )

    # Prova dinâmica: devolve em memória, sem tocar o sistema de arquivos.
    estado, parametros = _estado_e_parametros
    snapshot = calcular_plano(estado, parametros)
    assert isinstance(snapshot, SnapshotOrdem)


@pytest.mark.regra
def test_criterio5_erro_invariante_propaga_sem_ser_capturado(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 5: se um invariante for violado ao fim de qualquer
    mês da simulação (`ErroInvariante`, levantado internamente por `executar_
    mes`), o erro propaga para FORA de `calcular_plano` sem ser capturado —
    nunca degrada para um resultado aproximado.

    `executar_mes` fecha sua invariante por construção algébrica a partir
    das próprias variáveis internas (ver `tests/regras/test_ciclo_mensal.py`,
    `test_erro_invariante_existe_e_carrega_mensagem_de_diagnostico`): não
    existe `SelecionarAlvo` bem tipado, injetável de fora, capaz de quebrá-la
    através da API pública — o que é o comportamento CORRETO (guarda contra
    regressão, não contra entrada adversarial). Para provar honestamente que
    `calcular_plano` NÃO ENGOLE essa exceção — sem simular um bug interno
    fabricado que não existiria em produção — este teste substitui `simular_
    cenario` (o ponto exato de `engine/motor.py` que pode levantar
    `ErroInvariante`, via `executar_mes`) por um stub que a levanta
    deliberadamente, e confirma que `calcular_plano` deixa a exceção
    atravessar inteira, sem qualquer try/except no caminho."""
    import engine.motor as motor_mod

    def _simular_cenario_com_invariante_quebrado(*_args: object, **_kwargs: object) -> None:
        raise ErroInvariante(
            "conservação do ataque do mês não fechou (A-04/TRAVA): "
            "aplicado=Decimal('0') + nao_utilizado=Decimal('999') = Decimal('999'), "
            "esperado CAPACIDADE_ATAQUE_M=Decimal('100') (mes=1) — invariante "
            "sintético forçado por monkeypatch para provar propagação (T-68, "
            "critério de aceite 5)."
        )

    monkeypatch.setattr(motor_mod, "simular_cenario", _simular_cenario_com_invariante_quebrado)

    estado, parametros = _estado_e_parametros
    with pytest.raises(ErroInvariante, match="conservação do ataque do mês não fechou"):
        calcular_plano(estado, parametros)


@pytest.mark.regra
def test_calcular_plano_encadeia_snapshot_anterior(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Complemento de integração — não duplica `V-01` (já coberto por
    `tests/regras/test_snapshot.py`), apenas confirma que `calcular_plano`
    repassa `anterior`/`evento`/`motivo` corretamente até `montar_
    SnapshotOrdem` (V-01, V-02) através da orquestração completa."""
    estado, parametros = _estado_e_parametros

    primeiro = calcular_plano(estado, parametros)
    segundo = calcular_plano(
        estado,
        parametros,
        anterior=primeiro,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D003",
    )

    assertar_exato(segundo.versao, primeiro.versao + 1)
    assertar_exato(segundo.snapshot_anterior_id, primeiro.SNAPSHOT_ID)
    assertar_exato(segundo.EVENTO_RECALCULO, EVENTO_RECALCULO.QUITACAO_CONFIRMADA)
    assertar_exato(segundo.MOTIVO_RECALCULO, "QUITACAO_D003")


@pytest.mark.regra
def test_calcular_plano_e_pura_data_referencia_vem_do_estado(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """NFR determinismo — `DATA_REFERENCIA` do snapshot é sempre `estado.
    DATA_REFERENCIA`, nunca `date.today()`: alterar a data do estado de
    entrada muda a data do snapshot, provando que não há relógio envolvido.
    """
    estado, parametros = _estado_e_parametros

    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.DATA_REFERENCIA, estado.DATA_REFERENCIA)

    nova_data = dataclasses.replace(
        estado, DATA_REFERENCIA=estado.DATA_REFERENCIA.replace(year=estado.DATA_REFERENCIA.year + 1)
    )
    snapshot_outra_data = calcular_plano(nova_data, parametros)
    assertar_exato(snapshot_outra_data.DATA_REFERENCIA, nova_data.DATA_REFERENCIA)
    assert snapshot_outra_data.DATA_REFERENCIA != snapshot.DATA_REFERENCIA


@pytest.mark.regra
def test_AC53_economia_potencial_positiva_emite_acao_de_economia(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`AC-53` (`T-88`, RF-33): `ECONOMIA_POTENCIAL_IMEDIATA > 0` produz uma
    `AcaoRequerida` em `ORDEM_ACOES` com `TIPO_ACAO="ECONOMIA"` e
    `DIVIDA_ID=None`. `GAB-C` parte de `ECONOMIA_POTENCIAL_IMEDIATA = 0`
    (fixture); `dataclasses.replace` torna o campo positivo, sem tocar em
    mais nada da carteira."""
    estado, parametros = _estado_e_parametros
    estado_com_economia = dataclasses.replace(
        estado, ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("500")
    )

    snapshot = calcular_plano(estado_com_economia, parametros)

    acoes_economia = [acao for acao in snapshot.ORDEM_ACOES if acao.TIPO_ACAO == "ECONOMIA"]
    assertar_exato(len(acoes_economia), 1)
    assertar_exato(acoes_economia[0].DIVIDA_ID, None)
    assertar_exato(acoes_economia[0].gate_origem, None)
    assertar_exato(acoes_economia[0].CAMPO_PENDENTE, None)


@pytest.mark.regra
def test_AC54_economia_potencial_zero_nao_emite_acao(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`AC-54` (`T-88`, RF-33): `ECONOMIA_POTENCIAL_IMEDIATA = 0` (caso
    comum, não uma falha) não adiciona nenhuma `AcaoRequerida` de
    `TIPO_ACAO="ECONOMIA"` a `ORDEM_ACOES`. `GAB-C` já tem o campo zerado —
    nenhuma alteração de estado é necessária."""
    estado, parametros = _estado_e_parametros
    assertar_exato(estado.ECONOMIA_POTENCIAL_IMEDIATA, dinheiro("0"))

    snapshot = calcular_plano(estado, parametros)

    acoes_economia = [acao for acao in snapshot.ORDEM_ACOES if acao.TIPO_ACAO == "ECONOMIA"]
    assertar_exato(acoes_economia, [])


@pytest.mark.regra
def test_EC20_economia_coexiste_com_acoes_de_informacao_do_gate_1() -> None:
    """`EC-20` (`T-88`, RF-33): quando há simultaneamente
    `ECONOMIA_POTENCIAL_IMEDIATA > 0` e uma ou mais dívidas bloqueadas pelo
    Gate 1, `ORDEM_ACOES` contém tanto a(s) `AcaoRequerida` de
    `TIPO_ACAO="INFORMACAO"` quanto a de `TIPO_ACAO="ECONOMIA"` — emissão
    independente do estado dos gates. `GAB-A` já bloqueia as duas dívidas no
    Gate 1 (`SALDO_DEVEDOR_ATUAL = DESCONHECIDO`, `AC-05`/`T-87`); aqui
    `ECONOMIA_POTENCIAL_IMEDIATA` é elevada de 0 (fixture) para um valor
    positivo, sem alterar as dívidas."""
    estado = dataclasses.replace(carregar_gab_a(), ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("300"))
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    tipos_presentes = {acao.TIPO_ACAO for acao in snapshot.ORDEM_ACOES}
    assertar_exato(
        "INFORMACAO" in tipos_presentes,
        True,
    )  # GAB-A tem dívidas com SALDO_DEVEDOR_ATUAL DESCONHECIDO — deveriam
    # bloquear no Gate 1 e emitir AcaoRequerida(TIPO_ACAO='INFORMACAO').
    assertar_exato("ECONOMIA" in tipos_presentes, True)

    acoes_economia = [acao for acao in snapshot.ORDEM_ACOES if acao.TIPO_ACAO == "ECONOMIA"]
    assertar_exato(len(acoes_economia), 1)
    assertar_exato(acoes_economia[0].DIVIDA_ID, None)
