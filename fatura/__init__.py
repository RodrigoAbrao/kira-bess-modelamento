"""
Pacote ``fatura`` — Cálculo heurístico de fatura de energia.

Exporta as funções principais:
  • calcular_fatura_azul  → modalidade AZUL
  • calcular_fatura_verde → modalidade VERDE
"""

from .calculo_azul import calcular_fatura_azul
from .calculo_verde import calcular_fatura_verde

__all__ = ["calcular_fatura_azul", "calcular_fatura_verde"]
