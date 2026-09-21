"""Testa `RepositorioSnapshots` (`engine/portas.py`) e o adaptador
`RepositorioSnapshotsArquivo` (`persistencia/arquivo/repositorio_snapshots.py`)
— `RF-10`, `RF-12`, `V-01..V-03`, `T-69`.

Cobre os cinco critérios de aceite de `T-69`:

1. A porta (`Protocol`) NÃO tem `atualizar` nem `remover` — provado por
   inspeção do `Protocol` e por `AttributeError` ao tentar chamar.
2. `anexar` chamado duas vezes preserva as DUAS versões no arquivo, na
   ordem em que foram escritas (nunca sobrescreve).
3. Todo `Decimal` do `SnapshotOrdem` vira string no JSONL e volta como
   `Decimal` EXATO (round-trip bit a bit) ao ler de volta.
4. `historico(caso_id)` devolve a cadeia completa de snapshots daquele
   caso, em ordem determinística (por `versao` crescente — ver docstring
   de `RepositorioSnapshotsArquivo.historico`).
5. Erro de escrita em disco é PROPAGADO ao chamador, e o `SnapshotOrdem`
   em memória passado a `anexar` permanece intacto (não é mutado nem
   perdido).

Reusa a fixture `GAB-C` real (`_montar_snapshot_gab_c`,
`tests/regras/test_snapshot.py`, T-67) para montar `SnapshotOrdem`
completos, com todas as árvores de tipos do motor preenchidas — o mesmo
padrão de reaproveitamento já usado por outros módulos de teste
(`test_S.py` reusa nomes/cenários de `T-59`).

REGRAS: RF-10, RF-12, V-01, V-02, V-03
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

from engine.classificacao_ativos import classificar_ativo_fisico, classificar_investimento
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    ESSENCIALIDADE,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    RESERVA_EXISTE,
    TIPO_ATIVO_FISICO,
    EstadoFinanceiro,
    ItemAtivo,
    ItemInvestimento,
    RecursoExtraordinario,
)
from engine.gates import AcaoRequerida
from engine.parametros import Parametros
from engine.portas import RepositorioSnapshots
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO, EVENTO_RECALCULO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import (
    ErroSnapshotNaoEncontrado,
    RepositorioSnapshotsArquivo,
)
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c
from tests.regras.test_snapshot import _montar_snapshot_gab_c


@pytest.fixture(scope="module")
def _estado_e_parametros() -> tuple[EstadoFinanceiro, Parametros]:
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return estado, parametros


@pytest.mark.regra
def test_criterio1_porta_nao_tem_atualizar_nem_remover() -> None:
    """Critério de aceite 1: `RepositorioSnapshots` (`Protocol`) expõe
    exatamente `anexar`, `obter` e `historico` — sem `atualizar`/`remover`.
    Prova por inspeção do `Protocol` (nenhum verbo de mutação declarado) e
    por `AttributeError` real ao chamar `.atualizar(...)`/`.remover(...)`
    em uma instância do adaptador concreto — a violação de `V-01` é
    estruturalmente inexprimível, não uma checagem em runtime."""
    metodos_protocolo = {
        nome
        for nome in dir(RepositorioSnapshots)
        if not nome.startswith("_")
    }
    assert metodos_protocolo == {"anexar", "obter", "historico"}, (
        f"RepositorioSnapshots deveria expor exatamente anexar/obter/historico, "
        f"encontrou {metodos_protocolo!r}"
    )
    assert "atualizar" not in metodos_protocolo
    assert "remover" not in metodos_protocolo

    repositorio = RepositorioSnapshotsArquivo(Path("inexistente.jsonl"))
    with pytest.raises(AttributeError):
        repositorio.atualizar(None)  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        repositorio.remover("qualquer-id")  # type: ignore[attr-defined]


@pytest.mark.regra
def test_criterio2_anexar_duas_vezes_preserva_as_duas_versoes_na_ordem(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """Critério de aceite 2: `anexar` chamado duas vezes preserva as DUAS
    versões no arquivo, na ordem em que foram escritas — nunca sobrescreve
    a linha anterior."""
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    primeiro = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    segundo = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D001",
        anterior=primeiro,
    )

    repositorio.anexar(primeiro)
    repositorio.anexar(segundo)

    linhas = caminho.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 2, (
        f"esperava 2 linhas no arquivo após 2 chamadas a anexar, obteve {len(linhas)}"
    )

    # A ordem das LINHAS no arquivo é a ordem de escrita — primeiro anexado
    # é a primeira linha, segundo anexado é a segunda (nunca sobrescrita).
    obtido_primeiro = repositorio.obter(primeiro.SNAPSHOT_ID)
    obtido_segundo = repositorio.obter(segundo.SNAPSHOT_ID)
    assertar_exato(obtido_primeiro.SNAPSHOT_ID, primeiro.SNAPSHOT_ID)
    assertar_exato(obtido_segundo.SNAPSHOT_ID, segundo.SNAPSHOT_ID)
    assertar_exato(obtido_segundo.snapshot_anterior_id, primeiro.SNAPSHOT_ID)

    import json

    linha_1 = json.loads(linhas[0])
    linha_2 = json.loads(linhas[1])
    assertar_exato(linha_1["SNAPSHOT_ID"], primeiro.SNAPSHOT_ID)
    assertar_exato(linha_2["SNAPSHOT_ID"], segundo.SNAPSHOT_ID)
    assertar_exato(linha_1["versao"], 1)
    assertar_exato(linha_2["versao"], 2)


@pytest.mark.regra
def test_criterio3_decimal_vira_string_e_volta_exato_round_trip(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """Critério de aceite 3: todo `Decimal` do `SnapshotOrdem` vira string
    no JSONL (nunca `float`) e volta como `Decimal` EXATO — round-trip bit
    a bit, comparado com `assertar_exato` (tolerância zero, RF-12)."""
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    original = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    repositorio.anexar(original)

    # Confere diretamente na linha crua do arquivo: todo campo monetário
    # está serializado como STRING JSON, nunca como number (que o parser
    # padrão devolveria como float/int, nunca Decimal).
    import json

    linha_bruta = caminho.read_text(encoding="utf-8").strip().splitlines()[0]
    bruto = json.loads(linha_bruta)
    assert isinstance(bruto["diagnostico"]["CAPACIDADE_ATAQUE_CONSERVADORA"], str), (
        "Decimal deveria ter sido serializado como string JSON, nunca number"
    )
    assert isinstance(bruto["ENGINE_VERSION"], str)

    reconstruido = repositorio.obter(original.SNAPSHOT_ID)

    # Round-trip EXATO campo a campo — não só "igual numericamente": o tipo
    # também precisa ser Decimal (bit a bit, não aproximado).
    assert type(reconstruido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA) is type(
        original.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    )
    assertar_exato(
        reconstruido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
        original.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
    )
    assertar_exato(
        reconstruido.diagnostico.FATOR_SEGURANCA, original.diagnostico.FATOR_SEGURANCA
    )
    assertar_exato(
        reconstruido.comparacao.DIFERENCA_PERCENTUAL, original.comparacao.DIFERENCA_PERCENTUAL
    )
    assertar_exato(reconstruido.hash_inputs, original.hash_inputs)
    assertar_exato(reconstruido.SNAPSHOT_ID, original.SNAPSHOT_ID)
    assertar_exato(reconstruido.versao, original.versao)
    assertar_exato(reconstruido.DATA_REFERENCIA, original.DATA_REFERENCIA)
    assertar_exato(reconstruido.estado_inputs, original.estado_inputs)
    assertar_exato(reconstruido.METODO_RECOMENDADO_PIQ, original.METODO_RECOMENDADO_PIQ)
    assertar_exato(reconstruido.STATUS_METODO, original.STATUS_METODO)
    assertar_exato(reconstruido.ORDEM_STATUS, original.ORDEM_STATUS)
    assertar_exato(reconstruido.ORDEM_QUITACAO, original.ORDEM_QUITACAO)
    assertar_exato(reconstruido.ORDEM_ACOES, original.ORDEM_ACOES)
    assertar_exato(reconstruido.cenarios, original.cenarios)
    assertar_exato(reconstruido.diagnostico, original.diagnostico)

    # Para cada valor de apoio (Decimal) de cada posição publicada: exato.
    for posicao_original, posicao_reconstruida in zip(
        original.ORDEM_QUITACAO, reconstruido.ORDEM_QUITACAO, strict=True
    ):
        for chave, valor in posicao_original.valores_de_apoio.items():
            assertar_exato(posicao_reconstruida.valores_de_apoio[chave], valor)


@pytest.mark.regra
def test_T92_acao_requerida_round_trip_contrato_estendido(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """T-92 — `_acao_requerida` (desserialização) precisa reconstruir os
    campos novos/obrigatórios de `AcaoRequerida` (`ACAO_ID`, `TIPO_ACAO`) e o
    opcional (`CAMPO_PENDENTE`), não só `DIVIDA_ID`/`descricao`/`gate_origem`
    do contrato antigo. `GAB-C` sozinho não gera nenhuma `AcaoRequerida`
    (`ORDEM_ACOES` vazia) — este teste injeta duas ações manualmente via
    `dataclasses.replace` no snapshot: uma ligada a uma dívida (Gate 1,
    `CAMPO_PENDENTE` preenchido) e uma de economia (`DIVIDA_ID=None`,
    `gate_origem=None`, `CAMPO_PENDENTE=None`, `RF-31`/`RF-33`), provando que
    o `str | None` de `DIVIDA_ID` e o `Literal | None` de `CAMPO_PENDENTE`
    sobrevivem ao ciclo `anexar`/`obter` exatamente como no original.

    T-133 (RF-61 · §14.2.1/§14.2.2): as duas fixtures ganham
    `VALOR_ACAO_FINANCEIRA_IMEDIATA` explícito, exercitando o round-trip do
    campo novo nos dois sabores de `DinheiroTalvez` — `acao_gate_1` com
    `Decimal` exato conhecido, `acao_economia` com `DESCONHECIDO` — provando
    que nenhum dos dois vira silenciosamente `0`/`None` na desserialização."""
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    acao_gate_1 = AcaoRequerida(
        ACAO_ID="D001:INFORMACAO",
        DIVIDA_ID="D001",
        TIPO_ACAO="INFORMACAO",
        descricao="D001: SALDO_DEVEDOR_ATUAL desconhecido — teste T-92.",
        gate_origem=1,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro("123.45"),
        prioridade_excepcional=False,
        CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL",
    )
    acao_economia = AcaoRequerida(
        ACAO_ID="ACAO:ECONOMIA",
        DIVIDA_ID=None,
        TIPO_ACAO="ECONOMIA",
        descricao="Ação de economia — teste T-92.",
        gate_origem=None,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO,
        prioridade_excepcional=False,
        CAMPO_PENDENTE=None,
    )

    original = dataclasses.replace(
        _montar_snapshot_gab_c(estado=estado, parametros=parametros),
        ORDEM_ACOES=(acao_gate_1, acao_economia),
    )
    repositorio.anexar(original)
    reconstruido = repositorio.obter(original.SNAPSHOT_ID)

    assertar_exato(reconstruido.ORDEM_ACOES, original.ORDEM_ACOES)
    assertar_exato(len(reconstruido.ORDEM_ACOES), 2)
    assertar_exato(reconstruido.ORDEM_ACOES[0].ACAO_ID, "D001:INFORMACAO")
    assertar_exato(reconstruido.ORDEM_ACOES[0].TIPO_ACAO, "INFORMACAO")
    assertar_exato(reconstruido.ORDEM_ACOES[0].CAMPO_PENDENTE, "SALDO_DEVEDOR_ATUAL")
    assertar_exato(
        reconstruido.ORDEM_ACOES[0].VALOR_ACAO_FINANCEIRA_IMEDIATA, dinheiro("123.45")
    )
    assertar_exato(reconstruido.ORDEM_ACOES[1].ACAO_ID, "ACAO:ECONOMIA")
    assertar_exato(reconstruido.ORDEM_ACOES[1].DIVIDA_ID, None)
    assertar_exato(reconstruido.ORDEM_ACOES[1].gate_origem, None)
    assertar_exato(reconstruido.ORDEM_ACOES[1].CAMPO_PENDENTE, None)
    assertar_exato(reconstruido.ORDEM_ACOES[1].VALOR_ACAO_FINANCEIRA_IMEDIATA, DESCONHECIDO)


@pytest.mark.regra
def test_T97_estado_financeiro_rodada_3_round_trip_itens_e_desconhecido(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """T-97 — `_estado_financeiro` precisa reconstruir os NOVE campos da
    Rodada 3 (`RF-36`..`RF-39`), e `_item_investimento`/`_item_ativo`/
    `_recurso_extraordinario` precisam desserializar os três tipos de item.
    Mesmo padrão de `test_T92_acao_requerida_round_trip_contrato_estendido`:
    `GAB-C` é neutro nesses campos (reserva ausente, caixa zero, coleções
    vazias — `AC-87`), então este teste injeta um estado PREENCHIDO via
    `dataclasses.replace` e prova que o ciclo `anexar`/`obter` devolve

      - `Decimal` EXATO (casas preservadas, nunca via `float` — `RF-12`);
      - o sentinela `DESCONHECIDO` de `DinheiroTalvez` intacto (§13.1 Regra
        3: nunca convertido silenciosamente em `0` nem em `None`);
      - cada `Enum` de domínio da Rodada 3 (`RESERVA_EXISTE`,
        `DISPOSICAO_USO_RESERVA`, `CLASSIFICACAO_MOBILIZACAO`,
        `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`);
      - a ORDEM e a IDENTIDADE (`ITEM_ID`) de cada item, por item — `AC-64`
        exige coleção tipada, nunca um total já somado.
    """
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    estado_preenchido = dataclasses.replace(
        estado,
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        RESERVA_TOTAL=dinheiro("30000.07"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        # `DESCONHECIDO` aqui é o caso da Regra 3 da §13.1 ("prefiro decidir
        # depois" / "não sei"): tem de sobreviver ao round-trip como
        # sentinela, não como zero.
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
        DINHEIRO_DISPONIVEL=dinheiro("1234.56"),
        investimentos=(
            # INV-01: campos brutos da Regra 4 (§14.3.1) — SIM, D0, sem custo/
            # perda relevante, VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL>0 ->
            # classificar_investimento DERIVA MOBILIZACAO_RECOMENDAVEL.
            ItemInvestimento(
                ITEM_ID="INV-01",
                VALOR_LIQUIDO_REALIZAVEL=dinheiro("10000.01"),
                POSSUI_LIQUIDEZ=True,
                LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D0,
                DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.SIM,
                VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro("10000.01"),
                TEM_CUSTO_CONHECIDO=False,
                SEM_CUSTO_PERDA_RELEVANTE=True,
            ),
            # INV-02: campos brutos da Regra 3 (§14.3.1) — TALVEZ, liquidez
            # não bloqueada -> classificar_investimento DERIVA
            # MOBILIZACAO_POSSIVEL.
            ItemInvestimento(
                ITEM_ID="INV-02",
                VALOR_LIQUIDO_REALIZAVEL=dinheiro("0.99"),
                POSSUI_LIQUIDEZ=False,
                LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D1,
                DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.TALVEZ,
                VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro("0.99"),
                TEM_CUSTO_CONHECIDO=False,
                SEM_CUSTO_PERDA_RELEVANTE=False,
            ),
        ),
        ativos=(
            # ATV-01: campos brutos do ramo 8c (§14.8/§14.9) — não essencial,
            # venda SIM, fluxo líquido recorrente <= 0 -> classificar_ativo_
            # fisico DERIVA MOBILIZACAO_RECOMENDAVEL. `RENDA_RECORRENTE_ATIVO`
            # concreto (não None nem DESCONHECIDO): item não é veículo, então
            # None aqui acionaria o bloqueio de OQ-38 sem necessidade.
            ItemAtivo(
                ITEM_ID="ATV-01",
                TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
                POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
                ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
                VALOR_ESTIMADO_ATIVO=dinheiro("250000.10"),
                POSSUI_PASSIVO_VINCULADO=False,
                SALDO_PASSIVO_VINCULADO=dinheiro(0),
                POSSUI_CUSTO_DESMOBILIZACAO=False,
                CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
                RENDA_RECORRENTE_ATIVO=dinheiro(0),
                CUSTO_RECORRENTE_ATIVO=dinheiro(0),
            ),
            # ATV-02: veículo não essencial, venda aceita, `RENDA_RECORRENTE_
            # ATIVO=None` — o sentinela ESTRUTURAL de OQ-38 (RF-56) — prova
            # que o `None` sobrevive ao round-trip sem virar DESCONHECIDO nem
            # 0 (distinto de `_dinheiro_talvez`, que não aceita None).
            ItemAtivo(
                ITEM_ID="ATV-02",
                TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.VEICULO,
                POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
                ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
                VALOR_ESTIMADO_ATIVO=dinheiro("30000.00"),
                POSSUI_PASSIVO_VINCULADO=False,
                SALDO_PASSIVO_VINCULADO=dinheiro(0),
                POSSUI_CUSTO_DESMOBILIZACAO=False,
                CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
                RENDA_RECORRENTE_ATIVO=None,
                CUSTO_RECORRENTE_ATIVO=dinheiro(0),
            ),
        ),
        recursos_extraordinarios=(
            RecursoExtraordinario(
                ITEM_ID="REC-01",
                VALOR_RECURSO_EXTRAORDINARIO=dinheiro("5000.55"),
                JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
            RecursoExtraordinario(
                ITEM_ID="REC-02",
                VALOR_RECURSO_EXTRAORDINARIO=dinheiro("800.00"),
                JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO.SETE_A_DOZE_MESES,
                CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO.POSSIVEL,
            ),
        ),
    )

    original = dataclasses.replace(
        _montar_snapshot_gab_c(estado=estado, parametros=parametros),
        estado_inputs=estado_preenchido,
    )
    repositorio.anexar(original)
    reconstruido = repositorio.obter(original.SNAPSHOT_ID)
    obtido = reconstruido.estado_inputs

    # O `EstadoFinanceiro` inteiro volta igual por valor (frozen dataclass,
    # igualdade estrutural) — a asserção mais forte disponível.
    assertar_exato(obtido, estado_preenchido)

    # Reserva: `Decimal` exato de um lado, sentinela do outro.
    assertar_exato(obtido.RESERVA_EXISTE, RESERVA_EXISTE.SIM)
    assertar_exato(obtido.DISPOSICAO_USO_RESERVA, DISPOSICAO_USO_RESERVA.GRANDE_PARTE)
    assert type(obtido.RESERVA_TOTAL) is Decimal
    assertar_exato(obtido.RESERVA_TOTAL, dinheiro("30000.07"))
    assert obtido.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO, (
        "§13.1 Regra 3: DESCONHECIDO nunca vira 0 nem None no round-trip"
    )

    # Caixa: `Dinheiro` sempre presente (`AC-63`), exato.
    assert type(obtido.DINHEIRO_DISPONIVEL) is Decimal
    assertar_exato(obtido.DINHEIRO_DISPONIVEL, dinheiro("1234.56"))

    # Patrimônio: item a item, na ordem, com identidade e classificação
    # DERIVADA (RF-59, T-125) — round-trip da classificação é chamar o
    # classificador nos dois lados da serialização, nunca comparar um campo
    # armazenado.
    assertar_exato(tuple(i.ITEM_ID for i in obtido.investimentos), ("INV-01", "INV-02"))
    assertar_exato(obtido.investimentos[0].VALOR_LIQUIDO_REALIZAVEL, dinheiro("10000.01"))
    assertar_exato(obtido.investimentos[0].POSSUI_LIQUIDEZ, True)
    assertar_exato(obtido.investimentos[1].POSSUI_LIQUIDEZ, False)
    for original_item, obtido_item in zip(
        estado_preenchido.investimentos, obtido.investimentos, strict=True
    ):
        assertar_exato(
            classificar_investimento(obtido_item), classificar_investimento(original_item)
        )
    assertar_exato(
        classificar_investimento(obtido.investimentos[1]),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
    )
    assertar_exato(tuple(a.ITEM_ID for a in obtido.ativos), ("ATV-01", "ATV-02"))
    for original_ativo, obtido_ativo in zip(estado_preenchido.ativos, obtido.ativos, strict=True):
        assertar_exato(
            classificar_ativo_fisico(obtido_ativo), classificar_ativo_fisico(original_ativo)
        )
    assertar_exato(
        classificar_ativo_fisico(obtido.ativos[0]),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
    )
    assertar_exato(obtido.ativos[0].VALOR_ESTIMADO_ATIVO, dinheiro("250000.10"))
    # ATV-02: veículo bloqueado (RF-56, OQ-38) — `None` sobrevive ao
    # round-trip como sentinela ESTRUTURAL, nunca vira DESCONHECIDO nem 0, e
    # `classificar_ativo_fisico` continua retornando `None` (não uma
    # CLASSIFICACAO_MOBILIZACAO do domínio).
    assert obtido.ativos[1].RENDA_RECORRENTE_ATIVO is None, (
        "RF-56/OQ-38: RENDA_RECORRENTE_ATIVO=None de veículo é sentinela "
        "ESTRUTURAL, precisa sobreviver ao round-trip como None"
    )
    assert classificar_ativo_fisico(obtido.ativos[1]) is None
    assertar_exato(
        obtido.recursos_extraordinarios[0].JANELA_RECURSO_EXTRAORDINARIO,
        JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
    )
    assertar_exato(
        obtido.recursos_extraordinarios[0].CERTEZA_RECURSO_EXTRAORDINARIO,
        CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
    )
    assertar_exato(
        obtido.recursos_extraordinarios[1].VALOR_RECURSO_EXTRAORDINARIO, dinheiro("800.00")
    )

    # Na LINHA CRUA: todo valor monetário dos itens é STRING JSON, nunca
    # `number` (que o parser padrão devolveria como float/int) — RF-12.
    import json

    bruto = json.loads(caminho.read_text(encoding="utf-8").strip().splitlines()[0])
    estado_bruto = bruto["estado_inputs"]
    assert isinstance(estado_bruto["DINHEIRO_DISPONIVEL"], str)
    assert isinstance(estado_bruto["RESERVA_TOTAL"], str)
    assertar_exato(estado_bruto["VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO"], "DESCONHECIDO")
    assert isinstance(estado_bruto["investimentos"][0]["VALOR_LIQUIDO_REALIZAVEL"], str)
    assert isinstance(estado_bruto["ativos"][0]["VALOR_ESTIMADO_ATIVO"], str)
    # ATV-02: RENDA_RECORRENTE_ATIVO=None (sentinela ESTRUTURAL, RF-56) fica
    # `null` na linha crua — nunca "DESCONHECIDO" nem "0".
    assert estado_bruto["ativos"][1]["RENDA_RECORRENTE_ATIVO"] is None
    assert isinstance(
        estado_bruto["recursos_extraordinarios"][0]["VALOR_RECURSO_EXTRAORDINARIO"], str
    )


@pytest.mark.regra
def test_T98_diagnostico_reserva_mobilizavel_round_trip_desconhecido(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """T-98 — `Diagnostico.RESERVA_MOBILIZAVEL` é `DinheiroTalvez` (`RF-41`,
    `AC-68`, §13.1 Regra 3) e por isso `_diagnostico` desserializa o campo com
    `_dinheiro_talvez`, não com `_decimal`.

    Mesmo padrão de `test_T97_estado_financeiro_rodada_3_round_trip_itens_e_
    desconhecido`: o `Diagnostico` de `GAB-C` traz o placeholder `0` de
    `T-90`, então este teste injeta `DESCONHECIDO` via `dataclasses.replace` e
    prova que o ciclo `anexar`/`obter` devolve o SENTINELA — nunca `0`, nunca
    `None`. A distinção é de método, não de estilo: `0` significa "o usuário
    não aceita mobilizar nada" e `DESCONHECIDO` significa "ainda não se sabe
    quanto ele aceita"; converter o segundo no primeiro apagaria a pendência
    que a §13.1 manda registrar.

    Prova também o ramo `Dinheiro` do mesmo campo (um `Decimal` com casas
    preservadas) e que `ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro`
    (plano R3.4.6) — não foi retipado "por simetria".
    """
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    base = _montar_snapshot_gab_c(estado=estado, parametros=parametros)

    # --- Ramo DESCONHECIDO (§13.1 Regra 3) ---
    original_desconhecido = dataclasses.replace(
        base,
        diagnostico=dataclasses.replace(
            base.diagnostico,
            RESERVA_MOBILIZAVEL=DESCONHECIDO,
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("321.09"),
        ),
    )
    repositorio.anexar(original_desconhecido)
    obtido = repositorio.obter(original_desconhecido.SNAPSHOT_ID).diagnostico

    assert obtido.RESERVA_MOBILIZAVEL is DESCONHECIDO, (
        "§13.1 Regra 3: RESERVA_MOBILIZAVEL DESCONHECIDA nunca vira 0 nem "
        f"None no round-trip, obteve {obtido.RESERVA_MOBILIZAVEL!r}"
    )
    assert obtido.RESERVA_MOBILIZAVEL != dinheiro(0)
    assert obtido.RESERVA_MOBILIZAVEL is not None
    # O diagnóstico inteiro volta igual por valor (frozen dataclass).
    assertar_exato(obtido, original_desconhecido.diagnostico)
    # `ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro` (plano R3.4.6).
    assert type(obtido.ATAQUE_IMEDIATO_RECOMENDADO) is Decimal
    assertar_exato(obtido.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("321.09"))

    # Na LINHA CRUA o sentinela é a string "DESCONHECIDO" (RF-12: monetário
    # nunca é `number` JSON).
    import json

    linhas = caminho.read_text(encoding="utf-8").strip().splitlines()
    diagnostico_bruto = json.loads(linhas[0])["diagnostico"]
    assertar_exato(diagnostico_bruto["RESERVA_MOBILIZAVEL"], "DESCONHECIDO")
    assert isinstance(diagnostico_bruto["ATAQUE_IMEDIATO_RECOMENDADO"], str)

    # --- Ramo Dinheiro do MESMO campo: valor exato, casa a casa ---
    original_conhecido = dataclasses.replace(
        base,
        SNAPSHOT_ID=base.SNAPSHOT_ID + "-conhecido",
        diagnostico=dataclasses.replace(
            base.diagnostico, RESERVA_MOBILIZAVEL=dinheiro("18000.13")
        ),
    )
    repositorio.anexar(original_conhecido)
    obtido_conhecido = repositorio.obter(original_conhecido.SNAPSHOT_ID).diagnostico

    assert type(obtido_conhecido.RESERVA_MOBILIZAVEL) is Decimal
    assertar_exato(obtido_conhecido.RESERVA_MOBILIZAVEL, dinheiro("18000.13"))
    assertar_exato(obtido_conhecido, original_conhecido.diagnostico)


@pytest.mark.regra
def test_criterio4_historico_devolve_cadeia_completa_em_ordem_deterministica(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """Critério de aceite 4: `historico(caso_id)` devolve a cadeia completa
    de snapshots daquele caso, em ordem determinística — por `versao`
    crescente (decisão documentada em `RepositorioSnapshotsArquivo.
    historico`). `caso_id` adotado é o `SNAPSHOT_ID` da RAIZ da cadeia."""
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    primeiro = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    segundo = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D001",
        anterior=primeiro,
    )
    terceiro = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.NOVA_DIVIDA,
        motivo="NOVA_DIVIDA",
        anterior=segundo,
    )

    # Anexados fora de ordem — historico() precisa ordenar por versao,
    # não confiar na ordem de escrita do arquivo.
    repositorio.anexar(segundo)
    repositorio.anexar(terceiro)
    repositorio.anexar(primeiro)

    cadeia = repositorio.historico(primeiro.SNAPSHOT_ID)

    assert len(cadeia) == 3, f"esperava 3 snapshots na cadeia, obteve {len(cadeia)}"
    assertar_exato([s.versao for s in cadeia], [1, 2, 3])
    assertar_exato(cadeia[0].SNAPSHOT_ID, primeiro.SNAPSHOT_ID)
    assertar_exato(cadeia[1].SNAPSHOT_ID, segundo.SNAPSHOT_ID)
    assertar_exato(cadeia[2].SNAPSHOT_ID, terceiro.SNAPSHOT_ID)
    assertar_exato(cadeia[1].snapshot_anterior_id, primeiro.SNAPSHOT_ID)
    assertar_exato(cadeia[2].snapshot_anterior_id, segundo.SNAPSHOT_ID)


@pytest.mark.regra
def test_criterio4_historico_de_caso_inexistente_e_vazio(tmp_path: Path) -> None:
    """`historico` de um `caso_id` que não existe no arquivo (ou arquivo
    ainda não criado) devolve sequência vazia — nunca erro nem `None`."""
    repositorio = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
    assertar_exato(tuple(repositorio.historico("qualquer-caso-inexistente")), ())


@pytest.mark.regra
def test_obter_snapshot_inexistente_levanta_erro(tmp_path: Path) -> None:
    """`obter` de um `SNAPSHOT_ID` ausente levanta `ErroSnapshotNaoEncontrado`
    — nunca devolve `None`/objeto fabricado (mesmo espírito de
    `engine.parametros.ErroParametros`)."""
    repositorio = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
    with pytest.raises(ErroSnapshotNaoEncontrado):
        repositorio.obter("id-que-nao-existe")


@pytest.mark.regra
def test_criterio5_erro_de_escrita_e_propagado_sem_perder_snapshot_em_memoria(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """Critério de aceite 5: se a escrita em disco falhar (simulada aqui
    apontando o repositório para um CAMINHO cujo diretório-pai é, na
    verdade, um ARQUIVO — `mkdir`/`open` falham com `NotADirectoryError`/
    `OSError`), o erro é PROPAGADO ao chamador, e o `SnapshotOrdem` em
    memória passado a `anexar` permanece intacto: mesmos campos, mesma
    identidade de objeto, sem qualquer mutação."""
    estado, parametros = _estado_e_parametros
    snapshot = _montar_snapshot_gab_c(estado=estado, parametros=parametros)

    # Campos-chave lidos ANTES da tentativa de anexar, para comparar depois
    # que a escrita falhar — nunca via dataclasses.asdict (recursaria pela
    # árvore inteira do snapshot sem necessidade; só interessa aqui provar
    # que os campos-chave permanecem os mesmos).
    snapshot_id_antes = snapshot.SNAPSHOT_ID
    versao_antes = snapshot.versao
    hash_inputs_antes = snapshot.hash_inputs

    # "diretorio_que_e_arquivo" é um ARQUIVO comum — usá-lo como diretório-
    # pai de snapshots.jsonl faz `Path.mkdir(parents=True)` levantar
    # FileExistsError/NotADirectoryError, uma falha de I/O real e não
    # controlada pelo código do adaptador.
    arquivo_bloqueador = tmp_path / "diretorio_que_e_arquivo"
    arquivo_bloqueador.write_text("nao sou um diretorio", encoding="utf-8")
    caminho_impossivel = arquivo_bloqueador / "snapshots.jsonl"

    repositorio = RepositorioSnapshotsArquivo(caminho_impossivel)

    with pytest.raises(OSError):
        repositorio.anexar(snapshot)

    # O objeto em memória não foi mutado nem perdido: mesma identidade,
    # mesmos campos-chave, ainda `frozen` (uma tentativa de escrita nele
    # continua levantando FrozenInstanceError).
    assertar_exato(snapshot.SNAPSHOT_ID, snapshot_id_antes)
    assertar_exato(snapshot.versao, versao_antes)
    assertar_exato(snapshot.hash_inputs, hash_inputs_antes)
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.MOTIVO_RECALCULO = "tentativa de sobrescrita apos falha"  # type: ignore[misc]

    # O chamador ainda pode tentar anexar de novo com um caminho válido —
    # nada no snapshot foi corrompido pela falha anterior.
    caminho_valido = tmp_path / "snapshots.jsonl"
    repositorio_valido = RepositorioSnapshotsArquivo(caminho_valido)
    repositorio_valido.anexar(snapshot)
    reobtido = repositorio_valido.obter(snapshot.SNAPSHOT_ID)
    assertar_exato(reobtido.SNAPSHOT_ID, snapshot.SNAPSHOT_ID)
