"""Decomposição da fatura nos componentes da planilha do usuário.

Componentes: Demanda HP, Demanda HFP, Encargos HP, Encargos HFP,
             Energia HP, Energia HFP, Bandeira, PIS/COFINS, ICMS.

O total = Σ bases + PIS/COFINS + ICMS deve bater com calcular_fatura_*.
"""
from fatura import calcular_fatura_azul, calcular_fatura_verde
from fatura.premissas import (
    AZUL_DEMANDA_HP, AZUL_DEMANDA_FP, AZUL_TUSD_HP, AZUL_TUSD_FP,
    VERDE_DEMANDA_UNICA, VERDE_TUSD_HP, VERDE_TUSD_FP,
    TE_COMERCIALIZADORA, DESCONTO_FONTE_INCENTIVADA,
    ICMS, PIS_COFINS, FATOR_TRIBUTADO, FATOR_ISENTO_ICMS,
    FATOR_COMERCIALIZADORA,
)

# ── Dados de entrada ────────────────────────────────────────────────────────────
dem_hp = 2_980.0       # kW
dem_fp = 3_280.0       # kW
cons_hp_kwh = 115_000.0
cons_fp_kwh = 1_260_000.0
cons_hp_mwh = cons_hp_kwh / 1_000
cons_fp_mwh = cons_fp_kwh / 1_000


# ── Funções auxiliares para decompor impostos ───────────────────────────────────
def _icms_trib(base):
    """ICMS = (base / FATOR_TRIBUTADO) × ICMS."""
    return (base / FATOR_TRIBUTADO) * ICMS


def _icms_comer(base):
    """ICMS sobre comercializadora (só ICMS, sem PIS/COFINS)."""
    return (base / FATOR_COMERCIALIZADORA) * ICMS


def _piscofins(base):
    """PIS/COFINS = base × PIS_COFINS / (1 − PIS_COFINS)."""
    return base * PIS_COFINS / (1 - PIS_COFINS)


# ═════════════════════════════════════════════════════════════════════════════════
#  AZUL
# ═════════════════════════════════════════════════════════════════════════════════
def calcular_componentes_azul():
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA  # 0.5

    # ── Bases dos itens visíveis (sem imposto, com desconto 50% na demanda) ────
    #    dem_medida = dem_contratada → toda tributada, isenta = 0
    base_dem_hp = dem_hp * AZUL_DEMANDA_HP * fator_dem
    base_dem_fp = dem_fp * AZUL_DEMANDA_FP * fator_dem
    base_tusd_hp = cons_hp_mwh * AZUL_TUSD_HP
    base_tusd_fp = cons_fp_mwh * AZUL_TUSD_FP
    base_te_hp = cons_hp_kwh * TE_COMERCIALIZADORA
    base_te_fp = cons_fp_kwh * TE_COMERCIALIZADORA

    # ── BEN (Benefício Tarifário) ──────────────────────────────────────────────
    # No AZUL: impostos_ben = taxes on the 4 demand bases.
    # Como desconto = base (50%/50%), taxar o "desconto" é idêntico a taxar a "base" novamente.
    # Portanto as bases tributáveis para impostos = itens + demandas em dobro.
    bases_trib_distrib = [base_dem_hp, base_dem_fp, base_tusd_hp, base_tusd_fp]
    bases_comer = [base_te_hp, base_te_fp]
    # impostos_ben = taxes on demand
    bases_trib_ben = [base_dem_hp, base_dem_fp]

    total_icms = (sum(_icms_trib(b) for b in bases_trib_distrib + bases_trib_ben)
                  + sum(_icms_comer(b) for b in bases_comer))
    total_piscofins = sum(_piscofins(b)
                          for b in bases_trib_distrib + bases_trib_ben)
    # Comercializadora (TE) não tem PIS/COFINS

    return {
        "Demanda HP":   base_dem_hp,
        "Demanda HFP":  base_dem_fp,
        "Encargos HP":  base_tusd_hp,
        "Encargos HFP": base_tusd_fp,
        "Energia HP":   base_te_hp,
        "Energia HFP":  base_te_fp,
        "Bandeira":     0.0,
        "PIS/COFINS":   total_piscofins,
        "ICMS":         total_icms,
    }


# ═════════════════════════════════════════════════════════════════════════════════
#  VERDE
# ═════════════════════════════════════════════════════════════════════════════════
def calcular_componentes_verde():
    fator_dem = 1 - DESCONTO_FONTE_INCENTIVADA

    # ── Bases dos itens visíveis ───────────────────────────────────────────────
    base_dem = dem_fp * VERDE_DEMANDA_UNICA * fator_dem
    base_tusd_fp = cons_fp_mwh * VERDE_TUSD_FP
    tarifa_hp_efe = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    base_tusd_hp = cons_hp_mwh * tarifa_hp_efe
    base_te_hp = cons_hp_kwh * TE_COMERCIALIZADORA
    base_te_fp = cons_fp_kwh * TE_COMERCIALIZADORA

    # ── BEN no VERDE ───────────────────────────────────────────────────────────
    # impostos_ben = impostos_demanda(taxes on base_dem) + impostos_tusd_hp(taxes on base_tusd_hp)
    # Portanto bases tributáveis = itens + demanda novamente + TUSD HP novamente
    bases_trib_distrib = [base_dem, base_tusd_fp, base_tusd_hp]
    bases_comer = [base_te_hp, base_te_fp]
    # impostos_ben = taxes on dem + tusd_hp
    bases_trib_ben = [base_dem, base_tusd_hp]

    total_icms = (sum(_icms_trib(b) for b in bases_trib_distrib + bases_trib_ben)
                  + sum(_icms_comer(b) for b in bases_comer))
    total_piscofins = sum(_piscofins(b)
                          for b in bases_trib_distrib + bases_trib_ben)
    # Comercializadora (TE) não tem PIS/COFINS

    return {
        "Demanda HP":   0.0,  # VERDE não tem demanda HP
        "Demanda HFP":  base_dem,
        "Encargos HP":  base_tusd_hp,
        "Encargos HFP": base_tusd_fp,
        "Energia HP":   base_te_hp,
        "Energia HFP":  base_te_fp,
        "Bandeira":     0.0,
        "PIS/COFINS":   total_piscofins,
        "ICMS":         total_icms,
    }


# ═════════════════════════════════════════════════════════════════════════════════
#  VALIDAÇÃO + OUTPUT
# ═════════════════════════════════════════════════════════════════════════════════
azul = calcular_componentes_azul()
verde = calcular_componentes_verde()

# Valida contra funções oficiais
res_azul = calcular_fatura_azul(dem_hp, dem_fp, dem_hp, dem_fp,
                                cons_hp_kwh, cons_fp_kwh)
res_verde = calcular_fatura_verde(dem_fp, dem_fp, cons_hp_kwh, cons_fp_kwh)

SEP = "─" * 56

print()
print("=" * 56)
print("   DECOMPOSIÇÃO POR COMPONENTE")
print("=" * 56)
print(f"\n  {'Componente':<20s}  {'AZUL':>14s}  {'VERDE':>14s}")
print(f"  {SEP}")
for k in ["Demanda HP", "Demanda HFP", "Encargos HP", "Encargos HFP",
          "Energia HP", "Energia HFP", "Bandeira", "PIS/COFINS", "ICMS"]:
    print(f"  {k:<20s}  {azul[k]:>14,.2f}  {verde[k]:>14,.2f}")

print(f"  {SEP}")
total_azul = sum(azul.values())
total_verde = sum(verde.values())
print(f"  {'TOTAL':<20s}  {total_azul:>14,.2f}  {total_verde:>14,.2f}")
diff = total_azul - total_verde
melhor = "AZUL" if diff < 0 else "VERDE"
print(f"\n  → {melhor} é R$ {abs(diff):,.2f} mais barata.")

# Confere contra total oficial
print(f"\n  Verificação (func oficial):")
print(
    f"    AZUL : decomp={total_azul:,.2f}  func={res_azul['custo_total']:,.2f}  diff={abs(total_azul-res_azul['custo_total']):,.2f}")
print(
    f"    VERDE: decomp={total_verde:,.2f}  func={res_verde['custo_total']:,.2f}  diff={abs(total_verde-res_verde['custo_total']):,.2f}")
