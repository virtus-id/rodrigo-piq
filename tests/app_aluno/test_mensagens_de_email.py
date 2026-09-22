"""A redação dos e-mails e a montagem do link — `T-182`.

**O que estes testes protegem.** Três e-mails são o único caminho entre o
sistema e um aluno que não está com o navegador aberto: o primeiro acesso
(`T-179`), a recuperação de senha e o aviso de plano liberado (`RF-31`).
Um link malformado num deles não degrada a experiência — tranca o aluno
para fora, sem outro caminho de entrada.

Os testes olham para o CONTRATO (o link certo, o token no lugar certo, a
recusa a montar texto quebrado), nunca para a redação palavra por palavra:
a redação vive em `textos/emails.yaml` justamente para poder mudar sem
tocar em código, e um teste que a repetisse literalmente anularia isso.

REGRAS: `RF-02`, `RF-31`
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.notificacao import mensagens
from app.notificacao.mensagens import (
    ErroTextoDeEmailInvalido,
    ErroUrlBaseAusente,
    link_de_senha,
    plano_liberado,
    primeiro_acesso,
    recuperacao_de_senha,
)

_URL_TESTE = "https://piq.exemplo.br"
_TOKEN = "token-de-teste-abc123"


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    """`_textos` é `lru_cache`d — sem isto, o primeiro teste que carregasse
    o YAML fixaria o resultado para todos os outros, e os testes de YAML
    inválido passariam por acidente, lendo o cache do arquivo bom."""
    mensagens._textos.cache_clear()
    yield
    mensagens._textos.cache_clear()


@pytest.fixture
def url_base(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("URL_BASE_APP", _URL_TESTE)
    return _URL_TESTE


# ---------------------------------------------------------------------------
# O link — a parte que, errada, tranca o aluno para fora.
# ---------------------------------------------------------------------------


def test_token_vai_no_fragmento_nunca_em_query_string(url_base: str) -> None:
    """**O ponto de segurança do módulo.** O fragmento (`#`) não é enviado
    ao servidor em requisição nenhuma. Numa query string, o token apareceria
    em log de proxy, de CDN e no `Referer` de qualquer recurso externo que a
    página carregasse — e quem lesse esse log entraria na conta do aluno."""
    link = link_de_senha(_TOKEN)

    assert link == f"{_URL_TESTE}/#definir-senha/{_TOKEN}"
    caminho, _, fragmento = link.partition("#")
    assert "?" not in caminho
    assert _TOKEN not in caminho
    assert _TOKEN in fragmento


def test_barra_final_na_url_base_nao_duplica(monkeypatch: pytest.MonkeyPatch) -> None:
    """`URL_BASE_APP` com barra no fim é erro de digitação provável em
    configuração de produção. `//#definir-senha` quebraria o roteamento por
    hash do frontend."""
    monkeypatch.setenv("URL_BASE_APP", f"{_URL_TESTE}/")

    assert link_de_senha(_TOKEN) == f"{_URL_TESTE}/#definir-senha/{_TOKEN}"


def test_url_base_vazia_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Sem fallback, por decisão.** Um link apontando para `localhost`
    chega ao aluno como link quebrado e ele não tem outro caminho de
    entrada. Falhar é ruidoso e cedo; adivinhar o domínio seria silencioso
    e tarde."""
    monkeypatch.setenv("URL_BASE_APP", "")

    with pytest.raises(ErroUrlBaseAusente):
        link_de_senha(_TOKEN)


def test_url_base_nao_definida_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("URL_BASE_APP", raising=False)

    with pytest.raises(ErroUrlBaseAusente):
        plano_liberado()


# ---------------------------------------------------------------------------
# As três mensagens.
# ---------------------------------------------------------------------------


def test_primeiro_acesso_carrega_o_link_de_senha(url_base: str) -> None:
    mensagem = primeiro_acesso(_TOKEN)

    assert mensagem.assunto.strip()
    assert link_de_senha(_TOKEN) in mensagem.corpo


def test_recuperacao_carrega_o_link_de_senha(url_base: str) -> None:
    mensagem = recuperacao_de_senha(_TOKEN)

    assert mensagem.assunto.strip()
    assert link_de_senha(_TOKEN) in mensagem.corpo


def test_plano_liberado_nao_expoe_caso_id_no_link(url_base: str) -> None:
    """A URL base basta: quem entra cai no Início, que lê a fase do caso e
    oferece o plano (`RF-58`). Pôr o `CASO_ID` no link seria expor o
    identificador num e-mail sem necessidade."""
    mensagem = plano_liberado()

    assert _URL_TESTE in mensagem.corpo
    assert "definir-senha" not in mensagem.corpo
    assert "CASO_" not in mensagem.corpo


def test_recuperacao_orienta_quem_nao_pediu(url_base: str) -> None:
    """Um e-mail de recuperação que não diz o que fazer se não foi você
    quem pediu deixa quem o recebe sem saber se a conta foi invadida. É
    requisito da mensagem, não escolha de redação — por isso é testado."""
    corpo = recuperacao_de_senha(_TOKEN).corpo.lower()

    assert "não foi você" in corpo


def test_nenhuma_mensagem_deixa_placeholder_por_substituir(url_base: str) -> None:
    """**A falha mais cara e mais silenciosa.** Um `{link}` literal chegando
    ao aluno é um e-mail inútil que o sistema conta como entregue — e
    ninguém descobre, porque o envio retorna sucesso."""
    for mensagem in (
        primeiro_acesso(_TOKEN),
        recuperacao_de_senha(_TOKEN),
        plano_liberado(),
    ):
        assert "{" not in mensagem.corpo, mensagem.assunto
        assert "}" not in mensagem.corpo, mensagem.assunto


def test_corpo_e_texto_puro_sem_html(url_base: str) -> None:
    """Texto puro chega mais íntegro: não depende de cliente que renderize
    CSS e não cai em filtro por imagem remota. A persona é um servidor
    público lendo no celular."""
    for mensagem in (primeiro_acesso(_TOKEN), recuperacao_de_senha(_TOKEN), plano_liberado()):
        assert "<" not in mensagem.corpo
        assert "&nbsp;" not in mensagem.corpo


def test_corpo_nao_termina_em_quebra_de_linha(url_base: str) -> None:
    """O bloco literal (`|`) do YAML sempre acrescenta um `\\n` final. O
    `.strip()` na carga o remove — sem isso, todo e-mail sairia com uma
    linha em branco no fim."""
    corpo = plano_liberado().corpo

    assert corpo == corpo.strip()


def test_paragrafos_do_yaml_sobrevivem_a_carga(url_base: str) -> None:
    """`.strip()` tira só as bordas. Se tocasse no miolo, os parágrafos
    virariam um bloco único ilegível no celular."""
    assert "\n\n" in primeiro_acesso(_TOKEN).corpo


# ---------------------------------------------------------------------------
# A carga do YAML — falha explícita, nunca e-mail pela metade.
# ---------------------------------------------------------------------------


def _escrever(tmp_path: Path, conteudo: str) -> Path:
    alvo = tmp_path / "emails.yaml"
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


def test_arquivo_ausente_levanta(tmp_path: Path) -> None:
    with pytest.raises(ErroTextoDeEmailInvalido):
        mensagens._textos(tmp_path / "nao-existe.yaml")


def test_yaml_malformado_levanta(tmp_path: Path) -> None:
    with pytest.raises(ErroTextoDeEmailInvalido):
        mensagens._textos(_escrever(tmp_path, "primeiro_acesso: [nao, fechado\n"))


def test_conteudo_que_nao_e_mapeamento_levanta(tmp_path: Path) -> None:
    with pytest.raises(ErroTextoDeEmailInvalido):
        mensagens._textos(_escrever(tmp_path, "- uma\n- lista\n"))


def test_mensagem_faltando_levanta_nomeando_a_chave(tmp_path: Path) -> None:
    """**Validação na carga, não no uso.** As três são conferidas mesmo que
    o processo só vá enviar uma: um YAML sem `plano_liberado` deve quebrar
    quando o servidor sobe, não semanas depois, no único momento em que
    aquela mensagem importa."""
    conteudo = (
        "primeiro_acesso:\n  assunto: a\n  corpo: b\n"
        "recuperacao_de_senha:\n  assunto: a\n  corpo: b\n"
    )

    with pytest.raises(ErroTextoDeEmailInvalido, match="plano_liberado"):
        mensagens._textos(_escrever(tmp_path, conteudo))


@pytest.mark.parametrize("campo", ["assunto", "corpo"])
def test_campo_vazio_levanta_nomeando_o_campo(tmp_path: Path, campo: str) -> None:
    """Assunto vazio vira e-mail sem assunto (filtro de spam); corpo vazio
    vira e-mail sem o link. Vazio é ausente, não é valor."""
    blocos = {"assunto": "a", "corpo": "b"}
    blocos[campo] = "   "
    conteudo = (
        "primeiro_acesso:\n"
        f"  assunto: \"{blocos['assunto']}\"\n"
        f"  corpo: \"{blocos['corpo']}\"\n"
        "recuperacao_de_senha:\n  assunto: a\n  corpo: b\n"
        "plano_liberado:\n  assunto: a\n  corpo: b\n"
    )

    with pytest.raises(ErroTextoDeEmailInvalido, match=f"primeiro_acesso.{campo}"):
        mensagens._textos(_escrever(tmp_path, conteudo))


def test_chaves_do_arquivo_real_batem_com_o_que_o_codigo_espera() -> None:
    """Amarra o YAML de produção ao código: renomear uma mensagem lá sem
    mudar `_MENSAGENS_ESPERADAS` aqui falha neste teste, não no envio."""
    assert set(mensagens._textos()) == set(mensagens._MENSAGENS_ESPERADAS)
