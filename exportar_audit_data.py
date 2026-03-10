"""
exportar_audit_data.py — Exporta audit_data.json para kira-data
================================================================

Gera o JSON de insumo que o frontend Next.js (kira-data) consome.
Toda a matemática financeira vem do modelo dia-a-dia (oficial).
O perfil horário (96 slots) é construído via mediana dos dias reais
apenas para visualização — não afeta nenhum número financeiro.

Uso::

    python exportar_audit_data.py

Saída::

    ../kira-data/src/data/audit_data.json

O agente do kira-data lê esse JSON e renderiza nas páginas:
    - /data-room           → KPIs financeiros, payback, TIR, VPL
    - /data-room/energia   → Perfil horário, gráfico mensal
    - /data-room/simulacao-fatura → Decomposição C1/C2/C3
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from pathlib import Path

from modelamento_anual import (
    load_full_year, load_solar_profile, simulate_bess_day,
    BESS_CAPACIDADE_KWH, BESS_POTENCIA_SAIDA, BESS_POTENCIA_CARGA,
    BESS_CARGA_INICIO, BESS_CARGA_FIM, BESS_GRID_MARGIN,
    CAPEX_SOLAR, CAPEX_BESS, CAPEX_IMPLANTACAO, CAPEX_TOTAL, CAPEX_SOLAR_ONLY,
    DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
    VIDA_UTIL_ANOS, TAXA_DESCONTO,
    ORDEM_ANO, _MES_NUM, DT,
)
from fatura import calcular_fatura_azul, calcular_fatura_verde
from fatura.premissas import (
    PIS, COFINS, ICMS, PIS_COFINS, FATOR_TRIBUTADO, FATOR_ISENTO_ICMS,
    DESCONTO_FONTE_INCENTIVADA,
    AZUL_DEMANDA_HP, AZUL_DEMANDA_FP, AZUL_TUSD_HP, AZUL_TUSD_FP,
    VERDE_DEMANDA_UNICA, VERDE_TUSD_HP, VERDE_TUSD_FP,
    TE_COMERCIALIZADORA,
)

# ── Paths ───────────────────────────────────────────────────────────────────
KIRA_DATA_DIR = Path(__file__).resolve().parent.parent / "kira-data" / "src" / "data"
LOCAL_DATA_DIR = Path("data")


# ─────────────────────────────────────────────────────────────────────────────
#  1. SIMULAÇÃO DIA-A-DIA (reutiliza modelamento_anual.py)
# ─────────────────────────────────────────────────────────────────────────────
def run_simulation():
    """Executa o dia-a-dia completo e retorna df_days, monthly, solar_monthly."""
    year = load_full_year()
    solar_profile, solar_monthly = load_solar_profile()

    dias = sorted(year.dia.unique())
    day_results = []

    for dia in dias:
        day_data = year[year.dia == dia].copy()
        mes = day_data.Mes.iloc[0]
        tipo = day_data.Tipo.iloc[0]
        mes_num = _MES_NUM[mes]

        solar_for_month = {}
        for h in range(24):
            try:
                solar_for_month[h] = float(solar_profile.get((mes_num, h), 0))
            except (KeyError, TypeError):
                solar_for_month[h] = 0.0

        res = simulate_bess_day(day_data, pd.Series(solar_for_month))
        day_results.append({"dia": dia, "mes": mes, "tipo": tipo, **res})

    df_days = pd.DataFrame(day_results)
    df_days["dia"] = pd.to_datetime(df_days["dia"])
    df_days["dow"] = df_days.dia.dt.day_name()
    df_days["has_ponta"] = df_days.cons_hp_total > 0

    # ── Faturas mês a mês ───────────────────────────────────────────────────
    monthly = []
    for mes in ORDEM_ANO:
        dm = df_days[df_days.mes == mes]
        if len(dm) == 0:
            continue

        cons_hp = float(dm.cons_hp_total.sum())
        cons_fp = float(dm.cons_fp_total.sum())
        cons_hp_resid = float(dm.cons_hp_residual.sum())
        cons_fp_net = float(dm.cons_fp_net.sum())
        solar_gen = solar_monthly[mes]

        dem_hp_max = float(dm.dem_hp_max.max())
        dem_fp_max = float(dm.dem_fp_max.max())
        dem_fp_solar = float(dm.dem_fp_solar.max())
        dem_fp_bess = float(dm.dem_fp_bess.max())
        dem_hp_resid = float(dm.dem_hp_resid.max())

        fat_c1 = calcular_fatura_azul(
            DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
            dem_hp_max, dem_fp_max, cons_hp, cons_fp)

        cons_fp_solar = max(0.0, cons_fp - solar_gen)
        fat_c2 = calcular_fatura_azul(
            DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
            dem_hp_max, dem_fp_solar, cons_hp, cons_fp_solar)

        dem_verde = max(dem_fp_bess, dem_hp_resid)
        fat_c3 = calcular_fatura_verde(
            DEMANDA_FP_CONTRATADA, dem_verde, cons_hp_resid, cons_fp_net)

        monthly.append({
            "mes": mes,
            "c1": fat_c1["custo_total"], "c2": fat_c2["custo_total"],
            "c3": fat_c3["custo_total"],
            "c1_detail": fat_c1, "c2_detail": fat_c2, "c3_detail": fat_c3,
            "cons_hp": cons_hp, "cons_fp": cons_fp,
            "cons_hp_resid": cons_hp_resid, "cons_fp_net": cons_fp_net,
            "solar_gen": solar_gen,
            "dem_hp": dem_hp_max, "dem_fp": dem_fp_max,
            "dem_verde": dem_verde, "dem_hp_resid": dem_hp_resid,
            "n_ponta": int(dm.has_ponta.sum()),
            "n_bess_dead": int(dm.bess_dead.sum()),
        })

    return df_days, monthly, solar_monthly, solar_profile, year


# ─────────────────────────────────────────────────────────────────────────────
#  2. PERFIL HORÁRIO (mediana dos dias reais — VISUAL ONLY)
# ─────────────────────────────────────────────────────────────────────────────
def build_profile(year: pd.DataFrame, solar_profile: pd.Series) -> dict:
    """
    Constrói perfil de 96 slots via mediana dos dias reais.
    Usado APENAS para visualização no frontend — sem impacto financeiro.
    """
    # Demanda mediana por slot (todas as medições de demanda FP)
    dem_fp = year[(year.Grandeza == "Demanda") &
                  (year.Medicao == "Demanda ativa Fora de Ponta")].copy()
    dem_hp = year[(year.Grandeza == "Demanda") &
                  (year.Medicao == "Demanda ativa de Ponta")].copy()

    dem_fp["slot"] = dem_fp.hora * 4 + dem_fp.minuto // 15
    dem_hp["slot"] = dem_hp.hora * 4 + dem_hp.minuto // 15

    # Demanda total por slot = mediana(FP) nos slots FP, mediana(HP) nos slots HP
    perfil_demanda = [0.0] * 96
    perfil_dem_hp_only = [0.0] * 96
    for s in range(96):
        fp_vals = dem_fp[dem_fp.slot == s]["Valor"]
        hp_vals = dem_hp[dem_hp.slot == s]["Valor"]
        dem_val = float(fp_vals.median()) if len(fp_vals) > 0 else 0.0
        hp_val = float(hp_vals.median()) if len(hp_vals) > 0 else 0.0
        perfil_demanda[s] = round(max(dem_val, hp_val), 1)
        perfil_dem_hp_only[s] = round(hp_val, 1)

    # Solar médio anual por slot (kW)
    perfil_solar = [0.0] * 96
    for s in range(96):
        h = s // 4
        vals = []
        for m in range(1, 13):
            try:
                vals.append(float(solar_profile.get((m, h), 0)))
            except (KeyError, TypeError):
                pass
        perfil_solar[s] = round(np.mean(vals) if vals else 0.0, 1)

    # is_ponta: True se HP > 0 naquele slot (mediana)
    is_ponta = [perfil_dem_hp_only[s] > 0 for s in range(96)]

    # Grid C3 = demanda - solar + BESS_charge (durante carga) ou demanda - BESS_discharge (ponta)
    # Simulação simplificada para perfil visual
    soc = 0.0
    perfil_grid_c3 = [0.0] * 96
    perfil_soc = [0.0] * 96

    for s in range(96):
        h = s // 4
        dem = perfil_demanda[s]
        sol = perfil_solar[s]

        if BESS_CARGA_INICIO <= h < BESS_CARGA_FIM:
            # Carga BESS
            espaco = BESS_CAPACIDADE_KWH - soc
            p_charge = min(BESS_POTENCIA_CARGA, espaco / DT)
            soc += p_charge * DT
            perfil_grid_c3[s] = round(max(0, dem - sol) + p_charge, 1)
        elif is_ponta[s] and soc > 0:
            # Descarga BESS
            bess_target = perfil_demanda[s] * (1 - BESS_GRID_MARGIN)
            max_kw = min(bess_target, BESS_POTENCIA_SAIDA)
            actual = min(soc, max_kw * DT)
            soc -= actual
            residual_dem = max(0, dem - actual / DT)
            perfil_grid_c3[s] = round(residual_dem, 1)
        else:
            perfil_grid_c3[s] = round(max(0, dem - sol), 1)

        perfil_soc[s] = round(soc, 1)

    horas = [round(s * 0.25, 2) for s in range(96)]

    return {
        "n_dias_simulados": int(year.dia.nunique()),
        "n_slots": 96,
        "dt_h": 0.25,
        "metodologia_perfil": "mediana_dias_reais (visual only)",
        "demanda_mediana_geral": round(float(np.median(perfil_demanda)), 1),
        "demanda_mediana_max": round(float(max(perfil_demanda)), 1),
        "perfil_horario_demanda": perfil_demanda,
        "perfil_horario_solar": perfil_solar,
        "perfil_horario_grid_c3": perfil_grid_c3,
        "perfil_horario_soc": perfil_soc,
        "horas": horas,
        "is_ponta": is_ponta,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  3. MÉTRICAS FINANCEIRAS
# ─────────────────────────────────────────────────────────────────────────────
def compute_financials(eco_total: float, eco_solar: float) -> dict:
    """Calcula payback, TIR, VPL, ROI para Solar+BESS e Solar-only."""

    def _metrics(capex, eco):
        if eco <= 0:
            return {"payback_simples": 999, "vpl": 0, "tir": 0, "roi": 0}
        payback = capex / eco
        cf = [-capex] + [eco] * VIDA_UTIL_ANOS
        vpl = sum(v / (1 + TAXA_DESCONTO) ** t for t, v in enumerate(cf))
        roi = (eco * VIDA_UTIL_ANOS - capex) / capex * 100

        # TIR via bisseção
        lo, hi = -0.5, 5.0
        for _ in range(200):
            m = (lo + hi) / 2
            s = sum(v / (1 + m) ** t for t, v in enumerate(cf))
            if s > 0:
                lo = m
            else:
                hi = m
        tir = (lo + hi) / 2

        # Payback descontado
        acum = 0.0
        pd_y = float(VIDA_UTIL_ANOS)
        for t in range(1, VIDA_UTIL_ANOS + 1):
            pvt = eco / (1 + TAXA_DESCONTO) ** t
            acum += pvt
            if acum >= capex:
                prev = acum - pvt
                pd_y = (t - 1) + (capex - prev) / pvt
                break

        return {
            "payback_simples": round(payback, 1),
            "payback_descontado": round(pd_y, 1),
            "vpl": round(vpl, 2),
            "tir": round(tir * 100, 1),
            "roi": round(roi, 0),
        }

    m_total = _metrics(CAPEX_TOTAL, eco_total)
    m_solar = _metrics(CAPEX_SOLAR_ONLY, eco_solar)

    return {
        "eco_solar_mes": round(eco_solar / 12, 0),
        "eco_bess_mes": round((eco_total - eco_solar) / 12, 0),
        "eco_total_mes": round(eco_total / 12, 0),
        "eco_anual": round(eco_total, 0),
        "capex_solar": CAPEX_SOLAR,
        "capex_bess": CAPEX_BESS,
        "capex_implantacao": CAPEX_IMPLANTACAO,
        "capex_total": CAPEX_TOTAL,
        "capex_solar_only": CAPEX_SOLAR_ONLY,
        "payback_simples": m_total["payback_simples"],
        "payback_descontado": m_total["payback_descontado"],
        "vpl": m_total["vpl"],
        "tir": m_total["tir"],
        "roi": m_total["roi"],
        "taxa_desconto": TAXA_DESCONTO * 100,
        "vida_util": VIDA_UTIL_ANOS,
        # Solar-only
        "solar_payback": m_solar["payback_simples"],
        "solar_vpl": m_solar["vpl"],
        "solar_tir": m_solar["tir"],
        "solar_roi": m_solar["roi"],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  4. MONTAGEM DO JSON
# ─────────────────────────────────────────────────────────────────────────────
def build_audit_json(df_days, monthly, solar_monthly, solar_profile, year):
    """Monta o dict completo no schema que kira-data espera."""

    total_c1 = sum(m["c1"] for m in monthly)
    total_c2 = sum(m["c2"] for m in monthly)
    total_c3 = sum(m["c3"] for m in monthly)

    eco_solar = total_c1 - total_c2
    eco_total = total_c1 - total_c3

    # Consumos anuais agregados
    cons_hp_total = sum(m["cons_hp"] for m in monthly)
    cons_fp_total = sum(m["cons_fp"] for m in monthly)
    cons_hp_resid = sum(m["cons_hp_resid"] for m in monthly)
    cons_fp_net = sum(m["cons_fp_net"] for m in monthly)
    solar_total = sum(solar_monthly.values())

    # Demandas máximas anuais
    dem_hp_max = max(m["dem_hp"] for m in monthly)
    dem_fp_max = max(m["dem_fp"] for m in monthly)
    dem_verde_max = max(m["dem_verde"] for m in monthly)

    # C1 detail (fatura anual completa para decomposição)
    fat_c1_anual = calcular_fatura_azul(
        DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
        dem_hp_max, dem_fp_max,
        cons_hp_total / 12, cons_fp_total / 12)

    # Perfil visual
    perfil = build_profile(year, solar_profile)
    perfil["geracao_anual_mwh"] = round(solar_total / 1000, 1)
    perfil["geracao_pico_kw"] = round(max(perfil["perfil_horario_solar"]), 1)

    # BESS stats
    dias_ponta = df_days[df_days.has_ponta]
    bess_charge_medio = float(dias_ponta.bess_charge_kwh.mean()) if len(dias_ponta) > 0 else 0
    bess_descarga_medio = float((dias_ponta.cons_hp_total - dias_ponta.cons_hp_residual).mean()) if len(dias_ponta) > 0 else 0
    cobertura_pct = float((1 - cons_hp_resid / cons_hp_total) * 100) if cons_hp_total > 0 else 100

    # Resumo mensal para chart
    resumo_mensal = []
    for m in monthly:
        resumo_mensal.append({
            "mes": m["mes"],
            "c1": round(m["c1"], 0),
            "c2": round(m["c2"], 0),
            "c3": round(m["c3"], 0),
            "cons_hp_kwh": round(m["cons_hp"], 0),
            "cons_fp_kwh": round(m["cons_fp"], 0),
            "cons_hp_resid_kwh": round(m["cons_hp_resid"], 0),
            "solar_gen_kwh": round(m["solar_gen"], 0),
            "n_dias_ponta": m["n_ponta"],
            "n_bess_dead": m["n_bess_dead"],
        })

    # Outliers (dias com BESS dead)
    outliers = []
    dead_days = df_days[df_days.bess_dead].sort_values("cons_hp_residual", ascending=False)
    for _, r in dead_days.iterrows():
        outliers.append({
            "dia": r.dia.strftime("%Y-%m-%d"),
            "dow": r.dow,
            "mes": r.mes,
            "hp_total_kwh": round(r.cons_hp_total, 0),
            "hp_residual_kwh": round(r.cons_hp_residual, 0),
            "dem_hp_kw": round(r.dem_hp_max, 0),
            "cobertura_pct": round((1 - r.cons_hp_residual / r.cons_hp_total) * 100, 1) if r.cons_hp_total > 0 else 100,
        })

    audit = {
        "_meta": {
            "gerado_por": "exportar_audit_data.py",
            "metodologia": "dia-a-dia (365 dias × 96 slots)",
            "nota": "Todos os números financeiros vêm da simulação dia-a-dia. "
                    "O perfil horário é mediana dos dias reais (visual only).",
            "dias_simulados": int(len(df_days)),
            "dias_com_ponta": int(dias_ponta.shape[0]),
            "dias_bess_dead": int(dead_days.shape[0]),
            "cobertura_bess_pct": round(cobertura_pct, 1),
        },

        "premissas": {
            "ICMS": ICMS * 100,
            "PIS": PIS * 100,
            "COFINS": COFINS * 100,
            "PIS_COFINS": PIS_COFINS * 100,
            "FATOR_TRIBUTADO": round(FATOR_TRIBUTADO, 6),
            "FATOR_ISENTO_ICMS": round(FATOR_ISENTO_ICMS, 6),
            "DESCONTO_FONTE": DESCONTO_FONTE_INCENTIVADA * 100,
            "AZUL_DEMANDA_HP": AZUL_DEMANDA_HP,
            "AZUL_DEMANDA_FP": AZUL_DEMANDA_FP,
            "AZUL_TUSD_HP": AZUL_TUSD_HP,
            "AZUL_TUSD_FP": AZUL_TUSD_FP,
            "VERDE_DEMANDA_UNICA": VERDE_DEMANDA_UNICA,
            "VERDE_TUSD_HP": VERDE_TUSD_HP,
            "VERDE_TUSD_FP": VERDE_TUSD_FP,
            "TE_COMERCIALIZADORA": TE_COMERCIALIZADORA,
            "DEMANDA_HP_CONTRATADA": DEMANDA_HP_CONTRATADA,
            "DEMANDA_FP_CONTRATADA": DEMANDA_FP_CONTRATADA,
        },

        "perfil": perfil,

        "bess": {
            "capacidade_kwh": BESS_CAPACIDADE_KWH,
            "potencia_saida_kw": BESS_POTENCIA_SAIDA,
            "potencia_carga_kw": BESS_POTENCIA_CARGA,
            "carga_janela": f"{BESS_CARGA_INICIO}h–{BESS_CARGA_FIM}h (solar)",
            "descarga_janela": "ponta (automático via medidor)",
            "grid_margin_pct": BESS_GRID_MARGIN * 100,
            "energia_carga_kwh_dia": round(bess_charge_medio, 1),
            "energia_descarga_kwh_dia": round(bess_descarga_medio, 1),
            "cobertura_bess_pct": round(cobertura_pct, 1),
            "dias_bess_dead": int(dead_days.shape[0]),
        },

        "demandas": {
            "c1": {
                "hp_medida": round(dem_hp_max, 1),
                "fp_medida": round(dem_fp_max, 1),
                "hp_faturada": DEMANDA_HP_CONTRATADA,
                "fp_faturada": DEMANDA_FP_CONTRATADA,
                "hp_trib": round(dem_hp_max, 1),
                "hp_isenta": round(DEMANDA_HP_CONTRATADA - dem_hp_max, 1),
                "fp_trib": round(dem_fp_max, 1),
                "fp_isenta": round(DEMANDA_FP_CONTRATADA - dem_fp_max, 1),
            },
            "c2": {
                "hp_medida": round(dem_hp_max, 1),
                "fp_medida": round(max(m["dem_fp"] for m in monthly), 1),
            },
            "c3": {
                "dem_unica_medida": round(dem_verde_max, 1),
                "dem_unica_faturada": DEMANDA_FP_CONTRATADA,
            },
        },

        "consumos": {
            "c1": {
                "hp_kwh": round(cons_hp_total, 0),
                "fp_kwh": round(cons_fp_total, 0),
                "total_kwh": round(cons_hp_total + cons_fp_total, 0),
            },
            "c2": {
                "hp_kwh": round(cons_hp_total, 0),
                "fp_kwh": round(max(0, cons_fp_total - solar_total), 0),
                "total_kwh": round(cons_hp_total + max(0, cons_fp_total - solar_total), 0),
            },
            "c3": {
                "hp_kwh": round(cons_hp_resid, 0),
                "fp_kwh": round(cons_fp_net, 0),
                "total_kwh": round(cons_hp_resid + cons_fp_net, 0),
            },
        },

        "fatura_azul_c1_detalhe": {
            "dem_hp_fat": fat_c1_anual.get("dem_hp_faturada", DEMANDA_HP_CONTRATADA),
            "dem_fp_fat": fat_c1_anual.get("dem_fp_faturada", DEMANDA_FP_CONTRATADA),
            "base_dem_hp_trib": fat_c1_anual.get("base_dem_hp_trib", 0),
            "base_dem_hp_isen": fat_c1_anual.get("base_dem_hp_isenta", 0),
            "base_dem_fp_trib": fat_c1_anual.get("base_dem_fp_trib", 0),
            "base_dem_fp_isen": fat_c1_anual.get("base_dem_fp_isenta", 0),
            "base_tusd_hp": fat_c1_anual.get("base_tusd_hp", 0),
            "base_tusd_fp": fat_c1_anual.get("base_tusd_fp", 0),
            "base_te": fat_c1_anual.get("base_comercializadora", 0),
            "val_dem_hp_trib": fat_c1_anual.get("valor_dem_hp_trib", 0),
            "val_dem_hp_isen": fat_c1_anual.get("valor_dem_hp_isenta", 0),
            "val_dem_fp_trib": fat_c1_anual.get("valor_dem_fp_trib", 0),
            "val_dem_fp_isen": fat_c1_anual.get("valor_dem_fp_isenta", 0),
            "val_tusd_hp": fat_c1_anual.get("valor_tusd_hp", 0),
            "val_tusd_fp": fat_c1_anual.get("valor_tusd_fp", 0),
            "val_te": round(fat_c1_anual.get("base_comercializadora", 0) / FATOR_TRIBUTADO, 2),
            "ben_liq": fat_c1_anual.get("ben_liquido", 0),
            "imp_ben": fat_c1_anual.get("impostos_ben", 0),
            "ben_bruto": fat_c1_anual.get("ben_bruto", 0),
            "total_distrib": fat_c1_anual.get("total_distribuidora", 0),
        },

        "faturas": {
            "c1": {
                "custo_total": round(total_c1 / 12, 0),
                "total_distribuidora": round(fat_c1_anual.get("total_distribuidora", 0), 2),
                "total_comercializadora": round(fat_c1_anual.get("total_comercializadora", 0), 2),
            },
            "c2": {
                "custo_total": round(total_c2 / 12, 0),
            },
            "c3": {
                "custo_total": round(total_c3 / 12, 0),
                "total_distribuidora": round(monthly[0]["c3_detail"].get("total_distribuidora", 0), 2),
                "total_comercializadora": round(monthly[0]["c3_detail"].get("total_comercializadora", 0), 2),
            },
        },

        "financeiro": compute_financials(eco_total, eco_solar),

        "resumo_mensal": resumo_mensal,

        "outliers": {
            "total": len(outliers),
            "hp_residual_anual_kwh": round(cons_hp_resid, 0),
            "dias": outliers,
        },
    }

    return audit


# ─────────────────────────────────────────────────────────────────────────────
#  5. MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("  EXPORTAR AUDIT_DATA.JSON → kira-data")
    print("  Metodologia: dia-a-dia (oficial)")
    print("=" * 70)
    print()

    df_days, monthly, solar_monthly, solar_profile, year = run_simulation()
    audit = build_audit_json(df_days, monthly, solar_monthly, solar_profile, year)

    # ── Resumo console ──────────────────────────────────────────────────────
    meta = audit["_meta"]
    fin = audit["financeiro"]
    bess = audit["bess"]

    print(f"\n{'='*70}")
    print("  RESULTADO OFICIAL (dia-a-dia)")
    print(f"{'='*70}")
    print(f"  Dias simulados:     {meta['dias_simulados']}")
    print(f"  Dias com ponta:     {meta['dias_com_ponta']}")
    print(f"  Dias BESS dead:     {meta['dias_bess_dead']}")
    print(f"  Cobertura BESS:     {meta['cobertura_bess_pct']:.1f}%")
    print(f"  Carga BESS/dia:     {bess['energia_carga_kwh_dia']:.0f} kWh")
    print()
    print(f"  C1 AZUL (mês):      R$ {audit['faturas']['c1']['custo_total']:,.0f}")
    print(f"  C2 Solar (mês):     R$ {audit['faturas']['c2']['custo_total']:,.0f}")
    print(f"  C3 VERDE+BESS(mês): R$ {audit['faturas']['c3']['custo_total']:,.0f}")
    print(f"  Economia/mês:       R$ {fin['eco_total_mes']:,.0f}")
    print(f"  Economia/ano:       R$ {fin['eco_anual']:,.0f}")
    print()
    print(f"  Payback simples:    {fin['payback_simples']} anos")
    print(f"  TIR:                {fin['tir']}%")
    print(f"  VPL:                R$ {fin['vpl']:,.2f}")
    print(f"  ROI:                {fin['roi']:.0f}%")

    # ── Salvar JSON ─────────────────────────────────────────────────────────
    # Local
    local_path = LOCAL_DATA_DIR / "audit_data.json"
    local_path.parent.mkdir(exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    print(f"\n  Exportado: {local_path}")

    # kira-data (se existir)
    if KIRA_DATA_DIR.exists():
        kira_path = KIRA_DATA_DIR / "audit_data.json"
        with open(kira_path, "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2, ensure_ascii=False)
        print(f"  Exportado: {kira_path}")
    else:
        print(f"\n  ⚠ kira-data não encontrado em {KIRA_DATA_DIR}")
        print("    Copie data/audit_data.json manualmente"
              " para kira-data/src/data/")

    # ── Também exporta CSV diário completo ──────────────────────────────────
    export_cols = [
        "dia", "mes", "tipo", "dow", "has_ponta",
        "cons_hp_total", "cons_hp_residual", "cons_fp_total", "cons_fp_net",
        "dem_hp_max", "dem_fp_max", "dem_hp_resid",
        "solar_saving", "bess_charge_kwh", "bess_dead",
    ]
    df_days[export_cols].to_csv(
        LOCAL_DATA_DIR / "bess_simulacao_diaria.csv",
        index=False, float_format="%.2f")
    print(f"  Exportado: data/bess_simulacao_diaria.csv ({len(df_days)} dias)")

    print(f"\n{'='*70}")
    print("  ✅ JSON pronto para consumo pelo kira-data frontend")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
