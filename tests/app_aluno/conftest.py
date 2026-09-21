"""Skip automático de `requer_banco` sem `DATABASE_URL` (T-05, RF-34).

O motor não tem hook: cada módulo de `tests/integracao/` declara seu próprio
`@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=...)` (T-76). Esta feature
introduz o marcador `requer_banco` como marcador de coleta (`pyproject.toml`),
e o hook abaixo aplica o mesmo skip a QUALQUER teste marcado com ele, em
qualquer subpasta de `tests/app_aluno/` — sem exigir que cada módulo repita o
`skipif`. `pytest -m "not requer_banco and not e2e"` nunca precisa de
`DATABASE_URL` porque os testes marcados já nem entram em coleção; rodar sem
esse filtro e sem `DATABASE_URL` também não falha: os testes aparecem como
`skipped`, com o motivo explícito abaixo, nunca como `failed`/`error`.
"""

import importlib.util
import os

import pytest

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"

# T-129: mesma disciplina do marcador acima, agora para o navegador real.
# Playwright vive num extra PRÓPRIO (`browser`), fora de `dev` e de `app` —
# numa máquina que nunca o instalou, os testes marcados `navegador` são
# pulados com motivo explícito, nunca falham. Assim `pytest -q` continua
# verde onde o extra não existe, exatamente como acontece sem DATABASE_URL.
_PLAYWRIGHT_AUSENTE = importlib.util.find_spec("playwright") is None
_MOTIVO_SKIP_NAVEGADOR = (
    "Playwright ausente — instale o extra `browser` (marcador navegador)"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    pular_banco = pytest.mark.skip(reason=_MOTIVO_SKIP)
    pular_navegador = pytest.mark.skip(reason=_MOTIVO_SKIP_NAVEGADOR)
    for item in items:
        if _DATABASE_URL_AUSENTE and "requer_banco" in item.keywords:
            item.add_marker(pular_banco)
        if _PLAYWRIGHT_AUSENTE and "navegador" in item.keywords:
            item.add_marker(pular_navegador)
