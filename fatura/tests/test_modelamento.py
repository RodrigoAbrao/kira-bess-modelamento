"""Testes unitários — simulate_bess_day e lógica de simulação BESS."""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path para importar modelamento_anual
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modelamento_anual import (
    simulate_bess_day,
    BESS_CAPACIDADE_KWH,
    BESS_POTENCIA_SAIDA,
    BESS_POTENCIA_CARGA,
    BESS_CARGA_INICIO,
    BESS_CARGA_FIM,
    BESS_GRID_MARGIN,
    BESS_WEEKEND_DEM_CAP,
    DT,
)
from fatura.premissas import VERDE_TUSD_HP, VERDE_TUSD_FP, FATOR_TRIBUTADO


# ── Helpers para construir day_data sintético ────────────────────────────────

def _make_day_data(date_str, slots):
    """
    Cria um DataFrame similar ao que load_and_clean() produz.

    Parameters
    ----------
    date_str : str
        Data no formato 'YYYY-MM-DD' (ex: '2025-11-03' = segunda).
    slots : list[dict]
        Cada dict tem: hora, minuto, grandeza, medicao, valor.
    """
    rows = []
    for s in slots:
        ts = pd.Timestamp(f"{date_str} {s['hora']:02d}:{s['minuto']:02d}:00")
        rows.append({
            "Timestamp": ts,
            "Valor": s["valor"],
            "Medicao": s["medicao"],
            "Grandeza": s["grandeza"],
            "Mes": "Nov",
            "Tipo": "Real",
            "dia": ts.date(),
            "hora": ts.hour,
            "minuto": ts.minute,
            "hora_frac": ts.hour + ts.minute / 60.0,
        })
    return pd.DataFrame(rows)


def _zero_solar():
    """Solar profile com zero em todas as horas."""
    return pd.Series(0.0, index=range(24))


def _flat_solar(kw=500.0):
    """Solar profile constante durante 7h–17h."""
    s = pd.Series(0.0, index=range(24))
    for h in range(7, 17):
        s[h] = kw
    return s


def _make_weekday_slots(date_str, dem_fp=2000.0, cons_fp_per_slot=500.0,
                         dem_hp=2500.0, cons_hp_per_slot=600.0,
                         n_charge_slots=30, n_hp_slots=12):
    """
    Gera slots para um dia útil típico:
    - n_charge_slots de FP na janela de carga (07:30–15:00)
    - n_hp_slots de HP na ponta (17:30–20:15)
    - Alguns slots FP fora da carga e fora da ponta
    """
    slots = []
    # Slots FP na janela de carga (07:30–15:00)
    h, m = 7, 30
    for _ in range(n_charge_slots):
        slots.append({"hora": h, "minuto": m, "grandeza": "Demanda",
                       "medicao": "Demanda ativa Fora de Ponta", "valor": dem_fp})
        slots.append({"hora": h, "minuto": m, "grandeza": "Consumo",
                       "medicao": "Consumo ativo Fora de Ponta", "valor": cons_fp_per_slot})
        m += 15
        if m >= 60:
            m -= 60
            h += 1

    # Slots HP na ponta (17:30–20:15)
    h, m = 17, 30
    for _ in range(n_hp_slots):
        slots.append({"hora": h, "minuto": m, "grandeza": "Demanda",
                       "medicao": "Demanda ativa de Ponta", "valor": dem_hp})
        slots.append({"hora": h, "minuto": m, "grandeza": "Consumo",
                       "medicao": "Consumo ativo de Ponta", "valor": cons_hp_per_slot})
        m += 15
        if m >= 60:
            m -= 60
            h += 1

    return _make_day_data(date_str, slots)


def _make_weekend_slots(date_str, dem_fp=2000.0, cons_fp_per_slot=500.0,
                         n_slots=48):
    """Gera slots para um dia de fim de semana — tudo FP."""
    slots = []
    h, m = 0, 0
    for _ in range(n_slots):
        slots.append({"hora": h, "minuto": m, "grandeza": "Demanda",
                       "medicao": "Demanda ativa Fora de Ponta", "valor": dem_fp})
        slots.append({"hora": h, "minuto": m, "grandeza": "Consumo",
                       "medicao": "Consumo ativo Fora de Ponta", "valor": cons_fp_per_slot})
        m += 15
        if m >= 60:
            m -= 60
            h += 1
    return _make_day_data(date_str, slots)


# ══════════════════════════════════════════════════════════════════════════════
#  TestBessDiaUtil
# ══════════════════════════════════════════════════════════════════════════════

class TestBessDiaUtil:
    """Dia útil com ponta — BESS carrega e descarrega."""

    def test_bess_charges_and_discharges(self):
        """BESS deve carregar na janela e descarregar na ponta."""
        day = _make_weekday_slots("2025-11-03")  # segunda-feira
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["bess_charge_kwh"] > 0, "BESS deve carregar"
        assert r["cons_hp_residual"] < r["cons_hp_total"], "BESS deve reduzir HP"

    def test_soc_final_non_negative(self):
        """SOC final nunca pode ser negativo."""
        day = _make_weekday_slots("2025-11-03")
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["soc_final"] >= 0.0

    def test_cons_hp_total_correct(self):
        """Consumo HP total = soma de todos os slots HP."""
        n_hp = 12
        cons_hp_per = 600.0
        day = _make_weekday_slots("2025-11-03", cons_hp_per_slot=cons_hp_per,
                                   n_hp_slots=n_hp)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["cons_hp_total"] == pytest.approx(n_hp * cons_hp_per, abs=1.0)

    def test_charge_limited_by_capacity(self):
        """Carga BESS não pode exceder a capacidade de 6.200 kWh."""
        day = _make_weekday_slots("2025-11-03", n_charge_slots=30)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["bess_charge_kwh"] <= BESS_CAPACIDADE_KWH + 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  TestSocProporcional
# ══════════════════════════════════════════════════════════════════════════════

class TestSocProporcional:
    """A2: Descarga SOC-proporcional distribui energia entre slots HP."""

    def test_uniform_distribution(self):
        """Com demanda HP constante, descarga deve ser ~uniforme entre slots."""
        n_hp = 12
        dem_hp = 2000.0  # abaixo de 3100 kW
        cons_hp_per = dem_hp * DT  # 500 kWh por slot

        day = _make_weekday_slots("2025-11-03", dem_hp=dem_hp,
                                   cons_hp_per_slot=cons_hp_per,
                                   n_hp_slots=n_hp)
        # SOC = 3000 kWh — não cobre tudo, forçando budget
        r = simulate_bess_day(day, _zero_solar(), initial_soc=3000.0,
                               collect_timeline=True)

        # Verificar que tem descarga em todos os slots HP
        hp_discharges = [t for t in r["timeline"] if t["bess_kw"] < -1.0]
        assert len(hp_discharges) >= n_hp - 1, \
            f"SOC-proporcional deve descarregar em (quase) todos os slots HP, got {len(hp_discharges)}"

    def test_no_early_depletion(self):
        """Com SOC limitado, o BESS não deve esgotar nos primeiros slots."""
        n_hp = 12
        dem_hp = 2500.0
        cons_hp_per = dem_hp * DT

        day = _make_weekday_slots("2025-11-03", dem_hp=dem_hp,
                                   cons_hp_per_slot=cons_hp_per,
                                   n_hp_slots=n_hp)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=2000.0,
                               collect_timeline=True)

        # Verificar que o último slot HP ainda tem descarga
        hp_slots = [t for t in r["timeline"]
                    if t["cons_hp_kwh"] > 0]
        if hp_slots:
            last_hp = hp_slots[-1]
            assert last_hp["bess_kw"] < -0.1, \
                "Último slot HP deve ter descarga — SOC-proporcional previne esgotamento precoce"

    def test_full_soc_covers_small_demand(self):
        """Com SOC cheio e demanda HP baixa, BESS cobre (quase) tudo."""
        n_hp = 12
        dem_hp = 800.0  # baixo
        cons_hp_per = dem_hp * DT

        day = _make_weekday_slots("2025-11-03", dem_hp=dem_hp,
                                   cons_hp_per_slot=cons_hp_per,
                                   n_hp_slots=n_hp)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=BESS_CAPACIDADE_KWH)
        total_hp = n_hp * cons_hp_per
        # Com 6200 kWh e demanda de 2400 kWh total, deve cobrir ~95%
        covered = total_hp - r["cons_hp_residual"]
        coverage = covered / total_hp
        assert coverage > 0.90, f"Coverage deveria ser > 90%, got {coverage:.1%}"


# ══════════════════════════════════════════════════════════════════════════════
#  TestCargaHeadroom
# ══════════════════════════════════════════════════════════════════════════════

class TestCargaHeadroom:
    """A4: Headroom limita carga para que dem_FP não ultrapasse BESS_POTENCIA_SAIDA."""

    def test_headroom_limits_charge(self):
        """Se dem_FP líquida é alta, p_charge deve ser reduzida pelo headroom."""
        # Demanda FP = 2800 kW → headroom = 3100 - 2800 = 300 kW
        # Sem headroom p_charge seria 1000 kW
        dem_fp = 2800.0
        day = _make_weekday_slots("2025-11-03", dem_fp=dem_fp, n_hp_slots=4)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        # dem_fp_bess deve ser ≤ 3100 kW (com margem de float)
        assert r["dem_fp_bess"] <= BESS_POTENCIA_SAIDA + 50, \
            f"dem_fp_bess ({r['dem_fp_bess']:.0f}) deve ser ≤ {BESS_POTENCIA_SAIDA} kW"

    def test_headroom_with_solar_allows_more_charge(self):
        """Solar reduz dem_líquida, permitindo p_charge maior."""
        dem_fp = 3000.0
        solar = _flat_solar(kw=500.0)  # Solar 500 kW → dem_liq = 2500 → headroom = 600
        day = _make_weekday_slots("2025-11-03", dem_fp=dem_fp, n_hp_slots=4)
        r = simulate_bess_day(day, solar, initial_soc=0.0)
        # Com solar, deve carregar mais do que sem solar com mesma dem_fp
        r_no_solar = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["bess_charge_kwh"] >= r_no_solar["bess_charge_kwh"] - 1.0

    def test_no_headroom_needed_low_demand(self):
        """Com dem_FP baixa, headroom não limita — carga normal a 1000 kW."""
        dem_fp = 1000.0  # headroom = 3100 - 1000 = 2100 >> 1000
        day = _make_weekday_slots("2025-11-03", dem_fp=dem_fp, n_hp_slots=4)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        # Deve carregar normalmente: 30 slots × 1000 kW × 0.25h = 7500, cap 6200
        assert r["bess_charge_kwh"] == pytest.approx(BESS_CAPACIDADE_KWH, abs=50)


# ══════════════════════════════════════════════════════════════════════════════
#  TestBessFimDeSemana
# ══════════════════════════════════════════════════════════════════════════════

class TestBessFimDeSemana:
    """Fim de semana — BESS faz peak-shaving FP com cap 2800 kW."""

    def test_weekend_no_hp(self):
        """Resultado do weekend deve ter cons_hp_total = 0."""
        day = _make_weekend_slots("2025-11-01")  # sábado
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["cons_hp_total"] == 0.0
        assert r["cons_hp_residual"] == 0.0

    def test_weekend_peak_shaving(self):
        """Se dem_FP > 2800, BESS deve descarregar para manter cap."""
        # Criar weekend com demanda alta = 3200 kW (> 2800 cap)
        day = _make_weekend_slots("2025-11-01", dem_fp=3200.0, n_slots=48)
        # SOC cheio para cobrir todos os slots com excess de 400 kW
        r = simulate_bess_day(day, _zero_solar(), initial_soc=BESS_CAPACIDADE_KWH)
        # dem_fp_bess deve ser próximo ou abaixo de 2800 (peak-shaving)
        assert r["dem_fp_bess"] <= BESS_WEEKEND_DEM_CAP + 100, \
            f"dem_fp_bess ({r['dem_fp_bess']:.0f}) deve ser próximo a {BESS_WEEKEND_DEM_CAP}"

    def test_weekend_charge_respects_cap(self):
        """Carga no weekend não deve elevar demanda acima de 2800 kW."""
        day = _make_weekend_slots("2025-11-01", dem_fp=2000.0, n_slots=48)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        assert r["dem_fp_bess"] <= BESS_WEEKEND_DEM_CAP + 10


# ══════════════════════════════════════════════════════════════════════════════
#  TestBessFeriado
# ══════════════════════════════════════════════════════════════════════════════

class TestBessFeriado:
    """Feriado em dia útil (sem HP) — BESS permanece idle."""

    def test_holiday_idle(self):
        """Em feriado sem HP, BESS não carrega nem descarrega."""
        # Dia útil mas sem nenhum slot HP → detectado como feriado
        slots = []
        h, m = 8, 0
        for _ in range(40):
            slots.append({"hora": h, "minuto": m, "grandeza": "Demanda",
                           "medicao": "Demanda ativa Fora de Ponta", "valor": 2000.0})
            slots.append({"hora": h, "minuto": m, "grandeza": "Consumo",
                           "medicao": "Consumo ativo Fora de Ponta", "valor": 500.0})
            m += 15
            if m >= 60:
                m -= 60
                h += 1
        # quarta-feira (dia útil) sem HP
        day = _make_day_data("2025-11-05", slots)
        r = simulate_bess_day(day, _zero_solar(), initial_soc=1000.0)
        assert r["cons_hp_total"] == 0.0
        assert r["bess_charge_kwh"] == 0.0
        assert r["soc_final"] == pytest.approx(1000.0, abs=0.1)


# ══════════════════════════════════════════════════════════════════════════════
#  TestDisplayOutlier
# ══════════════════════════════════════════════════════════════════════════════

class TestDisplayOutlier:
    """A3: Tarifa HP efetiva usada no display de outliers."""

    def test_tarifa_hp_efetiva_formula(self):
        """Verifica a fórmula correta da tarifa HP efetiva."""
        tarifa_hp_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
        assert tarifa_hp_efetiva == pytest.approx(1218.42, abs=0.01)

    def test_tarifa_hp_efetiva_less_than_tusd_hp(self):
        """Tarifa efetiva deve ser ~metade da TUSD HP (com desconto)."""
        tarifa_hp_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
        assert tarifa_hp_efetiva < VERDE_TUSD_HP
        ratio = tarifa_hp_efetiva / VERDE_TUSD_HP
        assert ratio == pytest.approx(0.5305, abs=0.01)

    def test_custo_residual_calculation(self):
        """Custo residual deve usar tarifa_hp_efetiva, não VERDE_TUSD_HP."""
        hp_residual_kwh = 10_000.0  # 10 MWh
        tarifa_hp_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
        custo_correto = (hp_residual_kwh / 1000) * tarifa_hp_efetiva / FATOR_TRIBUTADO
        custo_errado = (hp_residual_kwh / 1000) * VERDE_TUSD_HP / FATOR_TRIBUTADO
        assert custo_correto < custo_errado
        assert custo_errado / custo_correto == pytest.approx(1.885, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════════
#  TestBessSolar
# ══════════════════════════════════════════════════════════════════════════════

class TestBessSolar:
    """Interação Solar + BESS."""

    def test_solar_reduces_fp_net(self):
        """Solar deve reduzir consumo FP líquido."""
        day = _make_weekday_slots("2025-11-03", n_hp_slots=4)
        r_no_solar = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        r_solar = simulate_bess_day(day, _flat_solar(500.0), initial_soc=0.0)
        assert r_solar["cons_fp_net"] < r_no_solar["cons_fp_net"]

    def test_solar_does_not_affect_hp(self):
        """Solar não gera durante ponta (noite) — HP total inalterado."""
        day = _make_weekday_slots("2025-11-03", n_hp_slots=12)
        r_no_solar = simulate_bess_day(day, _zero_solar(), initial_soc=0.0)
        r_solar = simulate_bess_day(day, _flat_solar(500.0), initial_soc=0.0)
        assert r_solar["cons_hp_total"] == pytest.approx(
            r_no_solar["cons_hp_total"], abs=1.0)
