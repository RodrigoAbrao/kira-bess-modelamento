"""
Validação da heurística AZUL contra fatura real.

Recebe as tarifas unitárias e quantidades EXATAS da fatura,
itera o desconto de fonte incentivada entre 48 % e 50 %
e mostra qual valor reproduz o total de R$ 472.508,26.

NOTA: as tarifas de demanda na fatura JÁ têm o desconto aplicado.
"""

from fatura.premissas import FATOR_TRIBUTADO, FATOR_ISENTO_ICMS

# ── Dados da fatura real ────────────────────────────────────────────────────────
dem_hp_trib = 2_527.65     # kW
dem_hp_isenta = 452.35     # kW
dem_fp_trib = 2_902.31     # kW
dem_fp_isenta = 377.69     # kW
dem_hp_total = dem_hp_trib + dem_hp_isenta   # 2980
dem_fp_total = dem_fp_trib + dem_fp_isenta   # 3280

# Tarifas unitárias da fatura (R$/kW — JÁ COM desconto aplicado)
tarifa_dem_hp = 43.665000     # R$/kW
tarifa_dem_fp = 15.860000     # R$/kW

# TUSD energia (R$/kWh — sem desconto)
tarifa_tusd = 0.101360        # R$/kWh  (HP = FP na AZUL)

consumo_hp_kwh = 115_251.52
consumo_fp_kwh = 1_206_468.05

# Outros custos (Reativo + CIP + Ajuste)
reativo = 6.31
cip = 72.98
ajuste_cobranca = 78.73
outros = reativo + cip + ajuste_cobranca  # 158.02

TARGET = 472_508.26

# Valores da fatura para comparação individual
FATURA = {
    "valor_dem_hp_trib":    148_429.73,
    "valor_dem_hp_isenta":   20_586.12,
    "valor_dem_fp_trib":     61_903.81,
    "valor_dem_fp_isenta":    6_243.15,
    "valor_tusd_hp":         15_710.24,
    "valor_tusd_fp":        164_456.88,
    "ben_liquido":          182_142.50,
    "ben_bruto":            237_162.81,
}

print("=" * 80)
print("   VALIDAÇÃO DA HEURÍSTICA AZUL CONTRA FATURA REAL")
print("=" * 80)

# ── 1) Cálculo dos itens (não depende do desconto %) ───────────────────────────
base_dem_hp_trib = dem_hp_trib * tarifa_dem_hp
base_dem_hp_isenta = dem_hp_isenta * tarifa_dem_hp
base_dem_fp_trib = dem_fp_trib * tarifa_dem_fp
base_dem_fp_isenta = dem_fp_isenta * tarifa_dem_fp

base_tusd_hp = consumo_hp_kwh * tarifa_tusd
base_tusd_fp = consumo_fp_kwh * tarifa_tusd

valor_dem_hp_trib = base_dem_hp_trib / FATOR_TRIBUTADO
valor_dem_hp_isenta = base_dem_hp_isenta / FATOR_ISENTO_ICMS
valor_dem_fp_trib = base_dem_fp_trib / FATOR_TRIBUTADO
valor_dem_fp_isenta = base_dem_fp_isenta / FATOR_ISENTO_ICMS
valor_tusd_hp = base_tusd_hp / FATOR_TRIBUTADO
valor_tusd_fp = base_tusd_fp / FATOR_TRIBUTADO

soma_itens = (
    valor_dem_hp_trib + valor_dem_hp_isenta
    + valor_dem_fp_trib + valor_dem_fp_isenta
    + valor_tusd_hp + valor_tusd_fp
)

impostos_dem = (
    (valor_dem_hp_trib - base_dem_hp_trib)
    + (valor_dem_hp_isenta - base_dem_hp_isenta)
    + (valor_dem_fp_trib - base_dem_fp_trib)
    + (valor_dem_fp_isenta - base_dem_fp_isenta)
)

base_dem_total_faturada = dem_hp_total * \
    tarifa_dem_hp + dem_fp_total * tarifa_dem_fp

print(f"\n  {'ITENS DE FATURA (fixos, independem do desconto %)'}")
print(f"  {'─' * 76}")
print(f"  {'Item':<36s}  {'Calculado':>12s}  {'Fatura':>12s}  {'Diff':>10s}")
print(f"  {'─' * 76}")
for nome, calc, fat in [
    ("Dem. Ponta Trib.",     valor_dem_hp_trib,   FATURA["valor_dem_hp_trib"]),
    ("Dem. Pta Isenta ICMS", valor_dem_hp_isenta,
     FATURA["valor_dem_hp_isenta"]),
    ("Dem. FP Trib.",        valor_dem_fp_trib,   FATURA["valor_dem_fp_trib"]),
    ("Dem. FP Isenta ICMS",  valor_dem_fp_isenta,
     FATURA["valor_dem_fp_isenta"]),
    ("TUSD Energia HP",      valor_tusd_hp,       FATURA["valor_tusd_hp"]),
    ("TUSD Energia FP",      valor_tusd_fp,       FATURA["valor_tusd_fp"]),
]:
    diff = calc - fat
    print(f"  {nome:<36s}  {calc:>12,.2f}  {fat:>12,.2f}  {diff:>+10,.2f}")

print(f"  {'─' * 76}")
print(f"  {'Σ Itens (sem reativo)':<36s}  {soma_itens:>12,.2f}")
print(f"  {'Impostos sobre demanda':<36s}  {impostos_dem:>12,.2f}")
print(f"  {'Base dem total (total × tarifa)':<36s}  {base_dem_total_faturada:>12,.2f}")

# ── 2) Iteração sobre o desconto (48 % a 50 %) ─────────────────────────────────
print(f"\n  {'ITERAÇÃO DO DESCONTO DE FONTE INCENTIVADA'}")
print(f"  {'─' * 76}")
print(f"  {'D%':>5s}  {'BEN Líquido':>14s}  {'BEN Bruto':>14s}  {'Ajuste BEN':>12s}"
      f"  {'Total':>14s}  {'Diff':>12s}")
print(f"  {'─' * 76}")

for d_pct_10 in range(480, 501):  # 48.0% a 50.0% em passos de 0.1%
    d = d_pct_10 / 1000

    # BEN líquido = base_dem_total × D/(1−D)
    # (porque tarifa fatura = tarifa_cheia × (1−D), então desconto = tarifa_fatura × D/(1−D) por kW)
    ben_liq = base_dem_total_faturada * d / (1 - d)
    ben_bruto = ben_liq + impostos_dem
    ajuste_ben = ben_bruto - ben_liq   # = impostos_dem (constante!)

    total = soma_itens + ajuste_ben + outros
    diff = total - TARGET
    mark = " ◀─ MATCH" if abs(diff) < 1.0 else ""

    print(f"  {d*100:5.1f}  {ben_liq:>14,.2f}  {ben_bruto:>14,.2f}  {ajuste_ben:>12,.2f}"
          f"  {total:>14,.2f}  {diff:>+12,.2f}{mark}")

# ── 3) Resultado com D = 50 % ──────────────────────────────────────────────────
d_final = 0.50
ben_liq_final = base_dem_total_faturada * d_final / (1 - d_final)
ben_bruto_final = ben_liq_final + impostos_dem
total_final = soma_itens + impostos_dem + outros

print(f"\n{'=' * 80}")
print(f"  RESULTADO FINAL COM DESCONTO = {d_final*100:.0f}%")
print(f"  {'─' * 76}")
print(f"  {'Σ Itens':<36s}  {soma_itens:>12,.2f}")
print(f"  {'Reativo + CIP + Ajuste':<36s}  {outros:>12,.2f}")
print(
    f"  {'BEN Líquido':<36s}  {ben_liq_final:>12,.2f}  (fatura: {FATURA['ben_liquido']:>12,.2f})")
print(
    f"  {'BEN Bruto':<36s}  {ben_bruto_final:>12,.2f}  (fatura: {FATURA['ben_bruto']:>12,.2f})")
print(f"  {'Ajuste BEN (bruto − líquido)':<36s}  {impostos_dem:>12,.2f}")
print(f"  {'─' * 76}")
print(f"  {'TOTAL CALCULADO':<36s}  {total_final:>12,.2f}")
print(f"  {'TOTAL FATURA':<36s}  {TARGET:>12,.2f}")
print(f"  {'DIFERENÇA':<36s}  {total_final - TARGET:>+12,.2f}")
print(f"{'=' * 80}")

# ── 4) Tarifas cheias derivadas ─────────────────────────────────────────────────
print(f"\n  TARIFAS CHEIAS (sem desconto, para atualizar premissas.py):")
print(f"    AZUL_DEMANDA_HP = {tarifa_dem_hp / (1 - d_final):.6f}  R$/kW")
print(f"    AZUL_DEMANDA_FP = {tarifa_dem_fp / (1 - d_final):.6f}  R$/kW")
print(f"    AZUL_TUSD_HP    = {tarifa_tusd * 1000:.6f}  R$/MWh")
print(f"    AZUL_TUSD_FP    = {tarifa_tusd * 1000:.6f}  R$/MWh")
