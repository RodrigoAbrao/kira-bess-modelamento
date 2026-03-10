"""Testes unitários – Cálculo de fatura AZUL (split automático contratada/medida)."""

import pytest

from fatura.calculo_azul import calcular_fatura_azul
from fatura.premissas import (
    AZUL_DEMANDA_FP,
    AZUL_DEMANDA_HP,
    AZUL_TUSD_FP,
    AZUL_TUSD_HP,
    DESCONTO_FONTE_INCENTIVADA,
    FATOR_COMERCIALIZADORA,
    FATOR_ISENTO_ICMS,
    FATOR_TRIBUTADO,
    TE_COMERCIALIZADORA,
)

# ── Fixtures ────────────────────────────────────────────────────────────────────

# Caso com demanda parcialmente usada (medida < contratada)
CASO_BASE = dict(
    demanda_hp_contratada_kw=2_980.0,
    demanda_fp_contratada_kw=3_280.0,
    demanda_hp_medida_kw=2_527.65,
    demanda_fp_medida_kw=2_902.31,
    consumo_hp_kwh=115_251.52,
    consumo_fp_kwh=1_206_468.05,
    encargos=500.0,
)


@pytest.fixture
def resultado_base():
    return calcular_fatura_azul(**CASO_BASE)


# ── Testes de estrutura ────────────────────────────────────────────────────────

CHAVES_ESPERADAS = [
    "dem_hp_faturada", "dem_fp_faturada",
    "dem_hp_tributada", "dem_hp_isenta", "dem_fp_tributada", "dem_fp_isenta",
    "base_dem_hp_trib", "base_dem_hp_isenta",
    "base_dem_fp_trib", "base_dem_fp_isenta",
    "base_tusd_hp", "base_tusd_fp",
    "valor_dem_hp_trib", "valor_dem_hp_isenta",
    "valor_dem_fp_trib", "valor_dem_fp_isenta",
    "valor_tusd_hp", "valor_tusd_fp",
    "soma_itens", "desconto_fonte_total",
    "ben_liquido", "ben_bruto", "impostos_ben",
    "encargos", "total_distribuidora",
    "total_consumo_kwh", "base_comercializadora", "total_comercializadora", "custo_total",
]


def test_chaves_resultado(resultado_base):
    for chave in CHAVES_ESPERADAS:
        assert chave in resultado_base, f"Chave ausente: {chave}"


# ── Split automático ───────────────────────────────────────────────────────────

def test_split_hp(resultado_base):
    """Demanda faturada = max(contratada, medida); split tributada/isenta."""
    assert resultado_base["dem_hp_faturada"] == pytest.approx(
        2_980.0, abs=0.01)
    assert resultado_base["dem_hp_tributada"] == pytest.approx(
        2_527.65, abs=0.01)
    assert resultado_base["dem_hp_isenta"] == pytest.approx(452.35, abs=0.01)


def test_split_fp(resultado_base):
    assert resultado_base["dem_fp_faturada"] == pytest.approx(
        3_280.0, abs=0.01)
    assert resultado_base["dem_fp_tributada"] == pytest.approx(
        2_902.31, abs=0.01)
    assert resultado_base["dem_fp_isenta"] == pytest.approx(377.69, abs=0.01)


def test_medida_maior_que_contratada_isenta_zero():
    """Se medida >= contratada, porção isenta = 0."""
    r = calcular_fatura_azul(
        demanda_hp_contratada_kw=100, demanda_fp_contratada_kw=200,
        demanda_hp_medida_kw=150, demanda_fp_medida_kw=250,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_hp_isenta"] == pytest.approx(0.0, abs=0.01)
    assert r["dem_fp_isenta"] == pytest.approx(0.0, abs=0.01)
    assert r["dem_hp_faturada"] == pytest.approx(150.0, abs=0.01)
    assert r["dem_fp_faturada"] == pytest.approx(250.0, abs=0.01)


# ── Testes de base (sem imposto) ───────────────────────────────────────────────

def test_base_dem_hp_trib(resultado_base):
    esperado = 2_527.65 * AZUL_DEMANDA_HP * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_hp_trib"] == pytest.approx(
        esperado, abs=0.01)


def test_base_dem_hp_isenta(resultado_base):
    esperado = 452.35 * AZUL_DEMANDA_HP * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_hp_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_base_dem_fp_trib(resultado_base):
    esperado = 2_902.31 * AZUL_DEMANDA_FP * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_fp_trib"] == pytest.approx(
        esperado, abs=0.01)


def test_base_dem_fp_isenta(resultado_base):
    esperado = 377.69 * AZUL_DEMANDA_FP * (1 - DESCONTO_FONTE_INCENTIVADA)
    assert resultado_base["base_dem_fp_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_base_tusd_hp(resultado_base):
    esperado = (115_251.52 / 1000) * AZUL_TUSD_HP
    assert resultado_base["base_tusd_hp"] == pytest.approx(esperado, abs=0.01)


def test_base_tusd_fp(resultado_base):
    esperado = (1_206_468.05 / 1000) * AZUL_TUSD_FP
    assert resultado_base["base_tusd_fp"] == pytest.approx(esperado, abs=0.01)


# ── Testes de gross-up ─────────────────────────────────────────────────────────

def test_gross_up_dem_hp_trib(resultado_base):
    """Demanda HP usada → tributada (ICMS + PIS/COFINS)."""
    esperado = resultado_base["base_dem_hp_trib"] / FATOR_TRIBUTADO
    assert resultado_base["valor_dem_hp_trib"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_dem_hp_isenta(resultado_base):
    """Demanda HP não usada → isenta ICMS (só PIS/COFINS)."""
    esperado = resultado_base["base_dem_hp_isenta"] / FATOR_ISENTO_ICMS
    assert resultado_base["valor_dem_hp_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_dem_fp_trib(resultado_base):
    esperado = resultado_base["base_dem_fp_trib"] / FATOR_TRIBUTADO
    assert resultado_base["valor_dem_fp_trib"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_dem_fp_isenta(resultado_base):
    esperado = resultado_base["base_dem_fp_isenta"] / FATOR_ISENTO_ICMS
    assert resultado_base["valor_dem_fp_isenta"] == pytest.approx(
        esperado, abs=0.01)


def test_gross_up_energia_sempre_tributada(resultado_base):
    """TUSD energia é sempre tributada."""
    esperado_hp = resultado_base["base_tusd_hp"] / FATOR_TRIBUTADO
    esperado_fp = resultado_base["base_tusd_fp"] / FATOR_TRIBUTADO
    assert resultado_base["valor_tusd_hp"] == pytest.approx(
        esperado_hp, abs=0.01)
    assert resultado_base["valor_tusd_fp"] == pytest.approx(
        esperado_fp, abs=0.01)


def test_soma_itens(resultado_base):
    esperado = (
        resultado_base["valor_dem_hp_trib"] +
        resultado_base["valor_dem_hp_isenta"]
        + resultado_base["valor_dem_fp_trib"] +
        resultado_base["valor_dem_fp_isenta"]
        + resultado_base["valor_tusd_hp"] + resultado_base["valor_tusd_fp"]
    )
    assert resultado_base["soma_itens"] == pytest.approx(esperado, abs=0.05)


# ── Testes do Benefício ────────────────────────────────────────────────────────

def test_ben_liquido(resultado_base):
    esperado = resultado_base["desconto_fonte_total"]
    assert resultado_base["ben_liquido"] == pytest.approx(esperado, abs=0.02)


def test_impostos_ben(resultado_base):
    assert resultado_base["impostos_ben"] > 0


def test_ben_bruto(resultado_base):
    esperado = resultado_base["ben_liquido"] + resultado_base["impostos_ben"]
    assert resultado_base["ben_bruto"] == pytest.approx(esperado, abs=0.05)


def test_ben_bruto_positivo(resultado_base):
    assert resultado_base["ben_bruto"] > resultado_base["ben_liquido"]


# ── Testes do Total Distribuidora ──────────────────────────────────────────────

def test_total_distribuidora_formula(resultado_base):
    esperado = (
        resultado_base["soma_itens"]
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


# ── Teste do Custo Total ───────────────────────────────────────────────────────

def test_custo_total(resultado_base):
    esperado = resultado_base["total_distribuidora"] + \
        resultado_base["total_comercializadora"]
    assert resultado_base["custo_total"] == pytest.approx(esperado, abs=0.05)


# ── Testes de borda ────────────────────────────────────────────────────────────

def test_consumo_zero():
    r = calcular_fatura_azul(
        demanda_hp_contratada_kw=100, demanda_fp_contratada_kw=200,
        demanda_hp_medida_kw=80, demanda_fp_medida_kw=150,
        consumo_hp_kwh=0, consumo_fp_kwh=0,
    )
    assert r["base_tusd_hp"] == 0.0
    assert r["base_tusd_fp"] == 0.0
    assert r["total_comercializadora"] == 0.0
    assert r["total_consumo_kwh"] == 0.0


def test_demanda_zero():
    r = calcular_fatura_azul(
        demanda_hp_contratada_kw=0, demanda_fp_contratada_kw=0,
        demanda_hp_medida_kw=0, demanda_fp_medida_kw=0,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["ben_liquido"] == 0.0  # sem demanda, sem desconto
    assert r["desconto_fonte_total"] == 0.0
    assert r["impostos_ben"] == pytest.approx(0.0, abs=0.01)


def test_tudo_zero():
    r = calcular_fatura_azul(0, 0, 0, 0, 0, 0, 0)
    assert r["custo_total"] == 0.0


def test_encargos_somados(resultado_base):
    r_sem = calcular_fatura_azul(**{**CASO_BASE, "encargos": 0.0})
    diff = resultado_base["total_distribuidora"] - r_sem["total_distribuidora"]
    assert diff == pytest.approx(CASO_BASE["encargos"], abs=0.01)


# ── Teste: demanda toda contratada e não usada → tudo isenta ───────────────────

def test_demanda_toda_isenta():
    """Se medida = 0, toda demanda contratada fica isenta ICMS."""
    r = calcular_fatura_azul(
        demanda_hp_contratada_kw=1000, demanda_fp_contratada_kw=2000,
        demanda_hp_medida_kw=0, demanda_fp_medida_kw=0,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_hp_tributada"] == 0.0
    assert r["dem_fp_tributada"] == 0.0
    assert r["dem_hp_isenta"] == pytest.approx(1000.0)
    assert r["dem_fp_isenta"] == pytest.approx(2000.0)
    # Gross-up da demanda deve usar fator isento (base já com desconto 50%)
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    esperado_hp = (1000 * AZUL_DEMANDA_HP * fator_dem) / FATOR_ISENTO_ICMS
    assert r["valor_dem_hp_isenta"] == pytest.approx(esperado_hp, abs=0.01)
    assert r["valor_dem_hp_trib"] == 0.0


def test_demanda_toda_tributada():
    """Se medida >= contratada, toda demanda é tributada."""
    r = calcular_fatura_azul(
        demanda_hp_contratada_kw=1000, demanda_fp_contratada_kw=2000,
        demanda_hp_medida_kw=1500, demanda_fp_medida_kw=2500,
        consumo_hp_kwh=10_000, consumo_fp_kwh=50_000,
    )
    assert r["dem_hp_isenta"] == pytest.approx(0.0)
    assert r["dem_fp_isenta"] == pytest.approx(0.0)
    assert r["dem_hp_tributada"] == pytest.approx(1500.0)
    assert r["dem_fp_tributada"] == pytest.approx(2500.0)
    # Gross-up deve usar fator tributado (base já com desconto 50%)
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    esperado_hp = (1500 * AZUL_DEMANDA_HP * fator_dem) / FATOR_TRIBUTADO
    assert r["valor_dem_hp_trib"] == pytest.approx(esperado_hp, abs=0.01)
    assert r["valor_dem_hp_isenta"] == 0.0


# ── Teste de valores absolutos (dados da fatura real) ──────────────────────────

def test_valores_absolutos_fatura():
    """Verificação cruzada com dados da fatura."""
    r = calcular_fatura_azul(**CASO_BASE)

    # Split HP: isenta 452.35, tributada 2527.65
    assert r["dem_hp_isenta"] == pytest.approx(452.35, abs=0.01)
    assert r["dem_hp_tributada"] == pytest.approx(2_527.65, abs=0.01)

    # Split FP: isenta 377.69, tributada 2902.31
    assert r["dem_fp_isenta"] == pytest.approx(377.69, abs=0.01)
    assert r["dem_fp_tributada"] == pytest.approx(2_902.31, abs=0.01)

    # total_consumo = 115251.52 + 1206468.05 = 1321719.57
    assert r["total_consumo_kwh"] == pytest.approx(1_321_719.57, abs=0.01)

    # base_comercializadora = 1321719.57 × 0.308 = 407,089.63
    assert r["base_comercializadora"] == pytest.approx(407_089.63, abs=0.01)

    # total_comercializadora = 407089.63 / FATOR_COMERCIALIZADORA
    assert r["total_comercializadora"] == pytest.approx(
        407_089.63 / FATOR_COMERCIALIZADORA, abs=0.01)

    assert r["custo_total"] > 0
