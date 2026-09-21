"""Sobe o BACKEND para uso manual no navegador — demonstração local.

**A interface é React e roda separada** (T-145). Este script serve a API
JSON e o PDF; quem desenha a tela é o Vite, em `frontend/`, que faz proxy
das chamadas para cá (ver `frontend/vite.config.ts`). Subir só este
processo dá uma API navegável, não uma aplicação.

    DATABASE_URL="postgresql://postgres:piq_local_dev@127.0.0.1:55432/piq" \\
        .venv/Scripts/python.exe scripts/subir_demo.py

Depois abra a URL que o script imprime. Ver `docs/banco-local.md` para subir o
Postgres antes.

**Por que um script, e não só `uvicorn`.** Três coisas impedem `uvicorn
app.http.aplicacao:criar_aplicacao --factory` de dar uma aplicação navegável:

1. **HTTPS é obrigatório.** `criar_aplicacao()` fixa `https_only=True` no
   cookie de sessão. Sobre `http://localhost` o navegador não devolve o
   cookie, e toda rota protegida responde `401`. Este script gera um
   certificado efêmero (OpenSSL do sistema) e serve por TLS — a produção não
   é afrouxada para a demonstração acontecer.

2. **Não existe rota HTTP que crie um caso.** `rotas_conta.py` tem cadastro,
   login e logout; o `Caso` nasce direto no repositório (`OQ-11`: o
   `CASO_ID` é gerado pelo chamador). Sem isso não há o que visitar. Este
   script cria conta e caso, como a suíte de testes faz.

3. **`PEND-01` está em aberto** — não há texto de consentimento, e
   `carregar_texto_vigente()` trata a ausência como bloqueio explícito.

**Sobre o passo do consentimento, e por que ele é pulado aqui.** O caso é
criado já em `COLETA_INICIAL`, o estado que `inicia_coleta` produziria. Isso
**não** é "o consentimento foi resolvido": é uma demonstração da coleta que
começa depois dele. `app/consentimento/textos/README.md` é explícito em que
nem um placeholder deve ser escrito ali, porque um texto que pareça redação
real reintroduz exatamente o risco que `PEND-01` existe para evitar — então
este script não cria arquivo nenhum naquela pasta. Antes do piloto, o texto
do jurídico entra lá e o fluxo passa a incluir a tela de consentimento.

Nada aqui altera código de produção: só cria linhas de dado no banco local e
serve a aplicação real, com os roteadores reais.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.casos.maquina import ESTADO_CASO, Caso  # noqa: E402
from app.http.aplicacao import criar_aplicacao  # noqa: E402
from collection.carga import carregar_registros  # noqa: E402
from persistencia.app_aluno.casos import RepositorioCasosSupabase  # noqa: E402
from persistencia.app_aluno.contas import RepositorioContasSupabase  # noqa: E402

EMAIL_DEMO: Final[str] = "maria.silva@exemplo.gov.br"
SENHA_DEMO: Final[str] = "demonstracao-local-piq"
PORTA: Final[int] = 8443


def _certificado_efemero(destino: Path) -> tuple[Path, Path]:
    """Certificado autoassinado para `localhost`, via OpenSSL do sistema —
    sem acrescentar `cryptography`/`trustme` ao projeto."""
    chave = destino / "chave.pem"
    cert = destino / "cert.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(chave), "-out", str(cert), "-days", "1",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return chave, cert


def _porta_disponivel(porta: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", porta))
        except OSError:
            return False
        return True


def _preparar_conta_e_caso() -> tuple[str, str]:
    """Cria (ou reaproveita) a conta de demonstração e abre um caso novo em
    `COLETA_INICIAL`. Devolve `(conta_id, CASO_ID)`."""
    contas = RepositorioContasSupabase()
    conta = contas.buscar_por_email(EMAIL_DEMO)
    if conta is None:
        conta_id = str(uuid.uuid4())
        contas.criar(conta_id, EMAIL_DEMO, SENHA_DEMO)
    else:
        conta_id = conta.conta_id

    colecao = carregar_registros()
    agora = datetime.now(UTC)
    caso = Caso(
        CASO_ID=str(uuid.uuid4()),
        conta_id=conta_id,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date.today(),
        QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=agora,
        criado_em=agora,
    )
    RepositorioCasosSupabase().criar(caso)
    return conta_id, caso.CASO_ID


def main() -> int:
    import os

    os.environ.setdefault("CHAVE_ASSINATURA_SESSAO", "chave-de-demonstracao-local-piq")
    os.environ.setdefault("PARAMETROS_VERSION_VIGENTE", "1.0.1")

    if not _porta_disponivel(PORTA):
        print(f"porta {PORTA} ocupada — encerre o processo anterior")
        return 1

    _conta_id, caso_id = _preparar_conta_e_caso()
    temporario = Path(tempfile.mkdtemp())
    chave, cert = _certificado_efemero(temporario)

    base = f"https://localhost:{PORTA}"
    print()
    print("=" * 68)
    print("  PIQ — demonstração local (backend)")
    print("=" * 68)
    print("  Este processo serve a API e o PDF. A INTERFACE é React e roda")
    print("  em outro processo — suba-o numa segunda janela de terminal:")
    print()
    print("      cd frontend && npm run dev")
    print()
    print(f"  1. Abra {base}/saude e aceite o certificado autoassinado.")
    print("     Sem esse passo o proxy do Vite não consegue falar com a API.")
    print()
    print(f"  2. Abra  http://localhost:5173/?caso={caso_id}")
    print()
    print(f"  E-mail:   {EMAIL_DEMO}")
    print(f"  Senha:    {SENHA_DEMO}")
    print()
    print("  A sessão é o que autoriza a coleta: entre pelo login antes de")
    print("  responder. Sem consentimento (PEND-01), o caso já nasce em")
    print("  COLETA_INICIAL — a tela de aceite entra quando o texto do")
    print("  jurídico for publicado.")
    print()
    print(f"  API (sem tela):  {base}/caso/{caso_id}/api/plano")
    print(f"  PDF do plano:    {base}/caso/{caso_id}/plano/pdf")
    print()
    print("  Ctrl+C encerra.")
    print("=" * 68)
    print()

    uvicorn.run(
        criar_aplicacao(),
        host="127.0.0.1",
        port=PORTA,
        log_level="info",
        ssl_keyfile=str(chave),
        ssl_certfile=str(cert),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
