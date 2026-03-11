"""Testes unitários – Cálculo de fatura VERDE (split automático contratada/medida)."""

import pytest

from fatura.calculo_verde import calcular_fatura_verde
from fatura.premissas import (
    DESCONTO_FONTE_INCENTIVADA,
    FATOR_COMERCIALIZADORA,
    FATOR_ISENTO_ICMS,
    FATOR_TRIBUTADO,
    TE_COMERCIALIZADORA,
    VERDE_DEMANDA_UNICA,
    VERDE_TUSD_FP,
    VERDE_TUSD_HP,
)

# ── Fixtures ────────────────────────────────────────────────────────────────────

CASO_BASE = dict(
    demanda_contratada_kw=3_280.0,
    demanda_medida_kw=2_900.0,
    consumo_hp_kwh=10_000.0,
    consumo_fp_kwh=50_000.0,
    encargos=500.0,
)


@pytest.fixture
def resultado_base():
    return calcular_fatura_verde(**CASO_BASE)


# ── Testes de estrutura ────────────────────────────────────────────────────────

CHAVES_ESPERADAS = [
    "dem_faturada", "dem_tributada", "dem_isenta", "dem_ultrapassagem",
    "base_dem_trib", "base_dem_isenta", "base_dem_ultra",
    "base_tusd_fp", "base_tusd_hp", "tarifa_hp_efetiva", "desconto_hp", "desconto_fonte_total",
    "valor_dem_trib", "valor_dem_isenta", "valor_dem_ultra", "valor_tusd_fp", "valor_tusd_hp",
    "ben_liquido", "ben_bruto", "impostos_ben", "encargos",
    "total_distribuidora", "total_consumo_kwh", "base_comercializadora", "total_comercializadora",
    "custo_total",
]


def test_chaves_resultado(resultado_base):
    for chave in CHAVES_ESPERADAS:
        assert chave in resultado_base, f"Chave ausente: {chave}"


# ── Split automático ───────────────────────────────────────────────────────────

def test_split_demanda(resultado_base):
    assert resultado_base["dem_faturada"] == pytest.approx(3_280.0, abs=0.01)
    assert resultado_base["dem_tributada"] == pytest.approx(2_900.0, abs=0.01)
    assert resultado_base["dem_isenta"] == pytest.approx(380.0, abs=0.01)


def test_medida_maior_que_contratada():
    r = calcular_fatura_verde(
        demanda_contratada_kw=200, demanda_medida_kw=300,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_faturada"] == pytest.approx(300.0)
    assert r["dem_tributada"] == pytest.approx(200.0)
    assert r["dem_isenta"] == pytest.approx(0.0)
    assert r["dem_ultrapassagem"] == pytest.approx(100.0)


# ── Testes de base (sem imposto) ───────────────────────────────────────────────

def test_base_dem_trib(resultado_base):
    esperado = 2_900.0 * VERDE_DEMANDA_UNICA * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_trib"] == pytest.approx(esperado, abs=0.01)


def test_base_dem_isenta(resultado_base):
    esperado = 380.0 * VERDE_DEMANDA_UNICA * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_base_tusd_fp(resultado_base):
    esperado = (CASO_BASE["consumo_fp_kwh"] / 1000) * VERDE_TUSD_FP
    assert resultado_base["base_tusd_fp"] == pytest.approx(esperado, abs=0.01)


def test_tarifa_hp_efetiva(resultado_base):
    esperado = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    assert resultado_base["tarifa_hp_efetiva"] == pytest.approx(
        esperado, abs=0.01)


def test_base_tusd_hp(resultado_base):
    consumo_hp_mwh = CASO_BASE["consumo_hp_kwh"] / 1000
    tarifa_efe = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    esperado = consumo_hp_mwh * tarifa_efe
    assert resultado_base["base_tusd_hp"] == pytest.approx(esperado, abs=0.01)


def test_desconto_hp(resultado_base):
    consumo_hp_mwh = CASO_BASE["consumo_hp_kwh"] / 1000
    esperado = consumo_hp_mwh * (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    assert resultado_base["desconto_hp"] == pytest.approx(esperado, abs=0.01)


# ── Testes de gross-up ─────────────────────────────────────────────────────────

def test_gross_up_dem_trib(resultado_base):
    """Demanda usada → tributada."""
    esperado = resultado_base["base_dem_trib"] / FATOR_TRIBUTADO
    assert resultado_base["valor_dem_trib"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_dem_isenta(resultado_base):
    """Demanda não usada → isenta ICMS."""
    esperado = resultado_base["base_dem_isenta"] / FATOR_ISENTO_ICMS
    assert resultado_base["valor_dem_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_tusd_sempre_tributada(resultado_base):
    esperado_fp = resultado_base["base_tusd_fp"] / FATOR_TRIBUTADO
    esperado_hp = resultado_base["base_tusd_hp"] / FATOR_TRIBUTADO
    assert resultado_base["valor_tusd_fp"] == pytest.approx(
        esperado_fp, abs=0.01)
    assert resultado_base["valor_tusd_hp"] == pytest.approx(
        esperado_hp, abs=0.01)


# ── Testes do Benefício ────────────────────────────────────────────────────────

def test_ben_liquido(resultado_base):
    esperado = resultado_base["desconto_fonte_total"] + \
        resultado_base["desconto_hp"]
    assert resultado_base["ben_liquido"] == pytest.approx(esperado, abs=0.01)


def test_impostos_ben_positivo(resultado_base):
    assert resultado_base["impostos_ben"] > 0


def test_ben_bruto_maior_que_liquido(resultado_base):
    assert resultado_base["ben_bruto"] > resultado_base["ben_liquido"]


# ── Testes do Total Distribuidora ──────────────────────────────────────────────

def test_total_distribuidora_formula(resultado_base):
    esperado = (
        resultado_base["valor_dem_trib"]
        + resultado_base["valor_dem_isenta"]
        + resultado_base["valor_dem_ultra"]
        + resultado_base["valor_tusd_fp"]
        + resultado_base["valor_tusd_hp"]
        + resultado_base["encargos"]
        + resultado_base["ben_bruto"]
        - resultado_base["ben_liquido"]
    )
    assert resultado_base["total_distribuidora"] == pytest.approx(
        esperado, abs=0.05)


# ── Testes da Comercializadora ─────────────────────────────────────────────────

def test_total_consumo_kwh(resultado_base):
    esperado = CASO_BASE["consumo_hp_kwh"] + CASO_BASE["consumo_fp_kwh"]
    assert resultado_base["total_consumo_kwh"] == pytest.approx(
        esperado, abs=0.01)


def test_base_comercializadora(resultado_base):
    esperado = resultado_base["total_consumo_kwh"] * TE_COMERCIALIZADORA
    assert resultado_base["base_comercializadora"] == pytest.approx(
        esperado, abs=0.01)


def test_total_comercializadora(resultado_base):
    esperado = resultado_base["base_comercializadora"] / FATOR_COMERCIALIZADORA
    assert resultado_base["total_comercializadora"] == pytest.approx(
        esperado, abs=0.01)


# ── Custo Total ────────────────────────────────────────────────────────────────

def test_custo_total(resultado_base):
    esperado = resultado_base["total_distribuidora"] + \
        resultado_base["total_comercializadora"]
    assert resultado_base["custo_total"] == pytest.approx(esperado, abs=0.05)


# ── Testes de borda ────────────────────────────────────────────────────────────

def test_consumo_zero():
    r = calcular_fatura_verde(
        demanda_contratada_kw=200, demanda_medida_kw=100,
        consumo_hp_kwh=0, consumo_fp_kwh=0,
    )
    assert r["base_tusd_hp"] == 0.0
    assert r["base_tusd_fp"] == 0.0
    assert r["desconto_hp"] == 0.0
    assert r["desconto_fonte_total"] > 0  # demanda existe → desconto existe
    assert r["total_comercializadora"] == 0.0


def test_demanda_zero():
    r = calcular_fatura_verde(
        demanda_contratada_kw=0, demanda_medida_kw=0,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["base_dem_trib"] == 0.0
    assert r["base_dem_isenta"] == 0.0
    assert r["valor_dem_trib"] == 0.0
    assert r["valor_dem_isenta"] == 0.0


def test_tudo_zero():
    r = calcular_fatura_verde(0, 0, 0, 0, 0)
    assert r["custo_total"] == 0.0


def test_encargos_somados(resultado_base):
    r_sem = calcular_fatura_verde(**{**CASO_BASE, "encargos": 0.0})
    diff = resultado_base["total_distribuidora"] - r_sem["total_distribuidora"]
    assert diff == pytest.approx(CASO_BASE["encargos"], abs=0.01)


# ── Demanda toda isenta / toda tributada ───────────────────────────────────────

def test_demanda_toda_isenta():
    """Medida = 0 → toda demanda isenta ICMS."""
    r = calcular_fatura_verde(
        demanda_contratada_kw=1000, demanda_medida_kw=0,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_tributada"] == 0.0
    assert r["dem_isenta"] == pytest.approx(1000.0)
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    esperado = (1000 * VERDE_DEMANDA_UNICA * fator_dem) / FATOR_ISENTO_ICMS
    assert r["valor_dem_isenta"] == pytest.approx(esperado, abs=0.01)
    assert r["valor_dem_trib"] == 0.0


def test_demanda_toda_tributada():
    """Medida >= contratada → tributável = contratada, excesso é ultrapassagem."""
    r = calcular_fatura_verde(
        demanda_contratada_kw=1000, demanda_medida_kw=1500,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_isenta"] == pytest.approx(0.0)
    assert r["dem_tributada"] == pytest.approx(1000.0)
    assert r["dem_ultrapassagem"] == pytest.approx(500.0)
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    esperado_trib = (1000 * VERDE_DEMANDA_UNICA * fator_dem) / FATOR_TRIBUTADO
    esperado_ultra = (500 * VERDE_DEMANDA_UNICA * 2) / FATOR_TRIBUTADO
    assert r["valor_dem_trib"] == pytest.approx(esperado_trib, abs=0.01)
    assert r["valor_dem_ultra"] == pytest.approx(esperado_ultra, abs=0.01)
    assert r["valor_dem_isenta"] == 0.0


# ── Valores absolutos ─────────────────────────────────────────────────────────

def test_valores_absolutos():
    r = calcular_fatura_verde(**CASO_BASE)

    # tarifa_hp_efetiva = 140.21 + (2296.63 − 140.21) × 0.5 = 1218.42
    assert r["tarifa_hp_efetiva"] == pytest.approx(1_218.42, abs=0.01)

    # desconto_hp = 10 MWh × (2296.63 − 140.21) × 0.5 = 10782.10
    assert r["desconto_hp"] == pytest.approx(10_782.10, abs=0.01)

    # desconto_fonte_total = 3280 × 32.50 × 0.5 = 53300.00
    assert r["desconto_fonte_total"] == pytest.approx(53_300.00, abs=0.01)

    # base_comercializadora = 60000 × 0.306 = 18360.00
    assert r["base_comercializadora"] == pytest.approx(18_360.00, abs=0.01)

    # total_comercializadora = 18360.00 / FATOR_COMERCIALIZADORA
    assert r["total_comercializadora"] == pytest.approx(
        18_360.00 / FATOR_COMERCIALIZADORA, abs=0.01)

    assert r["custo_total"] > 0


def test_verde_tusd_hp_mais_caro_que_fp():
    r = calcular_fatura_verde(**CASO_BASE)
    assert r["tarifa_hp_efetiva"] > VERDE_TUSD_FP
