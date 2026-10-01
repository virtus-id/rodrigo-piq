"""O "hoje" do app — data civil no fuso do aluno — `T-302`.

`date.today()` lê o fuso do servidor (UTC em produção): às 22h de 30/09 em
Brasília ele já devolve 01/10, e `DATA_REFERENCIA` saía um dia adiantada.
Toda data civil do caso (cadastro, provisionamento) vem daqui. Timestamps de
auditoria (`criado_em`, `ultima_interacao_em`...) continuam
`datetime.now(UTC)` — instante, não data civil.

A imagem de produção precisa de `tzdata` do sistema (`Dockerfile`): sem ele
`ZoneInfo` falha na importação — alto, na subida, nunca uma data errada.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final
from zoneinfo import ZoneInfo

FUSO_DO_APP: Final[ZoneInfo] = ZoneInfo("America/Sao_Paulo")


def hoje(agora: datetime | None = None) -> date:
    """A data civil de `agora` (padrão: o instante atual) em `FUSO_DO_APP`."""
    return (agora if agora is not None else datetime.now(UTC)).astimezone(FUSO_DO_APP).date()
