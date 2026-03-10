"""Simulação da fatura VERDE com dados reais da conta — resultado por componente."""

from fatura import calcular_fatura_verde
from fatura.premissas import (
    VERDE_DEMANDA_UNICA,
    VERDE_TUSD_HP, VERDE_TUSD_FP,
    TE_COMERCIALIZADORA,
    DESCONTO_FONTE_INCENTIVADA,
    FATOR_TRIBUTADO, FATOR_ISENTO_ICMS,
    ICMS, PIS, COFINS,
)

# Mesmos dados de consumo; demanda VERDE usa contratada FP única
r = calcular_fatura_verde(
    demanda_contratada_kw=3_280.00,
    demanda_medida_kw=2_902.31,
    consumo_hp_kwh=115_251.52,
    consumo_fp_kwh=1_206_468.05,
)

SEP = "─" * 72

print()
print("=" * 72)
print("   FATURA VERDE — SIMULAÇÃO HEURÍSTICA POR COMPONENTE")
print("=" * 72)

# ────────────────────────────────────────────────────────────────────────
# BLOCO 1: DISTRIBUIDORA
# ────────────────────────────────────────────────────────────────────────
print(f"\n  {'DISTRIBUIDORA (TUSD)':─^70}")

print(f"\n  {'Componente':<36s}  {'Base':>12s}  {'Imposto':>12s}  {'Total':>12s}")
print(f"  {SEP}")

tarifa_dem_desc = VERDE_DEMANDA_UNICA * (1 - DESCONTO_FONTE_INCENTIVADA)

componentes = [
    ("Dem. Distrib. F.Ponta",
     f"{r['dem_tributada']:,.2f} kW × {tarifa_dem_desc:.2f} R$/kW (desc. 50%)",
     r["base_dem_trib"], r["valor_dem_trib"]),
    ("Dem. Distrib. FP Isenta ICMS",
     f"{r['dem_isenta']:,.2f} kW × {tarifa_dem_desc:.2f} R$/kW (desc. 50%)",
     r["base_dem_isenta"], r["valor_dem_isenta"]),
    ("TUSD Energia Fora Ponta",
     f"{1_206_468.05/1000:,.2f} MWh × {VERDE_TUSD_FP:.2f} R$/MWh",
     r["base_tusd_fp"], r["valor_tusd_fp"]),
    ("TUSD Energia Ponta",
     f"{115_251.52/1000:,.2f} MWh × {r['tarifa_hp_efetiva']:,.2f} R$/MWh (FP + 50% dif.)",
     r["base_tusd_hp"], r["valor_tusd_hp"]),
]

for nome, detalhe, base, total in componentes:
    imp = total - base
    print(f"  {nome:<36s}  {base:>12,.2f}  {imp:>12,.2f}  {total:>12,.2f}")
    print(f"    ({detalhe})")

print(f"  {SEP}")
soma_base = sum(c[2] for c in componentes)
soma_total = sum(c[3] for c in componentes)
soma_imp = soma_total - soma_base
print(f"  {'Subtotal Itens':<36s}  {soma_base:>12,.2f}  {soma_imp:>12,.2f}  {soma_total:>12,.2f}")

# BEN
print(
    f"\n  {'Desconto Fonte Incent. (demanda)':<36s}  {r['desconto_fonte_total']:>12,.2f}")
print(f"  {'Desconto diferencial HP':<36s}  {r['desconto_hp']:>12,.2f}")
print(
    f"  {'BEN líquido (desc.fonte + desc.hp)':<36s}  {r['ben_liquido']:>12,.2f}")
print(f"  {'Impostos sobre BEN':<36s}  {r['impostos_ben']:>12,.2f}")
print(f"  {'BEN bruto':<36s}  {r['ben_bruto']:>12,.2f}")
print(
    f"  {'Ajuste BEN (bruto − líquido)':<36s}  {'':<12s}  {'':<12s}  {r['ben_bruto'] - r['ben_liquido']:>12,.2f}")

print(
    f"\n  {'Encargos setoriais':<36s}  {'':<12s}  {'':<12s}  {r['encargos']:>12,.2f}")

print(f"  {SEP}")
print(
    f"  {'TOTAL DISTRIBUIDORA':<36s}  {'':<12s}  {'':<12s}  {r['total_distribuidora']:>12,.2f}")

# ────────────────────────────────────────────────────────────────────────
# BLOCO 2: COMERCIALIZADORA
# ────────────────────────────────────────────────────────────────────────
print(f"\n  {'COMERCIALIZADORA (TE)':─^70}")

imp_c = r["total_comercializadora"] - r["base_comercializadora"]
print(f"\n  {'Componente':<36s}  {'Base':>12s}  {'Imposto':>12s}  {'Total':>12s}")
print(f"  {SEP}")
print(
    f"  {'Energia Comercializad.':<36s}  {r['base_comercializadora']:>12,.2f}  {imp_c:>12,.2f}  {r['total_comercializadora']:>12,.2f}")
print(f"    ({r['total_consumo_kwh']:,.2f} kWh × {TE_COMERCIALIZADORA} R$/kWh)")
print(f"  {SEP}")
print(
    f"  {'TOTAL COMERCIALIZADORA':<36s}  {'':<12s}  {'':<12s}  {r['total_comercializadora']:>12,.2f}")

# ────────────────────────────────────────────────────────────────────────
# TOTAL
# ────────────────────────────────────────────────────────────────────────
print(f"\n{'=' * 72}")
print(
    f"  {'CUSTO TOTAL DA FATURA':<36s}  {'':<12s}  {'':<12s}  {r['custo_total']:>12,.2f}")
print(f"{'=' * 72}")

print(f"\n  Premissas:")
print(
    f"    ICMS = {ICMS*100:.2f}%  |  PIS = {PIS*100:.4f}%  |  COFINS = {COFINS*100:.4f}%")
print(
    f"    Desc. Fonte Incentivada = {DESCONTO_FONTE_INCENTIVADA*100:.0f}% (sobre demanda)")
print(
    f"    Fator Tributado = {FATOR_TRIBUTADO:.6f}  |  Fator Isento ICMS = {FATOR_ISENTO_ICMS:.6f}")
print(f"    TE Comercializadora = {TE_COMERCIALIZADORA} R$/kWh")
print(
    f"    Tarifa HP efetiva = FP + 50%×(HP−FP) = {r['tarifa_hp_efetiva']:,.2f} R$/MWh")
