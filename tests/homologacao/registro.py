"""Emissão do `RegistroHomologacao` no relatório JUnit do pytest (`RF-96`,
T-268). A montagem vive em `app/revisao/homologacao.py` (`T-304`)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict

from app.revisao.homologacao import RegistroHomologacao


def emitir(record_property: Callable[[str, object], None], registro: RegistroHomologacao) -> None:
    """Vai para o relatório JUnit do pytest; nenhum arquivo escrito."""
    record_property("registro_homologacao", json.dumps(asdict(registro), default=str))
