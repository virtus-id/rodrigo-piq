"""Testes de `contar_coleta` e da varredura única de `app/casos/progresso.py`
— `RF-62`, `AC-90` (T-146).

`contar_coleta` dá o *"62 de 195"* da barra de progresso da tela Início. Os
três números (`respondidas`, `faltam`, `total`) saem da MESMA varredura que
`proxima_pergunta_nao_respondida` consome — `_percorrer_ocorrencias`, com os
predicados da **retomada** —, e é isso que impede a barra e o "continuar de
onde parei" de divergirem.

Este módulo cobre três frentes:

1. **`AC-90`** — `respondidas + faltam == total` sobre os registros REAIS
   (`carregar_registros()`), em estados de resposta diferentes: nenhuma
   resposta, algumas, e todas as perguntas abertas respondidas.
2. **`total` conta só o que está aberto agora** — um registro real cuja
   `condicao_exibicao` é falsa NÃO entra no denominador; respondida a
   pergunta que abre a condição, o denominador AUMENTA. O denominador variar
   é correto: exibir um total que inclui perguntas que nunca abrirão mentiria
   sobre o tamanho do trabalho restante.
3. **Não-regressão do refactor de T-146** — `proxima_pergunta_nao_respondida`
   e `pendencias_obrigatorias` mantêm o comportamento anterior, inclusive a
   **divergência deliberada** entre as duas varreduras: uma pergunta
   repetível por item CONDICIONAL **sem** o membro `REP` (Blocos 7, 8 e 11) é
   vista pela retomada e não pela pendência bloqueante.

> A coleção tem **247** registros. Nenhuma asserção aqui afirma `245` — essa
> contagem envelheceu quando `bloco-09.yaml` entrou.

REGRAS: `RF-31`, `RF-62`, `AC-01`, `AC-11`, `AC-90`
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from functools import cache
from typing import Final

from app.casos.progresso import (
    ContagemDeColeta,
    PendenciaObrigatoria,
    contar_coleta,
    pendencias_obrigatorias,
    proxima_pergunta_nao_respondida,
)
from collection.carga import carregar_registros
from collection.condicoes import CondicaoIgual, avaliar
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
)
from collection.respostas import Resposta, RespostasCaso

# `OBRIGACAO_FUTURA_INEVITAVEL == SIM` é a condição real que abre `B1.06A`,
# `B1.06B` e `B1.06C` — três registros não repetíveis, do Bloco 1, todos com
# `condicao_exibicao` idêntica. É o caso mais limpo dos registros reais para
# provar que o denominador só conta o que está aberto.
_VARIAVEL_QUE_ABRE: Final[str] = "OBRIGACAO_FUTURA_INEVITAVEL"
_IDS_ABERTOS_PELA_CONDICAO: Final[tuple[str, ...]] = ("B1.06A", "B1.06B", "B1.06C")

# `B7.13A` é o caso real da divergência deliberada: `obrigatoriedade=[COND]`
# (sem `REP`) com `escopo_repeticao=DIVIDA_ID`. Ver
# `_percorrer_ocorrencias`: ali `REP` qualificaria "obrigatório por item", e
# a retomada precisa oferecer toda pergunta que o aluno de fato VERIA por
# item, inclusive as só `COND`.
_ID_CONDICIONAL_POR_ITEM_SEM_REP: Final[str] = "B7.13A"
_VARIAVEL_QUE_ABRE_B7_13A: Final[str] = "PROPOSTA_DESCONTO_EXISTE"

# `B1.03A` é a ÚNICA pergunta `OPT` pura dos 247 registros reais (as demais
# combinações são `OBR`, `COND`, `REP` e `COND`+`REP`). Ela é condicional,
# então o teste que a usa precisa abrir a condição primeiro.
_ID_OPCIONAL_PURO: Final[str] = "B1.03A"


@cache
def _registros_reais() -> tuple[RegistroPergunta, ...]:
    """Os 247 registros REAIS, carregados dos YAML de `collection/registros/`.

    `@cache` porque `carregar_registros()` reparseia os YAML a cada chamada —
    sem ele, os testes que consultam registro por `ID` dentro de um laço
    passam a dominar o tempo da suíte. O valor é imutável (tupla de
    dataclasses `frozen`), então compartilhá-lo entre testes não acopla um ao
    outro."""
    return carregar_registros().registros


def _registro_real(ID: str) -> RegistroPergunta:
    return next(r for r in _registros_reais() if r.ID == ID)


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    """Mesmo formato de `tests/app_aluno/test_progresso.py::_resposta`.

    `ID_PERGUNTA` recebe a `VARIAVEL_GRAVADA` porque é por ela que
    `RespostasCaso` indexa — mesma convenção de `app/http/rotas_coleta.py`."""
    return Resposta(
        CASO_ID="CASO-CONTAGEM",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 9, 17, tzinfo=UTC),
    )


def _variavel_de(registro: RegistroPergunta) -> str:
    assert registro.VARIAVEL_GRAVADA is not None
    return registro.VARIAVEL_GRAVADA


# ---------------------------------------------------------------------------
# `AC-90` — `respondidas + faltam == total`, sobre os registros REAIS, em
# três estados de resposta diferentes.
#
# ⚠️ **A soma sozinha é TAUTOLÓGICA e não prova nada.** `ContagemDeColeta`
# define `respondidas = total - faltam`, então `(t - f) + f == t` vale mesmo
# que `contar_coleta` esteja completamente errada. Ela fica nos testes porque
# documenta o contrato, mas quem de fato morde é:
#
#   - as asserções LATERAIS de cada teste (`respondidas == 0`, `faltam > 0`,
#     tuplas exatas), que fixam os valores;
#   - `_contar_por_fora`, abaixo, que reconta com uma varredura INDEPENDENTE
#     e compara. É ela que falha se a varredura de produção mudar de
#     comportamento.
# ---------------------------------------------------------------------------


def _contar_por_fora(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> tuple[int, int]:
    """Reconta `(respondidas, total)` SEM usar nada de `progresso.py` além do
    avaliador de condição — que é a definição de "aberta" e não faria sentido
    duplicar.

    O ponto é não compartilhar o percurso com a produção: se
    `_percorrer_ocorrencias` passar a pular uma ocorrência, ou a contar um
    item duas vezes, os números divergem e o teste falha. Comparar
    `contar_coleta` consigo mesma nunca pegaria isso."""
    itens_por_escopo = itens_por_escopo or {}
    respondidas = 0
    total = 0

    for registro in registros:
        if registro.condicao_exibicao is not None and not avaliar(
            registro.condicao_exibicao, respostas
        ):
            continue

        variavel = registro.VARIAVEL_GRAVADA
        assert variavel is not None, f"{registro.ID} sem variável gravada"

        if registro.escopo_repeticao != EscopoRepeticao.NENHUM:
            for item_id in itens_por_escopo.get(registro.escopo_repeticao, ()):
                total += 1
                if respostas.valor_no_item(item_id, variavel) is not None:
                    respondidas += 1
            continue

        total += 1
        if respostas.valor(variavel) is not None:
            respondidas += 1

    return respondidas, total


def test_ac90_a_contagem_bate_com_uma_varredura_independente() -> None:
    """`AC-90` — a asserção que de fato morde.

    Reconta por fora, com percurso próprio, e exige o mesmo resultado. É o
    teste que falha se a varredura de produção regredir — ao contrário da
    soma, que vale por definição da dataclass."""
    registros = _registros_reais()
    itens = {EscopoRepeticao.DIVIDA_ID: ("D001", "D002", "D003")}
    respostas = RespostasCaso(
        respostas=(
            _resposta("PACTO", "ESTABELECIDO"),
            _resposta(_VARIAVEL_QUE_ABRE, "SIM"),
        )
    )

    contagem = contar_coleta(registros, respostas, itens)
    respondidas, total = _contar_por_fora(registros, respostas, itens)

    assert (contagem.respondidas, contagem.total) == (respondidas, total)
    assert contagem.faltam == total - respondidas


def test_ac90_invariante_vale_sem_nenhuma_resposta_gravada() -> None:
    """`AC-90` — caso recém-criado: tudo falta, nada foi respondido, e a
    soma fecha."""
    registros = _registros_reais()

    contagem = contar_coleta(registros, RespostasCaso(respostas=()))

    assert contagem.respondidas + contagem.faltam == contagem.total
    assert contagem.respondidas == 0
    assert contagem.total > 0


def test_ac90_invariante_vale_com_algumas_respostas_gravadas() -> None:
    """`AC-90` — estado intermediário, que é o da barra na vida real: parte
    respondida, parte em branco, e a soma continua fechando."""
    registros = _registros_reais()
    respostas = RespostasCaso(
        respostas=(
            _resposta("PACTO", "ESTABELECIDO"),
            _resposta(_VARIAVEL_QUE_ABRE, "SIM"),
            _resposta("TIPO_OBRIGACAO_FUTURA", "IPVA"),
        )
    )

    contagem = contar_coleta(registros, respostas)

    assert contagem.respondidas + contagem.faltam == contagem.total
    assert contagem.respondidas > 0
    assert contagem.faltam > 0


def test_ac90_invariante_vale_com_todas_as_perguntas_abertas_respondidas() -> None:
    """`AC-90` — o extremo oposto: respondendo TODA pergunta aberta, `faltam`
    zera e `respondidas == total`.

    O conjunto de perguntas abertas é descoberto pela própria varredura, não
    por uma lista transcrita — e responder as abertas pode ABRIR outras
    (condição que vira verdadeira), então o laço itera até estabilizar. Isso
    é o denominador dinâmico de `RF-62` funcionando: ele cresce conforme o
    aluno responde, e o invariante segue valendo **em cada passo**.

    O recorte é o Bloco 1 REAL (16 registros, com condicionais reais entre
    eles) e não a coleção inteira: exaurir 247 registros custaria mais de um
    minuto por reconstrução de índice, sem exercitar nada que o Bloco 1 já
    não exercite — condição que abre pergunta, pergunta sempre aberta e
    pergunta `OPT`."""
    por_id = {registro.ID: registro for registro in _registros_reais()}
    registros = tuple(r for r in por_id.values() if r.bloco == 1)
    assert len(registros) == 16
    respostas = RespostasCaso(respostas=())

    for _ in range(len(registros) * 2):
        pendencia = proxima_pergunta_nao_respondida(registros, respostas)
        if pendencia is None:
            break
        respostas = RespostasCaso(
            respostas=(
                *respostas.respostas,
                _resposta(
                    _variavel_de(por_id[pendencia.ID]), "RESPOSTA-QUALQUER"
                ),
            )
        )
        contagem_parcial = contar_coleta(registros, respostas)
        assert (
            contagem_parcial.respondidas + contagem_parcial.faltam
            == contagem_parcial.total
        )
    else:  # pragma: no cover — defensivo: a varredura não estabilizou
        raise AssertionError("a varredura não estabilizou")

    contagem = contar_coleta(registros, respostas)

    assert contagem.faltam == 0
    assert contagem.respondidas == contagem.total
    assert contagem.respondidas + contagem.faltam == contagem.total


def test_ac90_invariante_vale_com_fichas_repetiveis_ativas() -> None:
    """`AC-90` — com itens ativos por escopo, as ocorrências por item entram
    na contagem e o invariante continua valendo. Duas dívidas produzem um
    total MAIOR que nenhuma: a ficha repetida é trabalho real do aluno."""
    registros = _registros_reais()
    respostas = RespostasCaso(respostas=())

    sem_itens = contar_coleta(registros, respostas)
    com_duas_dividas = contar_coleta(
        registros, respostas, {EscopoRepeticao.DIVIDA_ID: ("D001", "D002")}
    )

    assert com_duas_dividas.respondidas + com_duas_dividas.faltam == (
        com_duas_dividas.total
    )
    assert com_duas_dividas.total > sem_itens.total


def test_ac90_resposta_em_um_item_nao_conta_pelo_outro() -> None:
    """`AC-90` — responder a ficha de `D001` move a barra em uma unidade, não
    nas duas: a ocorrência de `D002` continua em branco."""
    registro = _registro_real("B5.B01")
    itens = {EscopoRepeticao.DIVIDA_ID: ("D001", "D002")}

    vazio = contar_coleta((registro,), RespostasCaso(respostas=()), itens)
    respondido_em_d001 = contar_coleta(
        (registro,),
        RespostasCaso(
            respostas=(_resposta(_variavel_de(registro), "Cartão", item_id="D001"),)
        ),
        itens,
    )

    assert vazio == ContagemDeColeta(respondidas=0, faltam=2, total=2)
    assert respondido_em_d001 == ContagemDeColeta(respondidas=1, faltam=1, total=2)


# ---------------------------------------------------------------------------
# `RF-62` — `total` conta apenas as perguntas ABERTAS agora.
# ---------------------------------------------------------------------------


def test_rf62_pergunta_com_condicao_falsa_nao_entra_no_total() -> None:
    """`RF-62` — `B1.06A` só abre com `OBRIGACAO_FUTURA_INEVITAVEL == SIM`.
    Respondido `NAO`, a pergunta não é contada: ela nunca será exibida neste
    estado, e incluí-la no denominador mentiria sobre o trabalho restante."""
    registro_condicional = _registro_real(_IDS_ABERTOS_PELA_CONDICAO[0])
    assert isinstance(registro_condicional.condicao_exibicao, CondicaoIgual)
    assert registro_condicional.condicao_exibicao.variavel == _VARIAVEL_QUE_ABRE

    respostas_com_condicao_falsa = RespostasCaso(
        respostas=(_resposta(_VARIAVEL_QUE_ABRE, "NAO"),)
    )

    contagem = contar_coleta((registro_condicional,), respostas_com_condicao_falsa)

    assert contagem == ContagemDeColeta(respondidas=0, faltam=0, total=0)


def test_rf62_total_aumenta_quando_a_resposta_abre_a_condicao() -> None:
    """`RF-62` — a mesma pergunta, agora com a condição verdadeira, entra no
    denominador. Sobre os registros REAIS, responder `SIM` abre `B1.06A`,
    `B1.06B` e `B1.06C`: o total sobe exatamente três, e todas as três
    entram como faltantes."""
    registros = _registros_reais()

    com_condicao_falsa = contar_coleta(
        registros, RespostasCaso(respostas=(_resposta(_VARIAVEL_QUE_ABRE, "NAO"),))
    )
    com_condicao_verdadeira = contar_coleta(
        registros, RespostasCaso(respostas=(_resposta(_VARIAVEL_QUE_ABRE, "SIM"),))
    )

    assert com_condicao_verdadeira.total > com_condicao_falsa.total
    assert com_condicao_verdadeira.total - com_condicao_falsa.total == len(
        _IDS_ABERTOS_PELA_CONDICAO
    )
    # Abrir perguntas novas NÃO muda quantas já foram respondidas — só o
    # denominador e o que falta.
    assert com_condicao_verdadeira.respondidas == com_condicao_falsa.respondidas
    assert com_condicao_verdadeira.faltam - com_condicao_falsa.faltam == len(
        _IDS_ABERTOS_PELA_CONDICAO
    )
    assert (
        com_condicao_verdadeira.respondidas + com_condicao_verdadeira.faltam
        == com_condicao_verdadeira.total
    )


def test_rf62_pergunta_sem_condicao_esta_sempre_no_total() -> None:
    """`RF-62` — registro sem `condicao_exibicao` nunca depende de nada para
    ser contado: está sempre aberto."""
    registro_sempre_aberto = _registro_real("B1.01")
    assert registro_sempre_aberto.condicao_exibicao is None

    contagem = contar_coleta((registro_sempre_aberto,), RespostasCaso(respostas=()))

    assert contagem == ContagemDeColeta(respondidas=0, faltam=1, total=1)


def test_rf62_barra_conta_o_que_o_aluno_ve_nao_so_o_que_bloqueia() -> None:
    """`RF-62` — a barra usa os predicados da RETOMADA, não os da pendência:
    uma pergunta `OPT` pura (que não bloqueia o avanço) é contada, porque o
    aluno a vê e a responde.

    Se a barra usasse os predicados da pendência, ela andaria para trás
    quando uma condição abrisse um bloco novo, e o aluno responderia
    perguntas que ela não conta."""
    registro_opcional = _registro_real(_ID_OPCIONAL_PURO)
    assert registro_opcional.obrigatoriedade == frozenset({Obrigatoriedade.OPT})
    assert isinstance(registro_opcional.condicao_exibicao, CondicaoIgual)

    # Abre a condição da única pergunta `OPT` pura da coleção real.
    respostas = RespostasCaso(
        respostas=(
            _resposta(
                registro_opcional.condicao_exibicao.variavel,
                registro_opcional.condicao_exibicao.valor,
            ),
        )
    )

    contagem = contar_coleta((registro_opcional,), respostas)

    assert contagem == ContagemDeColeta(respondidas=0, faltam=1, total=1)
    assert pendencias_obrigatorias((registro_opcional,), respostas) == ()


# ---------------------------------------------------------------------------
# Não-regressão do refactor de T-146 — as duas varreduras antigas continuam
# com o comportamento de antes, inclusive na divergência DELIBERADA.
# ---------------------------------------------------------------------------


def test_ac01_retomada_devolve_a_primeira_pergunta_aberta_em_branco() -> None:
    """`AC-01` (não-regressão) — sobre os registros reais sem nenhuma
    resposta, a retomada aponta para `B1.01`, a primeira pergunta do primeiro
    bloco, exatamente como antes do refactor."""
    registros = _registros_reais()

    pendencia = proxima_pergunta_nao_respondida(registros, RespostasCaso(respostas=()))

    assert pendencia == PendenciaObrigatoria(ID="B1.01", item_id=None)


def test_ac01_retomada_pula_a_pergunta_ja_respondida() -> None:
    """`AC-01` (não-regressão) — respondida a primeira, a retomada avança
    para a seguinte em branco, e nunca reapresenta a já respondida."""
    registros = _registros_reais()
    respostas = RespostasCaso(respostas=(_resposta("PACTO", "ESTABELECIDO"),))

    pendencia = proxima_pergunta_nao_respondida(registros, respostas)

    assert pendencia is not None
    assert pendencia.ID != "B1.01"


def test_ac11_pendencia_obrigatoria_continua_devolvendo_so_os_obr() -> None:
    """`AC-11` (não-regressão) — a varredura de pendência segue mais estreita
    que a de retomada: sobre os registros reais sem resposta, toda pendência
    devolvida declara `OBR`, e há menos pendências do que ocorrências
    contadas pela barra."""
    registros = _registros_reais()
    respostas = RespostasCaso(respostas=())

    pendencias = pendencias_obrigatorias(registros, respostas)
    contagem = contar_coleta(registros, respostas)

    assert pendencias
    for pendencia in pendencias:
        assert Obrigatoriedade.OBR in _registro_real(pendencia.ID).obrigatoriedade
    assert len(pendencias) < contagem.total


def test_ac01_ac11_condicional_por_item_sem_rep_e_vista_so_pela_retomada() -> None:
    """A DIVERGÊNCIA DELIBERADA, preservada pelo gerador parametrizado.

    `B7.13A` é real: `obrigatoriedade=[COND]` (**sem** `REP`) com
    `escopo_repeticao=DIVIDA_ID`. Com a condição aberta e duas dívidas
    ativas:

    - a **retomada** (`AC-01`) a oferece por item — o aluno de fato veria a
      pergunta na ficha de `D001`;
    - a **pendência bloqueante** (`AC-11`) não a devolve — ela não é
      obrigatória por item, e não deve travar o avanço.

    Um `_ocorrencias_abertas` que fixasse um dos dois predicados quebraria
    uma das duas. É este teste que segura o refactor."""
    registro = _registro_real(_ID_CONDICIONAL_POR_ITEM_SEM_REP)
    assert Obrigatoriedade.REP not in registro.obrigatoriedade
    assert registro.escopo_repeticao is EscopoRepeticao.DIVIDA_ID

    respostas = RespostasCaso(
        respostas=(_resposta(_VARIAVEL_QUE_ABRE_B7_13A, "SIM"),)
    )
    itens = {EscopoRepeticao.DIVIDA_ID: ("D001", "D002")}

    retomada = proxima_pergunta_nao_respondida((registro,), respostas, itens)
    pendencias = pendencias_obrigatorias((registro,), respostas, itens)

    assert retomada == PendenciaObrigatoria(ID="B7.13A", item_id="D001")
    assert pendencias == ()


def test_rf62_barra_conta_a_condicional_por_item_sem_rep_em_cada_item() -> None:
    """`RF-62` — a barra usa os predicados da RETOMADA, então ela conta a
    mesma `B7.13A` uma vez por dívida ativa. É o que garante que "continuar
    de onde parei" aponte sempre para dentro do que a barra está medindo."""
    registro = _registro_real(_ID_CONDICIONAL_POR_ITEM_SEM_REP)
    respostas = RespostasCaso(
        respostas=(_resposta(_VARIAVEL_QUE_ABRE_B7_13A, "SIM"),)
    )

    contagem = contar_coleta(
        (registro,), respostas, {EscopoRepeticao.DIVIDA_ID: ("D001", "D002")}
    )

    assert contagem == ContagemDeColeta(respondidas=0, faltam=2, total=2)


def test_rf62_sem_item_ativo_a_pergunta_por_item_nao_entra_no_total() -> None:
    """`RF-62` — sem nenhuma dívida cadastrada não há ficha a preencher, e a
    pergunta por item não é contada. Nunca se inventa item (mesma convenção
    de `pendencias_obrigatorias`)."""
    registro = _registro_real(_ID_CONDICIONAL_POR_ITEM_SEM_REP)
    respostas = RespostasCaso(
        respostas=(_resposta(_VARIAVEL_QUE_ABRE_B7_13A, "SIM"),)
    )

    contagem = contar_coleta((registro,), respostas)

    assert contagem == ContagemDeColeta(respondidas=0, faltam=0, total=0)


def test_rf62_contagem_e_retomada_nunca_divergem_sobre_os_registros_reais() -> None:
    """`RF-62` — o contrato central do refactor: `faltam == 0` se e somente
    se a retomada devolve `None`. Barra zerada e "nada pendente" são o mesmo
    fato, medido pela mesma varredura.

    Verificado nos dois sentidos, sobre a coleção real (247 registros)."""
    registros = _registros_reais()

    respostas_vazias = RespostasCaso(respostas=())
    assert contar_coleta(registros, respostas_vazias).faltam > 0
    assert proxima_pergunta_nao_respondida(registros, respostas_vazias) is not None

    # Um recorte cuja única pergunta já está respondida: a retomada devolve
    # `None` e a barra marca zero faltando.
    registro_respondido = _registro_real("B1.01")
    respostas = RespostasCaso(
        respostas=(_resposta(_variavel_de(registro_respondido), "ESTABELECIDO"),)
    )
    assert contar_coleta((registro_respondido,), respostas).faltam == 0
    assert proxima_pergunta_nao_respondida((registro_respondido,), respostas) is None


def test_a_colecao_real_tem_244_registros() -> None:
    """Âncora explícita contra a contagem envelhecida: a coleção de COLETA
    tem **244** registros.

    Foram 247 até `T-172`, quando os três casos de prova do gerador
    (`B12.08`, `B12.15`, `B12.16`) saíram da coleção que a aplicação
    carrega. Eles nunca foram fluxo de coleta — o cabeçalho de
    `bloco-12-casos-de-prova.yaml` diz isso em caixa alta desde `T-19` —, e
    `B12.16` tornava `POST /caso/{id}/calculo` inalcançável: `OBR`, sempre
    aberta, com opções vindas de um campo do snapshot que só existe DEPOIS
    do cálculo que ela bloqueava.

    Continuam carregáveis com `carregar_registros(incluir_casos_de_prova=
    True)`, que é o que `test_gerador.py` usa para exercitar os três
    mecanismos que elas existem para provar."""
    assert len(_registros_reais()) == 244


def test_os_casos_de_prova_do_gerador_ficam_fora_da_coleta() -> None:
    """`T-172` — as três perguntas do Bloco 12 não entram no fluxo de coleta,
    e continuam disponíveis sob pedido explícito.

    Sem esta trava, um arquivo novo de casos de prova voltaria a entrar na
    coleção sem que ninguém percebesse — e o sintoma (cálculo bloqueado para
    sempre) só apareceria com a coleta inteira respondida."""
    da_coleta = {registro.ID for registro in _registros_reais()}
    com_provas = {
        registro.ID for registro in carregar_registros(incluir_casos_de_prova=True).registros
    }

    assert com_provas - da_coleta == {"B12.08", "B12.15", "B12.16"}
    for ID in ("B12.08", "B12.15", "B12.16"):
        assert ID not in da_coleta, f"{ID} voltou para o fluxo de coleta"
