"""Os três métodos de quitação — Avalanche, Bola de Neve, Híbrido.

Cada um implementa `SelecionarAlvo` (`engine/ciclo_mensal.py`), o único ponto
de variação entre os métodos (§1, §4 do plano técnico). Nenhum destes módulos
reimplementa o ciclo mensal — `engine/ciclo_mensal.py::executar_mes` é o único
lugar que orquestra M-01..M-12.
"""
