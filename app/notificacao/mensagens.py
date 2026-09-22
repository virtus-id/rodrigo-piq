"""Quais e-mails o aluno recebe, e quando — `T-182`.

**Separado de `email.py` de propósito.** Aquele módulo sabe FALAR SMTP e
nada mais; este sabe QUAL mensagem vai em cada momento e nada mais. A
separação é o que permite testar a escolha da mensagem sem servidor, e
trocar de provedor sem tocar em redação.

**A redação NÃO está aqui.** Ela vive em `textos/emails.yaml`. Escrevi este
módulo primeiro com o texto embutido, argumentando que e-mail transacional
não é peça normativa como o termo (`PEND-01`) ou a redação do plano
(`Q-03`) — e a trava estática de `AC-37` reprovou. Ela está certa e o
argumento estava errado: `AC-37` audita literal longo em `app/`, sem
perguntar se o texto é normativo. Uma regra que vale só quando o autor
concorda com ela não é regra. O texto saiu para YAML.

Aqui ficam três coisas, que são código de verdade: em que momento cada
mensagem é usada, como o link é construído, e a recusa a montar mensagem
com chave faltando.

**Texto puro, sem HTML.** Um e-mail transacional em texto chega mais
íntegro: não depende de cliente que renderize CSS, não cai em filtro de
spam por imagem remota, e é legível em leitor de tela sem esforço. A
persona é um servidor público lendo no celular — o que importa é o link
funcionar.

REGRAS: `RF-02`, `RF-31`
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-31")

_VARIAVEL_URL_BASE: Final[str] = "URL_BASE_APP"

CAMINHO_TEXTOS: Final[Path] = Path(__file__).parent / "textos" / "emails.yaml"

#: As três chaves de primeiro nível que `emails.yaml` precisa ter. Explícito
#: para que a ausência de uma delas falhe na carga, nomeando a chave — e não
#: mais tarde, no envio, como `KeyError` sem contexto.
_MENSAGENS_ESPERADAS: Final[tuple[str, ...]] = (
    "primeiro_acesso",
    "recuperacao_de_senha",
    "plano_liberado",
)


class ErroUrlBaseAusente(RuntimeError):
    """`URL_BASE_APP` não está configurada.

    **Não há fallback.** Um link de primeiro acesso apontando para
    `localhost` chega ao aluno como link quebrado — e ele não tem outro
    caminho para entrar. Falhar aqui é ruidoso e cedo; adivinhar o domínio
    seria silencioso e tarde."""


class ErroTextoDeEmailInvalido(RuntimeError):
    """`emails.yaml` está ausente, malformado ou incompleto.

    Mesma postura de `ErroTextoConsentimentoAusente`: falta de texto é
    impedimento explícito, nunca um e-mail enviado pela metade. Um corpo
    truncado é pior que nenhum e-mail — o aluno recebe um link quebrado e
    conclui que o produto não funciona."""


@dataclass(frozen=True, slots=True)
class Mensagem:
    """O que `EnviadorDeEmail.enviar` consome."""

    assunto: str
    corpo: str


@lru_cache(maxsize=1)
def _textos(caminho: Path = CAMINHO_TEXTOS) -> Mapping[str, Mapping[str, str]]:
    """Lê e valida `emails.yaml` uma vez por processo.

    **Validação na carga, não no uso.** As três mensagens são conferidas
    aqui mesmo que o processo só vá enviar uma: um YAML com `plano_liberado`
    faltando deve quebrar quando o servidor sobe, não semanas depois, no
    único momento em que aquela mensagem importa."""
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except OSError as erro:
        raise ErroTextoDeEmailInvalido(f"não foi possível ler {caminho}") from erro
    except yaml.YAMLError as erro:
        raise ErroTextoDeEmailInvalido(f"{caminho}: YAML inválido") from erro

    if not isinstance(bruto, dict):
        raise ErroTextoDeEmailInvalido(f"{caminho}: conteúdo não é um mapeamento YAML")

    textos: dict[str, Mapping[str, str]] = {}
    for nome in _MENSAGENS_ESPERADAS:
        bloco = bruto.get(nome)
        if not isinstance(bloco, dict):
            raise ErroTextoDeEmailInvalido(f"{caminho}: mensagem ausente {nome!r}")
        for campo in ("assunto", "corpo"):
            if not str(bloco.get(campo) or "").strip():
                raise ErroTextoDeEmailInvalido(f"{caminho}: {nome}.{campo} ausente ou vazio")
        textos[nome] = {
            "assunto": str(bloco["assunto"]).strip(),
            # `.strip()` no corpo tira só o `\n` final que o bloco literal
            # (`|`) do YAML sempre acrescenta — não toca na formatação
            # interna, que é o que dá as linhas em branco entre parágrafos.
            "corpo": str(bloco["corpo"]).strip(),
        }
    return textos


def _montar(nome: str, **valores: str) -> Mensagem:
    """Interpola os `valores` no corpo da mensagem `nome`.

    **`str.replace`, nunca `str.format`.** O corpo é dado externo: um `{` que
    alguém escreva no YAML por acidente quebraria `format` com `KeyError`, e
    `{}` vazio consumiria posicional. `replace` trata o texto como texto."""
    texto = _textos()[nome]
    corpo = texto["corpo"]
    for chave, valor in valores.items():
        corpo = corpo.replace("{" + chave + "}", valor)
    return Mensagem(assunto=texto["assunto"], corpo=corpo)


def _url_base() -> str:
    valor = os.environ.get(_VARIAVEL_URL_BASE)
    if not valor:
        raise ErroUrlBaseAusente(f"{_VARIAVEL_URL_BASE} ausente ou vazia.")
    return valor.rstrip("/")


def link_de_senha(token: str) -> str:
    """O link que leva à tela de criar senha.

    **O token vai no HASH (`#`), nunca em query string.** O fragmento não é
    enviado ao servidor em requisição nenhuma: fica no navegador até o
    JavaScript o ler. Numa query string, o token apareceria em log de
    proxy, de CDN e no `Referer` de qualquer recurso externo que a página
    carregasse — e quem lesse esse log entraria na conta do aluno."""
    return f"{_url_base()}/#definir-senha/{token}"


def primeiro_acesso(token: str) -> Mensagem:
    """A compra foi aprovada e a conta existe, sem senha — `T-179`."""
    return _montar("primeiro_acesso", link=link_de_senha(token))


def recuperacao_de_senha(token: str) -> Mensagem:
    """O aluno esqueceu a senha — mesmo mecanismo de token."""
    return _montar("recuperacao_de_senha", link=link_de_senha(token))


def plano_liberado() -> Mensagem:
    """O revisor liberou o plano — `RF-23`, `RF-31`.

    **Sem `CASO_ID` no link.** A URL base basta: quem entra cai no Início,
    que lê a fase do caso e oferece o plano (`RF-58`). Pôr o caso no link
    seria expor o identificador num e-mail sem necessidade — e o Início já
    sabe para onde levar."""
    return _montar("plano_liberado", link=_url_base())
