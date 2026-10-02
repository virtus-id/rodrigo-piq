"""Telas da equipe identificam o caso pelo e-mail do aluno — `RF-111` (e),
`T-327`.

Relato do produto (2026-10-02): a conferência mostrava "Conferir o plano de
CASO_4910a3ea…". O servidor agora manda `email_do_aluno` (da conta dona do
caso) na fila e na conferência; o painel é coberto em
`tests/app_aluno/e2e/test_rotas_operador.py`. O caso e as rotas são os de
`T-326` (`test_t326_linguagem_humana.py`).

REGRAS: `RF-111`
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.http.rotas_api_plano import obter_emails_dos_alunos
from tests.app_aluno.test_t326_linguagem_humana import _CASO_ID, _cliente

_EMAIL = "fulano@exemplo.invalido"


class _Emails:
    """Conta as consultas — a fila pede todos os e-mails de uma vez."""

    def __init__(self, emails: dict[str, str]) -> None:
        self._emails = emails
        self.consultas: list[tuple[str, ...]] = []

    def emails_dos_casos(self, caso_ids: tuple[str, ...]) -> dict[str, str]:
        self.consultas.append(caso_ids)
        return {c: self._emails[c] for c in caso_ids if c in self._emails}


def _com_emails(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO, emails: dict[str, str]
) -> tuple[TestClient, _Emails]:
    cliente, _ = _cliente(monkeypatch, estado)
    dublê = _Emails(emails)
    aplicacao: Any = cliente.app
    aplicacao.dependency_overrides[obter_emails_dos_alunos] = lambda: dublê
    return cliente, dublê


def test_fila_traz_o_email_do_aluno_numa_consulta_so(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, dublê = _com_emails(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO, {_CASO_ID: _EMAIL})

    itens = cliente.get("/api/revisao/fila").json()["itens"]

    assert [(i["CASO_ID"], i["email_do_aluno"]) for i in itens] == [(_CASO_ID, _EMAIL)]
    assert dublê.consultas == [(_CASO_ID,)]


def test_conferencia_traz_o_email_do_aluno(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _com_emails(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO, {_CASO_ID: _EMAIL})

    corpo = cliente.get(f"/api/revisao/caso/{_CASO_ID}").json()

    assert corpo["fila"]["email_do_aluno"] == _EMAIL
    assert corpo["CASO_ID"] == _CASO_ID


def test_conta_sem_email_cai_no_caso_id(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _com_emails(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO, {})

    item = cliente.get("/api/revisao/fila").json()["itens"][0]
    fila = cliente.get(f"/api/revisao/caso/{_CASO_ID}").json()["fila"]

    assert item["email_do_aluno"] is None
    assert fila["email_do_aluno"] is None


def test_rota_do_aluno_nao_expoe_email(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, dublê = _com_emails(monkeypatch, ESTADO_CASO.PLANO_LIBERADO, {_CASO_ID: _EMAIL})

    resposta = cliente.get(f"/caso/{_CASO_ID}/api/plano")

    assert resposta.status_code == 200
    assert _EMAIL not in resposta.text
    assert "email_do_aluno" not in resposta.text
    assert dublê.consultas == []
