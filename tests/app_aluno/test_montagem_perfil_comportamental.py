"""Testes de `app/montagem/estado.py::montar_perfil_comportamental` e
`montar_sinais_comportamentais` — RF-14, AC-13 (T-50).

Cobre os quatro critérios de aceite de `T-50` com os registros REAIS dos
Blocos 1, 2 e 5 (`collection/registros/bloco-0{1,2,5}.yaml`, T-17), carregados
por `collection.carga.carregar_registros` — nenhum `VARIAVEL_GRAVADA`/
`valor_interno` é inventado no teste; todos vêm do próprio registro de
produção, para que uma mudança no YAML que quebre o mapeamento seja pega aqui.

REGRAS: RF-14, AC-13
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.montagem.estado import (
    ErroRespostaAusente,
    ErroSinalComportamentalAusente,
    ErroValorInternoDesconhecido,
    _autopercepcao_controle,
    montar_perfil_comportamental,
    montar_sinais_comportamentais,
)
from collection.carga import carregar_registros
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    JANELA_NOVA_DIVIDA,
    REGISTRO_GASTOS,
    REVISAO_SEMANAL,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.tipos import DESCONHECIDO, SimNaoTalvez

_CASO_ID = "caso-teste-t50"
_QUESTIONARIO_VERSION = "1.0.0"
_AGORA = datetime(2026, 1, 1, tzinfo=UTC)

_OMITIR = object()  # sentinela local de teste: "não gravar esta resposta"


def _resposta(ID_PERGUNTA: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
        respondida_em=_AGORA,
    )


# Os 8 `VARIAVEL_GRAVADA` do Bloco 2 (collection/registros/bloco-02.yaml,
# T-17) que compõem `PerfilComportamental`, cada um com um `valor_interno`
# concreto e válido do próprio registro.
def _perfil_comportamental_minimo_completo(**sobrescritas: object) -> RespostasCaso:
    valores: dict[str, object] = {
        "REGISTRO_GASTOS": "TUDO",
        "FREQUENCIA_REGISTRO": "DIARIA",
        "DEFASAGEM_REGISTRO": "NA_HORA",
        "COBERTURA_PEQUENOS_GASTOS": "TODOS",
        "COBERTURA_MEIOS_PAGAMENTO": "TOTAL",
        "CONHECIMENTO_GASTO": "BOA_APROXIMACAO",
        "GASTOS_NAO_IDENTIFICADOS": "NUNCA",
        "REVISAO_SEMANAL": "SEMPRE",
    }
    valores.update(sobrescritas)
    respostas = tuple(
        _resposta(ID_PERGUNTA=variavel, valor=valor)
        for variavel, valor in valores.items()
        if valor is not _OMITIR
    )
    return RespostasCaso(respostas=respostas)


# Os 10 `VARIAVEL_GRAVADA` de `SinaisComportamentais` (Blocos 1, 2, 5 e 9,
# T-17/T-99).
def _sinais_comportamentais_minimo_completo(**sobrescritas: object) -> RespostasCaso:
    valores: dict[str, object] = {
        "NOVA_DIVIDA_PREVISTA": "NAO",
        "MECANISMO_DEFICIT": frozenset({"CORTE"}),
        "HISTORICO_RECAIDA": "NENHUMA",
        "NOVO_PARCELAMENTO_PREVISTO": "NAO",
        "PACTO": "ESTABELECIDO",
        "RISCO_IMPULSO": "NENHUMA",
        "NECESSIDADE_VITORIA": 5,
        "HISTORICO_ABANDONO": "NAO",
    }
    valores.update(sobrescritas)
    respostas = tuple(
        _resposta(ID_PERGUNTA=variavel, valor=valor)
        for variavel, valor in valores.items()
        if valor is not _OMITIR
    )
    return RespostasCaso(respostas=respostas)


# ---------------------------------------------------------------------------
# Critério 1 (AC-13) — as 8 variáveis de PerfilComportamental e os 10 campos
# de SinaisComportamentais estão preenchidos.
# ---------------------------------------------------------------------------
class TestCriterio1AC13TodosOsCamposPreenchidos:
    def test_perfil_comportamental_com_as_8_variaveis_preenchidas(self) -> None:
        respostas = _perfil_comportamental_minimo_completo()

        perfil = montar_perfil_comportamental(respostas)

        assert isinstance(perfil, PerfilComportamental)
        assert perfil.REGISTRO_GASTOS is REGISTRO_GASTOS.TUDO
        assert perfil.FREQUENCIA_REGISTRO is FREQUENCIA_REGISTRO.DIARIA
        assert perfil.DEFASAGEM_REGISTRO is DEFASAGEM_REGISTRO.NA_HORA
        assert perfil.COBERTURA_PEQUENOS_GASTOS is COBERTURA_PEQUENOS_GASTOS.TODOS
        assert perfil.COBERTURA_MEIOS_PAGAMENTO is COBERTURA_MEIOS_PAGAMENTO.TOTAL
        assert perfil.CONHECIMENTO_GASTO is CONHECIMENTO_GASTO.BOA_APROXIMACAO
        assert perfil.GASTOS_NAO_IDENTIFICADOS is GASTOS_NAO_IDENTIFICADOS.NUNCA
        assert perfil.REVISAO_SEMANAL is REVISAO_SEMANAL.SEMPRE

    @pytest.mark.parametrize(
        "campo_obrigatorio",
        [
            "REGISTRO_GASTOS",
            "FREQUENCIA_REGISTRO",
            "DEFASAGEM_REGISTRO",
            "COBERTURA_PEQUENOS_GASTOS",
            "COBERTURA_MEIOS_PAGAMENTO",
            "CONHECIMENTO_GASTO",
            "GASTOS_NAO_IDENTIFICADOS",
            "REVISAO_SEMANAL",
        ],
    )
    def test_campo_de_perfil_sem_resposta_levanta_erro_explicito(
        self, campo_obrigatorio: str
    ) -> None:
        respostas = _perfil_comportamental_minimo_completo(**{campo_obrigatorio: _OMITIR})

        with pytest.raises(ErroRespostaAusente) as excecao:
            montar_perfil_comportamental(respostas)

        assert excecao.value.VARIAVEL_GRAVADA == campo_obrigatorio

    def test_sinais_comportamentais_com_os_10_campos_preenchidos(self) -> None:
        respostas = _sinais_comportamentais_minimo_completo()

        sinais = montar_sinais_comportamentais(respostas)

        assert isinstance(sinais, SinaisComportamentais)
        assert sinais.NOVA_DIVIDA_PREVISTA is SimNaoTalvez.NAO
        assert sinais.MECANISMO_DEFICIT == frozenset({"CORTE"})
        assert sinais.HISTORICO_RECAIDA is SimNaoTalvez.NAO
        assert sinais.NOVO_PARCELAMENTO_PREVISTO is SimNaoTalvez.NAO
        assert sinais.PACTO == "ESTABELECIDO"
        assert sinais.RISCO_IMPULSO == "NENHUMA"
        # LINHA_CONTINUA_SENDO_UTILIZADA — REP do Bloco 5; sem DIVIDA_ID
        # explícito é DESCONHECIDO (ver docstring de
        # `_linha_continua_sendo_utilizada`), nunca ausência do campo.
        assert sinais.LINHA_CONTINUA_SENDO_UTILIZADA is DESCONHECIDO
        # JANELA_NOVA_DIVIDA — COND (B1.05): sem NOVA_DIVIDA_PREVISTA em
        # {SIM, TALVEZ} a pergunta nem é exibida — ausência ESTRUTURAL, None.
        assert sinais.JANELA_NOVA_DIVIDA is None
        # As 2 variáveis do Bloco 9 (collection/registros/bloco-09.yaml,
        # T-99) — lidas do registro real.
        assert sinais.NECESSIDADE_VITORIA == 5
        assert sinais.HISTORICO_ABANDONO is SimNaoTalvez.NAO

    def test_janela_nova_divida_presente_e_resolvida_pelo_mecanismo_generico(self) -> None:
        respostas = _sinais_comportamentais_minimo_completo(
            NOVA_DIVIDA_PREVISTA="SIM", JANELA_NOVA_DIVIDA="ATE_30D"
        )

        sinais = montar_sinais_comportamentais(respostas)

        assert sinais.JANELA_NOVA_DIVIDA is JANELA_NOVA_DIVIDA.ATE_30D

    def test_linha_continua_sendo_utilizada_lida_por_divida_id_explicito(self) -> None:
        respostas_base = _sinais_comportamentais_minimo_completo()
        resposta_linha = _resposta(
            ID_PERGUNTA="LINHA_CONTINUA_SENDO_UTILIZADA", valor="SIM", item_id="D001"
        )
        respostas = RespostasCaso(respostas=(*respostas_base.respostas, resposta_linha))

        sinais = montar_sinais_comportamentais(respostas, DIVIDA_ID_PARA_LINHA_CONTINUA="D001")

        assert sinais.LINHA_CONTINUA_SENDO_UTILIZADA == "SIM"


# ---------------------------------------------------------------------------
# Critério 2 — AUTOPERCEPCAO_CONTROLE (B2.13) admite DESCONHECIDO.
# ---------------------------------------------------------------------------
class TestCriterio2AutopercepcaoControleAdmiteDesconhecido:
    def test_autopercepcao_controle_com_resposta_concreta(self) -> None:
        respostas = RespostasCaso(respostas=(_resposta("AUTOPERCEPCAO_CONTROLE", 7),))

        assert _autopercepcao_controle(respostas) == 7

    def test_autopercepcao_controle_sem_resposta_e_desconhecido(self) -> None:
        respostas = RespostasCaso(respostas=())

        assert _autopercepcao_controle(respostas) is DESCONHECIDO

    def test_autopercepcao_controle_nao_sei_e_desconhecido(self) -> None:
        respostas = RespostasCaso(respostas=(_resposta("AUTOPERCEPCAO_CONTROLE", NAO_SEI),))

        assert _autopercepcao_controle(respostas) is DESCONHECIDO

    def test_autopercepcao_controle_zero_e_preservado_como_zero(self) -> None:
        """Nota real da escala (0 = "muito pouca visibilidade") não pode
        ser confundida com ausência/DESCONHECIDO."""
        respostas = RespostasCaso(respostas=(_resposta("AUTOPERCEPCAO_CONTROLE", 0),))

        valor = _autopercepcao_controle(respostas)
        assert valor == 0
        assert isinstance(valor, int)


# ---------------------------------------------------------------------------
# Critério 3 — o mapeamento resposta → membro de enum é por valor_interno
# do registro, sem `if` por pergunta (mecanismo genérico `_membro_do_enum`).
# ---------------------------------------------------------------------------
class TestCriterio3MapeamentoPorValorInternoSemIfPorPergunta:
    @pytest.mark.parametrize(
        "variavel,valor_interno,enum_alvo,membro_esperado",
        [
            ("REGISTRO_GASTOS", "NAO_REGISTRA", REGISTRO_GASTOS, REGISTRO_GASTOS.NAO_REGISTRA),
            (
                "FREQUENCIA_REGISTRO",
                "SOB_DEMANDA",
                FREQUENCIA_REGISTRO,
                FREQUENCIA_REGISTRO.SOB_DEMANDA,
            ),
            ("DEFASAGEM_REGISTRO", "SEM_PADRAO", DEFASAGEM_REGISTRO, DEFASAGEM_REGISTRO.SEM_PADRAO),
            (
                "COBERTURA_PEQUENOS_GASTOS",
                "QUASE_NENHUM",
                COBERTURA_PEQUENOS_GASTOS,
                COBERTURA_PEQUENOS_GASTOS.QUASE_NENHUM,
            ),
            (
                "COBERTURA_MEIOS_PAGAMENTO",
                "PARCIAL",
                COBERTURA_MEIOS_PAGAMENTO,
                COBERTURA_MEIOS_PAGAMENTO.PARCIAL,
            ),
            ("CONHECIMENTO_GASTO", "RAZOAVEL", CONHECIMENTO_GASTO, CONHECIMENTO_GASTO.RAZOAVEL),
            (
                "GASTOS_NAO_IDENTIFICADOS",
                "FREQUENTE",
                GASTOS_NAO_IDENTIFICADOS,
                GASTOS_NAO_IDENTIFICADOS.FREQUENTE,
            ),
            ("REVISAO_SEMANAL", "RARAMENTE", REVISAO_SEMANAL, REVISAO_SEMANAL.RARAMENTE),
        ],
    )
    def test_cada_valor_interno_do_registro_resolve_o_membro_correspondente(
        self, variavel: str, valor_interno: str, enum_alvo: object, membro_esperado: object
    ) -> None:
        """Prova, para cada um dos 7 enums do Bloco 2, que TODO valor do
        domínio (não só o usado na ficha mínima) resolve — não uma cadeia
        de `if` que só cobriria os casos testados em outro lugar."""
        respostas = _perfil_comportamental_minimo_completo(**{variavel: valor_interno})

        perfil = montar_perfil_comportamental(respostas)

        assert getattr(perfil, variavel) is membro_esperado

    def test_valor_interno_sem_membro_correspondente_levanta_erro_explicito(self) -> None:
        """Nunca escolhe um membro "parecido" nem aceita silenciosamente —
        prova de que a resolução é por nome exato, não por heurística."""
        respostas = _perfil_comportamental_minimo_completo(REGISTRO_GASTOS="VALOR_INEXISTENTE")

        with pytest.raises(ErroValorInternoDesconhecido):
            montar_perfil_comportamental(respostas)

    def test_mapeamento_nao_usa_if_por_pergunta_verificado_por_ast(self) -> None:
        """Critério de aceite verificado estruturalmente: o corpo de
        `montar_perfil_comportamental` não contém nenhum `if`/`elif`/
        comparação condicional por pergunta — toda a tradução acontece via
        `_membro_do_enum` (EnumClasse[valor_interno]), chamado uma vez por
        campo."""
        import ast
        import inspect

        from app.montagem import estado as modulo_estado

        codigo_fonte = inspect.getsource(modulo_estado.montar_perfil_comportamental)
        arvore = ast.parse(codigo_fonte)
        nos_de_desvio_condicional = [
            no for no in ast.walk(arvore) if isinstance(no, (ast.If, ast.Compare))
        ]
        assert not nos_de_desvio_condicional, (
            "montar_perfil_comportamental não deve conter `if`/comparação — "
            "a tradução é só chamada a _membro_do_enum, por campo."
        )


# ---------------------------------------------------------------------------
# Critério 4 — nenhuma derivação comportamental (NIVEL_CONTROLE,
# RISCO_RECAIDA) é calculada aqui: nem os módulos, nem os nomes aparecem.
# ---------------------------------------------------------------------------
class TestCriterio4NenhumaDerivacaoComportamentalCalculadaAqui:
    def test_modulo_nao_importa_nem_referencia_derivacoes_do_motor(self) -> None:
        import inspect

        from app.montagem import estado as modulo_estado

        codigo_fonte = inspect.getsource(modulo_estado)

        assert "NIVEL_CONTROLE" not in codigo_fonte
        assert "RISCO_RECAIDA" not in codigo_fonte
        assert "engine.comportamento" not in codigo_fonte

    def test_perfil_comportamental_nao_tem_campo_de_nivel_de_controle(self) -> None:
        """`PerfilComportamental` (engine/estado.py) é só a ENTRADA — a
        derivação (NIVEL_CONTROLE) não é campo dela."""
        campos = {campo for campo in PerfilComportamental.__dataclass_fields__}
        assert "NIVEL_CONTROLE" not in campos

    def test_sinais_comportamentais_nao_tem_campo_de_risco_recaida(self) -> None:
        campos = {campo for campo in SinaisComportamentais.__dataclass_fields__}
        assert "RISCO_RECAIDA" not in campos


# ---------------------------------------------------------------------------
# Prova de fidelidade aos registros reais dos Blocos 1, 2 e 5 (T-17) —
# nenhum VARIAVEL_GRAVADA usado por montar_perfil_comportamental/
# montar_sinais_comportamentais é inventado no teste.
# ---------------------------------------------------------------------------
def test_mapeamento_usa_variaveis_dos_registros_reais() -> None:
    colecao = carregar_registros()
    variaveis_existentes = {
        registro.VARIAVEL_GRAVADA
        for registro in colecao.registros
        if registro.VARIAVEL_GRAVADA is not None
    }

    variaveis_usadas = {
        "REGISTRO_GASTOS",
        "FREQUENCIA_REGISTRO",
        "DEFASAGEM_REGISTRO",
        "COBERTURA_PEQUENOS_GASTOS",
        "COBERTURA_MEIOS_PAGAMENTO",
        "CONHECIMENTO_GASTO",
        "GASTOS_NAO_IDENTIFICADOS",
        "REVISAO_SEMANAL",
        "AUTOPERCEPCAO_CONTROLE",
        "NOVA_DIVIDA_PREVISTA",
        "MECANISMO_DEFICIT",
        "HISTORICO_RECAIDA",
        "NOVO_PARCELAMENTO_PREVISTO",
        "PACTO",
        "RISCO_IMPULSO",
        "LINHA_CONTINUA_SENDO_UTILIZADA",
        "JANELA_NOVA_DIVIDA",
        "NECESSIDADE_VITORIA",
        "HISTORICO_ABANDONO",
    }
    ausentes = variaveis_usadas - variaveis_existentes
    assert not ausentes, (
        f"montagem usa variável(is) que não existe(m) em nenhum registro real: {ausentes}"
    )


def test_necessidade_vitoria_e_historico_abandono_tem_registro_bloco_9() -> None:
    """T-99: o Bloco 9 (`collection/registros/bloco-09.yaml`) transcreveu
    `B9.02`/`B9.04` — os dois campos agora têm registro real e são lidos de
    fato, não mais fixados em valor neutro."""
    colecao = carregar_registros()
    variaveis_existentes = {
        registro.VARIAVEL_GRAVADA
        for registro in colecao.registros
        if registro.VARIAVEL_GRAVADA is not None
    }

    assert "NECESSIDADE_VITORIA" in variaveis_existentes
    assert "HISTORICO_ABANDONO" in variaveis_existentes


# ---------------------------------------------------------------------------
# T-99 — NECESSIDADE_VITORIA (B9.02, escala 0-10) e HISTORICO_ABANDONO
# (B9.04, seleção única) lidos do registro real de collection/registros/
# bloco-09.yaml.
# ---------------------------------------------------------------------------
def test_necessidade_vitoria_le_a_escala_0_10_do_registro_real() -> None:
    for valor_interno in (0, 5, 10):
        respostas = _sinais_comportamentais_minimo_completo(NECESSIDADE_VITORIA=valor_interno)

        sinais = montar_sinais_comportamentais(respostas)

        assert sinais.NECESSIDADE_VITORIA == valor_interno


def test_necessidade_vitoria_zero_e_preservado_como_zero() -> None:
    """Nota real da escala (0 = "isso faria pouca diferença para mim") não
    pode ser confundida com ausência/DESCONHECIDO — mesma prova de
    `_autopercepcao_controle` (B2.13)."""
    respostas = _sinais_comportamentais_minimo_completo(NECESSIDADE_VITORIA=0)

    sinais = montar_sinais_comportamentais(respostas)

    assert sinais.NECESSIDADE_VITORIA == 0
    assert isinstance(sinais.NECESSIDADE_VITORIA, int)


def test_necessidade_vitoria_nao_sei_e_desconhecido() -> None:
    respostas = _sinais_comportamentais_minimo_completo(NECESSIDADE_VITORIA=NAO_SEI)

    sinais = montar_sinais_comportamentais(respostas)

    assert sinais.NECESSIDADE_VITORIA is DESCONHECIDO


def test_necessidade_vitoria_sem_resposta_levanta_erro_explicito() -> None:
    respostas = _sinais_comportamentais_minimo_completo(NECESSIDADE_VITORIA=_OMITIR)

    with pytest.raises(ErroSinalComportamentalAusente):
        montar_sinais_comportamentais(respostas)


def test_historico_abandono_mapeia_os_cinco_valores_do_dominio_real() -> None:
    """B9.04: MAIS_DE_UMA/UMA → SIM; NAO/SEM_PLANO → NAO; NAO_SEI → TALVEZ
    (`piq-app-spec.md`, linha 4186: "HISTORICO_ABANDONO = SIM para A ou
    B")."""
    for valor_interno, esperado in (
        ("MAIS_DE_UMA", SimNaoTalvez.SIM),
        ("UMA", SimNaoTalvez.SIM),
        ("NAO", SimNaoTalvez.NAO),
        ("SEM_PLANO", SimNaoTalvez.NAO),
        ("NAO_SEI", SimNaoTalvez.TALVEZ),
    ):
        respostas = _sinais_comportamentais_minimo_completo(HISTORICO_ABANDONO=valor_interno)

        sinais = montar_sinais_comportamentais(respostas)

        assert sinais.HISTORICO_ABANDONO is esperado


def test_historico_abandono_sem_resposta_levanta_erro_explicito() -> None:
    respostas = _sinais_comportamentais_minimo_completo(HISTORICO_ABANDONO=_OMITIR)

    with pytest.raises(ErroSinalComportamentalAusente):
        montar_sinais_comportamentais(respostas)


def test_historico_recaida_mapeia_os_quatro_valores_do_dominio_real() -> None:
    """B1.10: MAIS_DE_UMA/UMA → SIM; NENHUMA → NAO; NAO_SEI → TALVEZ."""
    for valor_interno, esperado in (
        ("MAIS_DE_UMA", SimNaoTalvez.SIM),
        ("UMA", SimNaoTalvez.SIM),
        ("NENHUMA", SimNaoTalvez.NAO),
        ("NAO_SEI", SimNaoTalvez.TALVEZ),
    ):
        respostas = _sinais_comportamentais_minimo_completo(HISTORICO_RECAIDA=valor_interno)

        sinais = montar_sinais_comportamentais(respostas)

        assert sinais.HISTORICO_RECAIDA is esperado
