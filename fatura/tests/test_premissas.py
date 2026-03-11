"""Testes unitários – Premissas tarifárias."""

import pytest

from fatura.premissas import (
    AZUL_DEMANDA_FP,
    AZUL_DEMANDA_HP,
    AZUL_TUSD_FP,
    AZUL_TUSD_HP,
    COFINS,
    DESCONTO_FONTE_INCENTIVADA,
    FATOR_COMERCIALIZADORA,
    FATOR_ISENTO_ICMS,
    FATOR_TRIBUTADO,
    ICMS,
    PIS,
    PIS_COFINS,
    TE_COMERCIALIZADORA,
    VERDE_DEMANDA_UNICA,
    VERDE_TUSD_FP,
    VERDE_TUSD_HP,
)


# ── Impostos ────────────────────────────────────────────────────────────────────

def test_pis_cofins_soma():
    assert PIS_COFINS == pytest.approx(PIS + COFINS, abs=1e-10)


def test_fator_tributado():
    esperado = (1 - ICMS) * (1 - PIS_COFINS)
    assert FATOR_TRIBUTADO == pytest.approx(esperado, abs=1e-10)


def test_fator_isento_icms():
    esperado = 1 - PIS_COFINS
    assert FATOR_ISENTO_ICMS == pytest.approx(esperado, abs=1e-10)


def test_fator_tributado_menor_que_isento():
    """Fator tributado (com ICMS) deve ser menor que o isento."""
    assert FATOR_TRIBUTADO < FATOR_ISENTO_ICMS


def test_fatores_entre_zero_e_um():
    assert 0 < FATOR_TRIBUTADO < 1
    assert 0 < FATOR_ISENTO_ICMS < 1
    assert 0 < FATOR_COMERCIALIZADORA < 1


def test_fator_comercializadora():
    esperado = 1 - ICMS
    assert FATOR_COMERCIALIZADORA == pytest.approx(esperado, abs=1e-10)


# ── Tarifas positivas ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor, nome", [
    (AZUL_DEMANDA_HP, "AZUL_DEMANDA_HP"),
    (AZUL_DEMANDA_FP, "AZUL_DEMANDA_FP"),
    (AZUL_TUSD_HP, "AZUL_TUSD_HP"),
    (AZUL_TUSD_FP, "AZUL_TUSD_FP"),
    (VERDE_DEMANDA_UNICA, "VERDE_DEMANDA_UNICA"),
    (VERDE_TUSD_HP, "VERDE_TUSD_HP"),
    (VERDE_TUSD_FP, "VERDE_TUSD_FP"),
    (TE_COMERCIALIZADORA, "TE_COMERCIALIZADORA"),
])
def test_tarifas_positivas(valor, nome):
    assert valor > 0, f"{nome} deve ser positivo"


# ── Valores hardcoded ──────────────────────────────────────────────────────────

def test_valores_hardcoded():
    """Garante que as premissas hardcoded não foram alteradas acidentalmente."""
    assert PIS == pytest.approx(0.007216)
    assert COFINS == pytest.approx(0.033320)
    assert ICMS == pytest.approx(0.2250)

    assert AZUL_DEMANDA_HP == pytest.approx(88.82)
    assert AZUL_DEMANDA_FP == pytest.approx(32.50)
    assert AZUL_TUSD_HP == pytest.approx(140.21)
    assert AZUL_TUSD_FP == pytest.approx(140.21)

    assert VERDE_DEMANDA_UNICA == pytest.approx(32.50)
    assert VERDE_TUSD_HP == pytest.approx(2296.63)
    assert VERDE_TUSD_FP == pytest.approx(140.21)

    assert TE_COMERCIALIZADORA == pytest.approx(0.306)

    assert DESCONTO_FONTE_INCENTIVADA == pytest.approx(0.50)
