"""
Cálculo heurístico de fatura – Modalidade Tarifária **AZUL**.
=============================================================

Modalidade AZUL: o consumidor contrata duas demandas separadas:
**Ponta (HP)** e **Fora Ponta (FP)**. Cada uma é faturada com
sua respectiva tarifa de demanda (R$/kW) e TUSD de energia (R$/MWh).

Heurística do Split Tributário
------------------------------
A demanda **faturada** = max(contratada, medida). Existe um split
automático de tributação baseado no que foi efetivamente usado:

+--------------------------+-------------------------------------+
| Parcela                  | Tributação                          |
+==========================+=====================================+
| Demanda MEDIDA (usada)   | Tributada (ICMS + PIS + COFINS)     |
+--------------------------+-------------------------------------+
| Demanda NÃO USADA        | Isenta ICMS (só PIS + COFINS)       |
| (contratada − medida)    |                                     |
+--------------------------+-------------------------------------+
| TUSD Energia (HP e FP)   | Sempre Tributada                    |
+--------------------------+-------------------------------------+

Benefício (BEN) — Ajuste Tributário:
  O benefício tarifário de fonte incentivada (50% demanda) gera um
  desconto líquido + compensação dos impostos sobre as linhas de demanda.

  Ben_Líquido = soma dos descontos (50%) sobre bases de demanda
  Ben_Bruto = Ben_Líquido + impostos gerados nas linhas de demanda

Blocos da Fatura
----------------
BLOCO 1 – Distribuidora (TUSD)
  Total_Distribuidora = Σ Itens(gross-up) + Encargos + Ben_Bruto − Ben_Líquido

BLOCO 2 – Comercializadora (TE)
  Total_Comercializadora = Consumo_Total_kWh × TE / (1 − ICMS)

BLOCO 3 – Custo Global
  Custo = Distribuidora + Comercializadora
"""

from __future__ import annotations

from .premissas import (
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


def calcular_fatura_azul(
    demanda_hp_contratada_kw: float,
    demanda_fp_contratada_kw: float,
    demanda_hp_medida_kw: float,
    demanda_fp_medida_kw: float,
    consumo_hp_kwh: float,
    consumo_fp_kwh: float,
    encargos: float = 0.0,
) -> dict:
    """
    Calcula a fatura de energia na modalidade tarifária **AZUL**.

    O split tributário é feito automaticamente:
      - Demanda efetivamente usada (medida) → tributada (ICMS + PIS/COFINS)
      - Demanda contratada mas não usada    → isenta ICMS (só PIS/COFINS)

    Parâmetros
    ----------
    demanda_hp_contratada_kw : float
        Demanda contratada Ponta (kW).
    demanda_fp_contratada_kw : float
        Demanda contratada Fora Ponta (kW).
    demanda_hp_medida_kw : float
        Demanda medida Ponta (kW).
    demanda_fp_medida_kw : float
        Demanda medida Fora Ponta (kW).
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
    # ── 0. Split automático: tributada (medida) vs isenta (não usada) ────────────
    dem_hp_faturada = max(demanda_hp_contratada_kw, demanda_hp_medida_kw)
    dem_fp_faturada = max(demanda_fp_contratada_kw, demanda_fp_medida_kw)

    dem_hp_tributada = demanda_hp_medida_kw
    dem_hp_isenta = dem_hp_faturada - dem_hp_tributada  # ≥ 0

    dem_fp_tributada = demanda_fp_medida_kw
    dem_fp_isenta = dem_fp_faturada - dem_fp_tributada  # ≥ 0

    # ── 1. Bases (sem imposto) ──────────────────────────────────────────────────
    # Desconto de fonte incentivada (50%) aplica-se à DEMANDA
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA
    base_dem_hp_trib = dem_hp_tributada * AZUL_DEMANDA_HP * fator_dem
    base_dem_hp_isenta = dem_hp_isenta * AZUL_DEMANDA_HP * fator_dem
    base_dem_fp_trib = dem_fp_tributada * AZUL_DEMANDA_FP * fator_dem
    base_dem_fp_isenta = dem_fp_isenta * AZUL_DEMANDA_FP * fator_dem

    # Desconto em R$ para compor o BEN
    desconto_dem_hp_trib = dem_hp_tributada * \
        AZUL_DEMANDA_HP * DESCONTO_FONTE_INCENTIVADA
    desconto_dem_hp_isenta = dem_hp_isenta * \
        AZUL_DEMANDA_HP * DESCONTO_FONTE_INCENTIVADA
    desconto_dem_fp_trib = dem_fp_tributada * \
        AZUL_DEMANDA_FP * DESCONTO_FONTE_INCENTIVADA
    desconto_dem_fp_isenta = dem_fp_isenta * \
        AZUL_DEMANDA_FP * DESCONTO_FONTE_INCENTIVADA
    desconto_fonte_total = (
        desconto_dem_hp_trib + desconto_dem_hp_isenta
        + desconto_dem_fp_trib + desconto_dem_fp_isenta
    )

    consumo_hp_mwh = consumo_hp_kwh / 1_000
    consumo_fp_mwh = consumo_fp_kwh / 1_000
    base_tusd_hp = consumo_hp_mwh * AZUL_TUSD_HP
    base_tusd_fp = consumo_fp_mwh * AZUL_TUSD_FP

    # ── 2. Gross-up (imposto embutido) ──────────────────────────────────────────
    valor_dem_hp_trib = base_dem_hp_trib / FATOR_TRIBUTADO
    valor_dem_hp_isenta = base_dem_hp_isenta / FATOR_ISENTO_ICMS
    valor_dem_fp_trib = base_dem_fp_trib / FATOR_TRIBUTADO
    valor_dem_fp_isenta = base_dem_fp_isenta / FATOR_ISENTO_ICMS

    valor_tusd_hp = base_tusd_hp / FATOR_TRIBUTADO      # energia sempre tributada
    valor_tusd_fp = base_tusd_fp / FATOR_TRIBUTADO

    soma_itens = (
        valor_dem_hp_trib + valor_dem_hp_isenta
        + valor_dem_fp_trib + valor_dem_fp_isenta
        + valor_tusd_hp + valor_tusd_fp
    )

    # ── 3. Benefício – Ajuste Tributário ────────────────────────────────────────
    base_demanda_total = (
        base_dem_hp_trib + base_dem_hp_isenta
        + base_dem_fp_trib + base_dem_fp_isenta
    )
    valor_demanda_total = (
        valor_dem_hp_trib + valor_dem_hp_isenta
        + valor_dem_fp_trib + valor_dem_fp_isenta
    )
    ben_liquido = desconto_fonte_total
    impostos_ben = valor_demanda_total - base_demanda_total
    ben_bruto = ben_liquido + impostos_ben

    # ── 4. Total Distribuidora ──────────────────────────────────────────────────
    total_distribuidora = soma_itens + encargos + ben_bruto - ben_liquido

    # ── BLOCO 2: Comercializadora (TE) — só ICMS (sem PIS/COFINS) ────────────────
    total_consumo_kwh = consumo_hp_kwh + consumo_fp_kwh
    base_comercializadora = total_consumo_kwh * TE_COMERCIALIZADORA
    total_comercializadora = base_comercializadora / FATOR_COMERCIALIZADORA

    # ── BLOCO 3: Custo Global ───────────────────────────────────────────────────
    custo_total = total_distribuidora + total_comercializadora

    return {
        # Demandas faturadas (kW)
        "dem_hp_faturada": round(dem_hp_faturada, 2),
        "dem_fp_faturada": round(dem_fp_faturada, 2),
        "dem_hp_tributada": round(dem_hp_tributada, 2),
        "dem_hp_isenta": round(dem_hp_isenta, 2),
        "dem_fp_tributada": round(dem_fp_tributada, 2),
        "dem_fp_isenta": round(dem_fp_isenta, 2),
        # Bases demanda (sem imposto, já com desconto fonte 50%)
        "base_dem_hp_trib": round(base_dem_hp_trib, 2),
        "base_dem_hp_isenta": round(base_dem_hp_isenta, 2),
        "base_dem_fp_trib": round(base_dem_fp_trib, 2),
        "base_dem_fp_isenta": round(base_dem_fp_isenta, 2),
        # Bases energia (sem imposto, sem desconto)
        "base_tusd_hp": round(base_tusd_hp, 2),
        "base_tusd_fp": round(base_tusd_fp, 2),
        # Com imposto (gross-up)
        "valor_dem_hp_trib": round(valor_dem_hp_trib, 2),
        "valor_dem_hp_isenta": round(valor_dem_hp_isenta, 2),
        "valor_dem_fp_trib": round(valor_dem_fp_trib, 2),
        "valor_dem_fp_isenta": round(valor_dem_fp_isenta, 2),
        "valor_tusd_hp": round(valor_tusd_hp, 2),
        "valor_tusd_fp": round(valor_tusd_fp, 2),
        "soma_itens": round(soma_itens, 2),
        # Benefício
        "desconto_fonte_total": round(desconto_fonte_total, 2),
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
