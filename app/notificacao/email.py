"""Envio de e-mail por SMTP — `T-180`.

**Por que existe.** Duas telas prometem ao aluno, hoje, o que o sistema não
cumpria: *"A espera é com a equipe. Avisamos por e-mail."*
(`TrilhaDaJornada.tsx`) e *"Avisaremos por e-mail assim que o plano estiver
liberado."* (`TelaAguardando.tsx`). Não havia nenhum envio de e-mail no
projeto — a promessa era falsa, e o aluno que fechasse o navegador depois da
coleta nunca ficava sabendo que o plano saiu. Num acompanhamento de meses
(`OQ-06`), esse é o ponto de abandono mais provável do piloto.

E-mail é também a peça de que dependem o primeiro acesso (`T-179`) e a
recuperação de senha: as duas precisam entregar um token ao dono do
endereço, e só o e-mail prova essa posse.

**`smtplib`, da stdlib — nenhuma dependência nova.** O provedor é AWS SES
por SMTP (decisão do especialista, 2026-09-21), mas nada aqui é específico
de SES: qualquer servidor SMTP com STARTTLS serve, e trocar de provedor é
trocar variável de ambiente, nunca código.

**Configuração só por ambiente, nunca literal.** Mesma disciplina de
`CHAVE_ASSINATURA_SESSAO` (`app/http/aplicacao.py`) e `DATABASE_URL`
(`persistencia/supabase/conexao.py`): credencial em código vaza para o
repositório e de lá para todo lugar. Sem as variáveis, `enviar` levanta
`ErroConfiguracaoEmail` — nunca um envio silenciosamente descartado, que
seria pior: a aplicação acharia ter avisado o aluno.

**O que este módulo NÃO faz.** Não decide redação (quem chama passa assunto
e corpo), não monta HTML, não tem fila nem repetição automática. Fila e
repetição são infraestrutura que `OQ-06` (1 a 3 alunos no piloto) não
justifica; quando justificarem, o ponto de injeção é este módulo, não os
chamadores.

REGRAS: `RF-31`
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Final, Protocol

REGRAS: Final[tuple[str, ...]] = ("RF-31",)

_VAR_SERVIDOR: Final[str] = "SMTP_SERVIDOR"
_VAR_PORTA: Final[str] = "SMTP_PORTA"
_VAR_USUARIO: Final[str] = "SMTP_USUARIO"
_VAR_SENHA: Final[str] = "SMTP_SENHA"
_VAR_REMETENTE: Final[str] = "SMTP_REMETENTE"

#: Porta 587 (submissão com STARTTLS) é a do SES e o padrão de submissão
#: autenticada. Explícita porque o default de `smtplib` é 25, que o SES
#: recusa e que provedores bloqueiam.
_PORTA_PADRAO: Final[int] = 587


class ErroConfiguracaoEmail(RuntimeError):
    """Falta variável de ambiente de SMTP. Nunca há envio silenciosamente
    descartado: a aplicação não pode achar que avisou o aluno quando não
    avisou."""


class ErroEnvioEmail(RuntimeError):
    """O servidor SMTP recusou ou a conexão falhou. Propaga para o chamador
    decidir — nunca é engolido aqui."""


class EnviadorDeEmail(Protocol):
    """A porta. Existe para que os chamadores dependam de um contrato, não
    de `smtplib` — e para que os testes substituam o envio sem servidor
    nenhum no ar, mesmo padrão de todo repositório desta feature."""

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None: ...


def _variavel_obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise ErroConfiguracaoEmail(f"{nome} ausente ou vazia.")
    return valor


class EnviadorSMTP:
    """Envio real, por SMTP com STARTTLS.

    **STARTTLS obrigatório, nunca opcional.** `starttls()` é chamado antes
    do login: sem ele, a credencial do SES trafegaria em texto claro. Se o
    servidor não suportar, `smtplib` levanta — e é o comportamento certo,
    porque a alternativa seria autenticar em claro.
    """

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        servidor = _variavel_obrigatoria(_VAR_SERVIDOR)
        usuario = _variavel_obrigatoria(_VAR_USUARIO)
        senha = _variavel_obrigatoria(_VAR_SENHA)
        remetente = _variavel_obrigatoria(_VAR_REMETENTE)
        porta = int(os.environ.get(_VAR_PORTA) or _PORTA_PADRAO)

        mensagem = EmailMessage()
        mensagem["From"] = remetente
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content(corpo)

        try:
            with smtplib.SMTP(servidor, porta, timeout=30) as conexao:
                conexao.starttls(context=ssl.create_default_context())
                conexao.login(usuario, senha)
                conexao.send_message(mensagem)
        except (smtplib.SMTPException, OSError) as erro:
            # A mensagem do erro NÃO carrega o destinatário: e-mail é dado
            # pessoal sob LGPD, e esta exceção vai para o log do processo.
            raise ErroEnvioEmail(f"falha no envio SMTP: {type(erro).__name__}") from erro


class EnviadorEmMemoria:
    """Dublê para teste e para ambiente sem SMTP configurado. Guarda o que
    seria enviado, em vez de mandar."""

    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, str]] = []

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        self.enviados.append((destinatario, assunto, corpo))


def obter_enviador() -> EnviadorDeEmail:
    """Ponto único de injeção — sobrescrito nos testes por
    `app.dependency_overrides`, mesmo padrão de todo repositório desta
    feature."""
    return EnviadorSMTP()
