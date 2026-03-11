"""
Cálculo heurístico de fatura – Modalidade Tarifária **VERDE**.
==============================================================

Modalidade VERDE: o consumidor contrata uma **demanda única** (Fora Ponta),
mas o consumo no Horário de Ponta (HP) é penalizado por uma TUSD de
energia significativamente mais cara (R$ 2.296,63/MWh vs R$ 140,21/MWh).

Diferença fundamental AZUL vs VERDE
------------------------------------
No AZUL, a ponta é cara na **demanda** (R$ 88,82/kW vs R$ 32,50/kW).
No VERDE, a ponta é cara na **energia** (TUSD HP 16× maior que TUSD FP).

Isso faz o VERDE ideal para quem consegue **reduzir o consumo HP**
(ex: com BESS), mas mantém demanda alta no FP.

Mecânica do Desconto HP (Fonte Incentivada)
-------------------------------------------
O VERDE aplica um desconto de 50% sobre o **diferencial** entre
TUSD HP e TUSD FP no consumo de ponta::

    tarifa_hp_efetiva = TUSD_FP + (TUSD_HP − TUSD_FP) × 0.5
                     = 140.21 + (2296.63 − 140.21) × 0.5
                     = 140.21 + 1078.21
                     = R$ 1.218,42/MWh

Esse desconto aparece no BEN (Benefício de ajuste tributário) como::

    desconto_hp = Consumo_HP_MWh × (TUSD_HP − TUSD_FP) × 0.5

Blocos da Fatura
----------------
BLOCO 1 – Distribuidora (TUSD)
  A demanda faturada = max(contratada, medida) — demanda única FP.
  O split tributário é automático (mesma lógica do AZUL):
    - Medida → Tributada (ICMS + PIS/COFINS)
    - Não usada (contrat − medida) → Isenta ICMS (só PIS/COFINS)
    - TUSD Energia (HP e FP) → sempre Tributada

  Total_Distribuidora = Σ_itens + Encargos + Ben_Bruto − Ben_Líquido

BLOCO 2 – Comercializadora (TE)
  Total_Comercializadora = (Consumo_HP + Consumo_FP) × TE / (1 − ICMS)

BLOCO 3 – Custo Global
  Custo = Distribuidora + Comercializadora
"""

from __future__ import annotations

from .premissas import (
    DESCONTO_FONTE_INCENTIVADA,
    FATOR_COMERCIALIZADORA,
    FATOR_ISENTO_ICMS,
    FATOR_TRIBUTADO,
    TE_COMERCIALIZADORA,
    VERDE_DEMANDA_UNICA,
    VERDE_TUSD_FP,
    VERDE_TUSD_HP,
)


def calcular_fatura_verde(
    demanda_contratada_kw: float,
    demanda_medida_kw: float,
    consumo_hp_kwh: float,
    consumo_fp_kwh: float,
    encargos: float = 0.0,
) -> dict:
    """
    Calcula a fatura de energia na modalidade tarifária **VERDE**.

    O split tributário é feito automaticamente:
      - Demanda efetivamente usada (medida) → tributada (ICMS + PIS/COFINS)
      - Demanda contratada mas não usada    → isenta ICMS (só PIS/COFINS)

    Parâmetros
    ----------
    demanda_contratada_kw : float
        Demanda contratada única — Fora Ponta (kW).
    demanda_medida_kw : float
        Demanda medida única (kW).
    consumo_hp_kwh : float
        Consumo Horário Ponta (kWh).
    consumo_fp_kwh : float
        Consumo Horário Fora Ponta (kWh).
    encargos : float
        Encargos setoriais (R$), default 0.

    Retorna
    -------
    dict
        Dicionário com todos os componentes da fatura.
    """
    # ── 0. Split automático: tributada / isenta / ultrapassagem ─────────────────
    dem_faturada = max(demanda_contratada_kw, demanda_medida_kw)

    # Ultrapassagem: excedente acima da contratada → cobrado 2× tarifa cheia
    dem_ultrapassagem = max(0.0, demanda_medida_kw - demanda_contratada_kw)

    # Tributada = parcela medida dentro da contratada (incide ICMS)
    dem_tributada = min(demanda_medida_kw, demanda_contratada_kw)
    dem_isenta = demanda_contratada_kw - dem_tributada  # não usada → sem ICMS

    # ── 1. Bases demanda (sem imposto, com desconto fonte 50%) ──────────────
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    base_dem_trib = dem_tributada * VERDE_DEMANDA_UNICA * fator_dem
    base_dem_isenta = dem_isenta * VERDE_DEMANDA_UNICA * fator_dem

    # Ultrapassagem: 2× tarifa cheia, sem desconto fonte
    base_dem_ultra = dem_ultrapassagem * VERDE_DEMANDA_UNICA * 2

    desconto_dem_trib = dem_tributada * \
        VERDE_DEMANDA_UNICA * DESCONTO_FONTE_INCENTIVADA
    desconto_dem_isenta = dem_isenta * VERDE_DEMANDA_UNICA * DESCONTO_FONTE_INCENTIVADA
    desconto_fonte_total = desconto_dem_trib + desconto_dem_isenta

    consumo_hp_mwh = consumo_hp_kwh / 1_000
    consumo_fp_mwh = consumo_fp_kwh / 1_000

    # TUSD Energia sem desconto
    base_tusd_fp = consumo_fp_mwh * VERDE_TUSD_FP

    # HP cobra a tarifa FP + 50% do diferencial (HP − FP)
    tarifa_hp_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    base_tusd_hp = consumo_hp_mwh * tarifa_hp_efetiva

    # ── 2. Gross-up ─────────────────────────────────────────────────────────────
    valor_dem_trib = base_dem_trib / FATOR_TRIBUTADO
    valor_dem_isenta = base_dem_isenta / FATOR_ISENTO_ICMS
    valor_dem_ultra = base_dem_ultra / FATOR_TRIBUTADO

    valor_tusd_fp = base_tusd_fp / FATOR_TRIBUTADO       # energia sempre tributada
    valor_tusd_hp = base_tusd_hp / FATOR_TRIBUTADO

    # ── 3. Benefício – Ajuste Tributário ────────────────────────────────────────
    # Desconto diferencial HP para o BEN (mecânica do verde)
    desconto_hp = consumo_hp_mwh * (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5

    base_demanda_total = base_dem_trib + base_dem_isenta
    valor_demanda_total = valor_dem_trib + valor_dem_isenta

    ben_liquido = desconto_fonte_total + desconto_hp
    impostos_demanda = valor_demanda_total - base_demanda_total
    impostos_tusd_hp = valor_tusd_hp - base_tusd_hp
    impostos_ben = impostos_demanda + impostos_tusd_hp
    ben_bruto = ben_liquido + impostos_ben

    # ── 4. Total Distribuidora ──────────────────────────────────────────────────
    total_distribuidora = (
        valor_dem_trib + valor_dem_isenta + valor_dem_ultra
        + valor_tusd_fp + valor_tusd_hp
        + encargos
        + ben_bruto - ben_liquido
    )

    # ── BLOCO 2: Comercializadora (TE) — só ICMS (sem PIS/COFINS) ────────────────
    total_consumo_kwh = consumo_hp_kwh + consumo_fp_kwh
    base_comercializadora = total_consumo_kwh * TE_COMERCIALIZADORA
    total_comercializadora = base_comercializadora / FATOR_COMERCIALIZADORA

    # ── BLOCO 3: Custo Global ───────────────────────────────────────────────────
    custo_total = total_distribuidora + total_comercializadora

    return {
        # Demandas faturadas (kW)
        "dem_faturada": round(dem_faturada, 2),
        "dem_tributada": round(dem_tributada, 2),
        "dem_isenta": round(dem_isenta, 2),
        "dem_ultrapassagem": round(dem_ultrapassagem, 2),
        # Bases demanda (sem imposto, já com desconto fonte 50%)
        "base_dem_trib": round(base_dem_trib, 2),
        "base_dem_isenta": round(base_dem_isenta, 2),
        "base_dem_ultra": round(base_dem_ultra, 2),
        # Bases energia (sem imposto, sem desconto)
        "base_tusd_fp": round(base_tusd_fp, 2),
        "base_tusd_hp": round(base_tusd_hp, 2),
        "tarifa_hp_efetiva": round(tarifa_hp_efetiva, 2),
        "desconto_hp": round(desconto_hp, 2),
        "desconto_fonte_total": round(desconto_fonte_total, 2),
        # Com imposto (gross-up)
        "valor_dem_trib": round(valor_dem_trib, 2),
        "valor_dem_isenta": round(valor_dem_isenta, 2),
        "valor_dem_ultra": round(valor_dem_ultra, 2),
        "valor_tusd_fp": round(valor_tusd_fp, 2),
        "valor_tusd_hp": round(valor_tusd_hp, 2),
        # Benefício
        "ben_liquido": round(ben_liquido, 2),
        "ben_bruto": round(ben_bruto, 2),
        "impostos_ben": round(impostos_ben, 2),
        # Encargos
        "encargos": round(encargos, 2),
        # Distribuidora
        "total_distribuidora": round(total_distribuidora, 2),
        # Comercializadora
        "total_consumo_kwh": round(total_consumo_kwh, 2),
        "base_comercializadora": round(base_comercializadora, 2),
        "total_comercializadora": round(total_comercializadora, 2),
        # Total
        "custo_total": round(custo_total, 2),
    }
