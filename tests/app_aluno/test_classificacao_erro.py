"""Testes de `CLASSIFICACAO_ERRO` — `RF-26`, `T-72`.

Cobre os quatro critérios de aceite de T-72:

1. O enum tem exatamente os seis membros, com os nomes da §15.3.
2. Nenhuma descrição, definição ou exemplo de categoria aparece na tela ou
   no código — auditoria estática sobre `app/revisao/fila.py` e sobre
   `GET /revisao/caso/{id}/decisao`, que é o que a tela recebe.

   **T-144 mudou o alvo desta auditoria, não a regra.** A tela do revisor
   era `report/templates/revisao/decisao.html` e virou React; o `<select>`
   de classificação agora é montado no cliente a partir do JSON da rota.
   Auditar o template continuaria passando para sempre — o arquivo não
   existe mais —, então a prova migrou para onde os rótulos de fato saem
   do servidor.
3. O campo livre (`observacao`) acompanha a classificação e é gravado no
   `RegistroRevisao` junto com `classificacao_erro` — já coberto pelos
   testes de `test_rotas_revisao_decisao.py` (T-71) para `observacao`;
   aqui a prova adicional é que os dois campos coexistem no mesmo registro
   sem se substituírem.
4. O código registra, em comentário, que `OQ-12` está aberta e que a glosa
   (texto explicativo de cada categoria) entra quando ela for respondida.

REGRAS: RF-26
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path

from app.revisao.fila import CLASSIFICACAO_ERRO, DECISAO_REVISAO, RegistroRevisao

_RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent
_ARQUIVO_FILA = _RAIZ_PROJETO / "app" / "revisao" / "fila.py"

# Os seis nomes exatos confirmados contra `specs/piq-app-spec.md` §15.3 e
# `specs/app-aluno.spec.md` (RF-26/OQ-12): "TEXTO, PARÂMETRO, DADO, REGRA,
# CÁLCULO, UX" — sem acento no identificador Python (mesma convenção de
# `CLASSIFICACAO_FIXA_VARIAVEL`/`CLASSIFICACAO_OBRIGATORIA`, já existentes
# no motor, que também usam nomes ASCII para conceitos com acento na prosa).
_SEIS_NOMES_CANONICOS: tuple[str, ...] = (
    "TEXTO",
    "PARAMETRO",
    "DADO",
    "REGRA",
    "CALCULO",
    "UX",
)

# Palavras que só apareceriam se alguém tivesse inventado uma glosa (uma
# frase explicando o que cada categoria significa) — nenhuma delas é um
# nome de rótulo, então sua presença perto do enum ou do template denunciaria
# uma definição não autorizada por `OQ-12`.
_PISTAS_DE_GLOSA_INVENTADA: tuple[str, ...] = (
    "significa",
    "refere-se",
    "trata de erro",
    "é usado quando",
    "exemplo:",
    "por exemplo",
)


# ---------------------------------------------------------------------------
# Critério 1 — o enum tem exatamente os seis membros, com os nomes da §15.3.
# ---------------------------------------------------------------------------


def test_classificacao_erro_tem_exatamente_os_seis_membros_da_spec() -> None:
    nomes_do_enum = {membro.name for membro in CLASSIFICACAO_ERRO}
    assert nomes_do_enum == set(_SEIS_NOMES_CANONICOS)
    assert len(CLASSIFICACAO_ERRO) == 6


def test_classificacao_erro_valores_coincidem_com_os_nomes() -> None:
    """Cada `.value` é igual ao próprio nome — nenhum apelido, nenhuma
    tradução, nenhuma reescrita: o enum é uma transcrição literal dos seis
    rótulos, sem acrescentar nem remover nada."""
    for nome in _SEIS_NOMES_CANONICOS:
        membro = CLASSIFICACAO_ERRO[nome]
        assert membro.value == nome


# ---------------------------------------------------------------------------
# Critério 2 — nenhuma descrição/definição/exemplo de categoria aparece na
# tela nem no código. Auditoria estática: nenhuma "pista de glosa" perto da
# declaração do enum ou do `<select>` do template.
# ---------------------------------------------------------------------------


def test_nenhuma_pista_de_glosa_inventada_no_modulo_fila() -> None:
    """Lê `app/revisao/fila.py` por inteiro e garante que nenhuma das
    palavras/expressões típicas de uma DEFINIÇÃO de categoria aparece —
    prova negativa de que a docstring do enum (que É permitida, e é longa)
    não deriva para uma glosa não autorizada por `OQ-12`."""
    codigo_fonte = _ARQUIVO_FILA.read_text(encoding="utf-8").lower()
    violacoes = [pista for pista in _PISTAS_DE_GLOSA_INVENTADA if pista in codigo_fonte]
    assert not violacoes, (
        f"pista(s) de glosa inventada encontrada(s) em {_ARQUIVO_FILA}: {violacoes}"
    )


def _corpo_da_rota_sem_docstring() -> str:
    """O código da rota de decisão, SEM a docstring.

    **Por que `ast` e não aritmética de aspas.** A versão anterior fatiava
    a fonte procurando o terceiro `\"\"\"` por índice. Isso quebra de duas
    formas: qualquer docstring com aspas triplas no meio desloca a conta, e
    `inspect.getsource` relê o ARQUIVO — se ele for editado enquanto a
    suíte roda, o corte cai no lugar errado e o teste falha por um motivo
    que nada tem a ver com a regra que ele audita. Foi exatamente o que
    aconteceu em T-145.

    `ast` remove a docstring pela estrutura do código, não por contagem de
    caracteres."""
    import ast
    import textwrap

    from app.http import rotas_revisao

    fonte = inspect.getsource(rotas_revisao.formulario_de_decisao)
    arvore = ast.parse(textwrap.dedent(fonte))
    funcao = arvore.body[0]
    assert isinstance(funcao, ast.FunctionDef), "esperava uma função"

    corpo = funcao.body
    if (
        corpo
        and isinstance(corpo[0], ast.Expr)
        and isinstance(corpo[0].value, ast.Constant)
        and isinstance(corpo[0].value.value, str)
    ):
        corpo = corpo[1:]  # a docstring é documento de projeto, não vai à tela

    return "\n".join(ast.unparse(no) for no in corpo)


def _classificacoes_servidas_ao_revisor() -> list[str]:
    """Os rótulos que a rota de decisão entrega à tela.

    **O alvo da auditoria mudou de arquivo, não de regra** (T-144). A tela
    do revisor era `report/templates/revisao/decisao.html` e virou React; o
    que chega ao navegador agora é o JSON de `GET /revisao/caso/{id}/
    decisao`. O critério de aceite continua o mesmo — "nenhuma descrição
    aparece na tela" —, e é sobre o que o servidor entrega."""
    assert "classificacoes_erro" in _corpo_da_rota_sem_docstring()
    return [c.value for c in CLASSIFICACAO_ERRO]


def test_rota_de_decisao_expoe_so_os_seis_rotulos_sem_glosa() -> None:
    """A rota entrega os seis rótulos como NOMES PUROS, sem descrição,
    definição ou exemplo (`OQ-12` aberta).

    A prova está em dois níveis: os valores servidos são exatamente os seis
    nomes canônicos, e o corpo da rota (fora da docstring, que é documento
    de projeto e nunca chega ao navegador) não carrega nenhuma pista de
    glosa inventada."""
    servidos = _classificacoes_servidas_ao_revisor()
    assert sorted(servidos) == sorted(_SEIS_NOMES_CANONICOS)

    corpo_minusculo = _corpo_da_rota_sem_docstring().lower()
    violacoes = [pista for pista in _PISTAS_DE_GLOSA_INVENTADA if pista in corpo_minusculo]
    assert not violacoes, f"pista(s) de glosa inventada encontrada(s) na rota: {violacoes}"


def test_rota_de_decisao_tem_exatamente_seis_classificacoes() -> None:
    """Nenhum sétimo rótulo, nenhuma variação.

    A rota deriva a lista do próprio `CLASSIFICACAO_ERRO` em vez de repetir
    os nomes — por isso um sétimo rótulo só pode nascer no enum, num lugar
    só, onde a nota de `OQ-12` está escrita."""
    assert len(_classificacoes_servidas_ao_revisor()) == 6


# ---------------------------------------------------------------------------
# Critério 3 — o campo livre acompanha a classificação e é gravado no
# RegistroRevisao (junto, não em substituição).
# ---------------------------------------------------------------------------


def test_registro_revisao_grava_classificacao_e_observacao_juntas() -> None:
    """`classificacao_erro` (domínio fechado) e `observacao` (texto livre)
    coexistem no mesmo `RegistroRevisao` — nenhum dos dois substitui o
    outro."""
    agora = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    registro = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t72",
        CASO_ID="caso-teste-t72",
        decisao=DECISAO_REVISAO.REPROVADO,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        classificacao_erro=CLASSIFICACAO_ERRO.DADO,
        observacao="o saldo de D001 não confere com o extrato enviado",
    )

    assert registro.classificacao_erro is CLASSIFICACAO_ERRO.DADO
    assert registro.observacao == "o saldo de D001 não confere com o extrato enviado"


def test_registro_revisao_aceita_classificacao_sem_observacao_e_vice_versa() -> None:
    """Os dois campos são independentes: um pode estar preenchido sem o
    outro — classificar sem comentar, ou comentar sem classificar."""
    agora = datetime(2026, 5, 1, 9, 30, tzinfo=UTC)

    so_classificacao = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t72-a",
        CASO_ID="caso-teste-t72-a",
        decisao=DECISAO_REVISAO.REPROVADO,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        classificacao_erro=CLASSIFICACAO_ERRO.UX,
        observacao=None,
    )
    assert so_classificacao.classificacao_erro is CLASSIFICACAO_ERRO.UX
    assert so_classificacao.observacao is None

    so_observacao = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t72-b",
        CASO_ID="caso-teste-t72-b",
        decisao=DECISAO_REVISAO.REPROVADO,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        classificacao_erro=None,
        observacao="revisor optou por não classificar, só comentar",
    )
    assert so_observacao.classificacao_erro is None
    assert so_observacao.observacao == "revisor optou por não classificar, só comentar"


# ---------------------------------------------------------------------------
# Critério 4 — o código registra em comentário que OQ-12 está aberta e que a
# glosa entra quando ela for respondida.
# ---------------------------------------------------------------------------


def test_docstring_do_enum_cita_oq12_como_aberta() -> None:
    """A docstring de `CLASSIFICACAO_ERRO` (comentário narrativo mais
    próximo da declaração) cita `OQ-12` explicitamente e explica que a
    glosa ainda não existe para transcrever."""
    docstring = CLASSIFICACAO_ERRO.__doc__ or ""
    assert "OQ-12" in docstring
    assert "aberta" in docstring.lower() or "ABERTA" in docstring


def test_docstring_do_enum_promete_glosa_apenas_quando_oq12_for_respondida() -> None:
    """O comentário não inventa a definição agora: registra que ela só
    entra quando a Open Question for respondida."""
    docstring = CLASSIFICACAO_ERRO.__doc__ or ""
    assert "quando" in docstring.lower() and "respondida" in docstring.lower()


def test_modulo_fila_cita_oq12_fora_da_docstring_do_enum_tambem() -> None:
    """Reforço: `OQ-12` é citada em mais de um ponto do módulo (docstring do
    módulo e docstring do `RegistroRevisao`), não só uma vez isolada —
    qualquer leitor que passe pelo arquivo encontra a referência."""
    codigo_fonte = _ARQUIVO_FILA.read_text(encoding="utf-8")
    assert codigo_fonte.count("OQ-12") >= 2
