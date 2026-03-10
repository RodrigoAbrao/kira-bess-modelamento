"""Simulação rápida AZUL vs VERDE com dados fornecidos."""
from fatura import calcular_fatura_azul, calcular_fatura_verde

# Dados de entrada
# Demanda contratada = medida (tudo tributada, isenta = 0)
dem_hp = 2_980.0       # kW
dem_fp = 3_280.0       # kW
cons_hp = 115_000.0    # kWh  (115 MWh)
cons_fp = 1_260_000.0  # kWh  (1260 MWh)

SEP = "─" * 72

# ── AZUL ────────────────────────────────────────────────────────────────────────
a = calcular_fatura_azul(dem_hp, dem_fp, dem_hp, dem_fp, cons_hp, cons_fp)

print()
print("=" * 72)
print("   CENÁRIO 1: TARIFA AZUL")
print("=" * 72)
print(f"\n  {'Componente':<34s}  {'Base':>12s}  {'c/ Tributos':>12s}")
print(f"  {SEP}")
for nome, bk, vk in [
    ("Dem. Ponta (tributada)",     "base_dem_hp_trib",   "valor_dem_hp_trib"),
    ("Dem. Ponta (isenta ICMS)",   "base_dem_hp_isenta", "valor_dem_hp_isenta"),
    ("Dem. F.Ponta (tributada)",   "base_dem_fp_trib",   "valor_dem_fp_trib"),
    ("Dem. F.Ponta (isenta ICMS)", "base_dem_fp_isenta", "valor_dem_fp_isenta"),
    ("TUSD Energia HP",            "base_tusd_hp",       "valor_tusd_hp"),
    ("TUSD Energia FP",            "base_tusd_fp",       "valor_tusd_fp"),
]:
    print(f"  {nome:<34s}  {a[bk]:>12,.2f}  {a[vk]:>12,.2f}")

print(f"  {SEP}")
print(f"  {'Σ Itens':<34s}  {'':<12s}  {a['soma_itens']:>12,.2f}")
print(
    f"  {'Desc. Fonte (BEN Líquido)':<34s}  {a['desconto_fonte_total']:>12,.2f}  {-a['ben_liquido']:>+12,.2f}")
print(f"  {'BEN Bruto':<34s}  {'':<12s}  {a['ben_bruto']:>+12,.2f}")
print(
    f"  {'Ajuste BEN (bruto−líquido)':<34s}  {'':<12s}  {a['impostos_ben']:>12,.2f}")
print(f"  {SEP}")
print(
    f"  {'DISTRIBUIDORA':<34s}  {'':<12s}  {a['total_distribuidora']:>12,.2f}")
print(
    f"  {'COMERCIALIZADORA':<34s}  {a['base_comercializadora']:>12,.2f}  {a['total_comercializadora']:>12,.2f}")
print(f"  {SEP}")
print(f"  {'CUSTO TOTAL AZUL':<34s}  {'':<12s}  {a['custo_total']:>12,.2f}")

# ── VERDE ───────────────────────────────────────────────────────────────────────
v = calcular_fatura_verde(dem_fp, dem_fp, cons_hp, cons_fp)

print()
print("=" * 72)
print("   CENÁRIO 2: TARIFA VERDE")
print("=" * 72)
print(f"\n  {'Componente':<34s}  {'Base':>12s}  {'c/ Tributos':>12s}")
print(f"  {SEP}")
for nome, bk, vk in [
    ("Dem. Única (tributada)",     "base_dem_trib",   "valor_dem_trib"),
    ("Dem. Única (isenta ICMS)",   "base_dem_isenta", "valor_dem_isenta"),
    ("TUSD Energia FP",            "base_tusd_fp",    "valor_tusd_fp"),
    ("TUSD Energia HP",            "base_tusd_hp",    "valor_tusd_hp"),
]:
    print(f"  {nome:<34s}  {v[bk]:>12,.2f}  {v[vk]:>12,.2f}")

print(f"  {SEP}")
soma_itens_v = v["valor_dem_trib"] + v["valor_dem_isenta"] + \
    v["valor_tusd_fp"] + v["valor_tusd_hp"]
print(f"  {'Σ Itens':<34s}  {'':<12s}  {soma_itens_v:>12,.2f}")
print(
    f"  {'Desc. Fonte + Desc. HP (BEN Líq.)':<34s}  {v['ben_liquido']:>12,.2f}  {-v['ben_liquido']:>+12,.2f}")
print(
    f"  {'  └ Desc. fonte (demanda)':<34s}  {v['desconto_fonte_total']:>12,.2f}")
print(f"  {'  └ Desc. diferencial HP':<34s}  {v['desconto_hp']:>12,.2f}")
print(f"  {'BEN Bruto':<34s}  {'':<12s}  {v['ben_bruto']:>+12,.2f}")
print(
    f"  {'Ajuste BEN (bruto−líquido)':<34s}  {'':<12s}  {v['impostos_ben']:>12,.2f}")
print(f"  {SEP}")
print(
    f"  {'DISTRIBUIDORA':<34s}  {'':<12s}  {v['total_distribuidora']:>12,.2f}")
print(
    f"  {'COMERCIALIZADORA':<34s}  {v['base_comercializadora']:>12,.2f}  {v['total_comercializadora']:>12,.2f}")
print(f"  {SEP}")
print(f"  {'CUSTO TOTAL VERDE':<34s}  {'':<12s}  {v['custo_total']:>12,.2f}")

# ── COMPARATIVO ─────────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("   COMPARATIVO")
print("=" * 72)
print(f"  {'':34s}  {'AZUL':>12s}  {'VERDE':>12s}  {'Diff':>12s}")
print(f"  {SEP}")
for label, ka, kv in [
    ("Distribuidora", "total_distribuidora", "total_distribuidora"),
    ("Comercializadora", "total_comercializadora", "total_comercializadora"),
    ("CUSTO TOTAL", "custo_total", "custo_total"),
]:
    d = a[ka] - v[kv]
    print(f"  {label:<34s}  {a[ka]:>12,.2f}  {v[kv]:>12,.2f}  {d:>+12,.2f}")

diff = a["custo_total"] - v["custo_total"]
melhor = "AZUL" if diff < 0 else "VERDE"
print(f"\n  → {melhor} é R$ {abs(diff):,.2f} mais barata.")
