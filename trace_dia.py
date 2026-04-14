"""
Trace EXTREMAMENTE DETALHADO de 1 dia REAL (não dia típico).
Mostra TODOS os 96 slots de 15 min do dia, com workflow completo.
"""
import pandas as pd
import numpy as np
import datetime
from modelamento_anual import (
    load_full_year, load_solar_profile, _MES_NUM,
    BESS_CAPACIDADE_KWH, BESS_POTENCIA_SAIDA, BESS_POTENCIA_CARGA,
    BESS_CARGA_INICIO, BESS_CARGA_FIM, BESS_GRID_MARGIN, DT,
)

# ---------------------------------------------------------------------------
# 0 — CARREGA DADOS
# ---------------------------------------------------------------------------
year = load_full_year()
solar_profile, solar_monthly = load_solar_profile()

# ---------------------------------------------------------------------------
# DIA ESPECIFICO: 2025-11-20 (quinta-feira, 8332 kWh HP — dia pesado)
# ---------------------------------------------------------------------------
TARGET = datetime.date(2025, 11, 20)
day = year[year.dia == TARGET].copy()
assert len(day) > 0, f"Sem dados para {TARGET}"
mes_label = day.Mes.iloc[0]
mes_num = _MES_NUM[mes_label]
solar_for_hour = {h: float(solar_profile.get((mes_num, h), 0))
                  for h in range(24)}

W = 140  # largura do separador

# ---------------------------------------------------------------------------
# FASE 0 — PARAMETROS DA SIMULACAO
# ---------------------------------------------------------------------------
print("=" * W)
print("FASE 0: PARAMETROS DO MODELO")
print("=" * W)
print(f"  Dia:                   {TARGET} ({pd.Timestamp(TARGET).day_name()})")
print(f"  Mes:                   {mes_label} (mes_num={mes_num})")
print(f"  BESS Capacidade:       {BESS_CAPACIDADE_KWH:,.0f} kWh")
print(f"  BESS Potencia carga:   {BESS_POTENCIA_CARGA:,.0f} kW")
print(f"  BESS Potencia descarg: {BESS_POTENCIA_SAIDA:,.0f} kW")
print(
    f"  Janela de carga:       {BESS_CARGA_INICIO}h ate {BESS_CARGA_FIM}h (={BESS_CARGA_FIM - BESS_CARGA_INICIO}h, {(BESS_CARGA_FIM - BESS_CARGA_INICIO)*4} slots)")
print(f"  Grid margin:           {BESS_GRID_MARGIN*100:.0f}% (zero grid)")
print(f"  DT:                    {DT}h = 15 min")
print(f"  Max carga/slot:        {BESS_POTENCIA_CARGA * DT:,.0f} kWh")
print(f"  Max descarga/slot:     {BESS_POTENCIA_SAIDA * DT:,.0f} kWh")
print(
    f"  Tempo pra encher:      {BESS_CAPACIDADE_KWH / (BESS_POTENCIA_CARGA * DT):.1f} slots = {BESS_CAPACIDADE_KWH / BESS_POTENCIA_CARGA:.2f}h")
print()
print("  WORKFLOW DA SIMULACAO:")
print("  1. SOC inicia em 0 kWh a cada dia (BESS comeca vazio)")
print("  2. Para cada slot cronologicamente:")
print(f"     a) Se hora entre [{BESS_CARGA_INICIO}h, {BESS_CARGA_FIM}h):")
print(f"        - espaco = {BESS_CAPACIDADE_KWH} - SOC")
print(f"        - p_charge = min({BESS_POTENCIA_CARGA}, espaco / {DT})")
print("        - SOC += p_charge * 0.25")
print("        - Essa energia e CONSUMO FP adicional (vem do grid)")
print("     b) Se existe 'Consumo ativo de Ponta' nesse slot (REATIVO ao medidor):")
print("        - cons_kwh = valor do medidor")
print("        - dem_kw = demanda do medidor")
print("        - bess_target_kw = dem_kw * 0.95  (deixa 5% no grid)")
print(
    f"        - max_discharge_kw = min(bess_target_kw, {BESS_POTENCIA_SAIDA})")
print("        - max_discharge_kwh = max_discharge_kw * 0.25")
print("        - actual_discharge = min(SOC, max_discharge_kwh)")
print("        - SOC -= actual_discharge")
print("        - residual = max(0, cons_kwh - actual_discharge)  => fica no grid")
print("     c) Senao: STANDBY (nada acontece)")
print()
print("  NOTA IMPORTANTE SOBRE HORARIO DE PONTA:")
print("  O medidor iplenix classifica ponta como 18:30-21:30, mas esta ERRADO.")
print("  O horario real da Equatorial Piaui e 17:30-20:29.")
print("  load_and_clean() reclassifica os labels HP/FP com base no relogio real.")
print("  Resultado: 12 slots HP x 15min = 3h, de ~17:32 a ~20:17.")
print()

# ---------------------------------------------------------------------------
# FASE 1 — DADOS BRUTOS DO MEDIDOR
# ---------------------------------------------------------------------------
cons_hp_raw = day[(day.Grandeza == 'Consumo') & (
    day.Medicao == 'Consumo ativo de Ponta')]
cons_fp_raw = day[(day.Grandeza == 'Consumo') & (
    day.Medicao == 'Consumo ativo Fora de Ponta')]
dem_hp_raw = day[(day.Grandeza == 'Demanda') & (
    day.Medicao == 'Demanda ativa de Ponta')]
dem_fp_raw = day[(day.Grandeza == 'Demanda') & (
    day.Medicao == 'Demanda ativa Fora de Ponta')]

print("=" * W)
print("FASE 1: DADOS BRUTOS DO MEDIDOR")
print("=" * W)
print(
    f"  Consumo HP total:  {cons_hp_raw.Valor.sum():>10.1f} kWh  ({len(cons_hp_raw)} slots)")
print(
    f"  Consumo FP total:  {cons_fp_raw.Valor.sum():>10.1f} kWh  ({len(cons_fp_raw)} slots)")
print(f"  Demanda HP max:    {dem_hp_raw.Valor.max():>10.1f} kW")
print(f"  Demanda FP max:    {dem_fp_raw.Valor.max():>10.1f} kW")
print(f"  Total leituras:    {len(day)} (= {len(day)//4} slots x 4 grandezas)")
print()

# Listar TODOS os slots HP com timestamp exato
print("  TODOS OS SLOTS HP (timestamp exato do medidor):")
print(f"  {'#':>3s} {'Timestamp':>22s} {'H:M':>6s} {'Cons_kWh':>10s} {'Dem_kW':>10s}")
for i, (_, r) in enumerate(cons_hp_raw.sort_values('Timestamp').iterrows(), 1):
    h = f"{int(r.hora):02d}:{int(r.minuto):02d}"
    dk = dem_hp_raw[(dem_hp_raw.hora == r.hora) &
                    (dem_hp_raw.minuto == r.minuto)]
    dem_v = float(dk.Valor.iloc[0]) if len(dk) > 0 else 0
    print(
        f"  {i:>3d} {str(r.Timestamp):>22s} {h:>6s} {r.Valor:>10.1f} {dem_v:>10.1f}")
print(f"  {'':>3s} {'':>22s} {'TOTAL':>6s} {cons_hp_raw.Valor.sum():>10.1f}")
print()

# Solar do mes
print(f"  PERFIL SOLAR ({mes_label}, kW medio por hora):")
solar_total = 0
for h in range(24):
    s = solar_for_hour[h]
    if s > 0:
        print(f"    {h:02d}h: {s:>8.1f} kW  x{DT}h = {s*DT:.1f} kWh/slot")
        solar_total += s
print(
    f"    Geracao total estimada no dia: {solar_total:.0f} kWh/h => ~{solar_total * 1:.0f} kWh (integral)")
print()

# ---------------------------------------------------------------------------
# FASE 2 — SOLAR FP (pre-calculo, exatamente como o modelo faz)
# ---------------------------------------------------------------------------
print("=" * W)
print("FASE 2: SOLAR — ECONOMIA FP SLOT-A-SLOT (exatamente como simulate_bess_day)")
print("=" * W)
print()
print("  O modelo percorre cada slot de Consumo FP e subtrai a geracao solar.")
print("  Formula: solar_saving_slot = min(consumo_fp_slot, solar_kw * 0.25)")
print()

solar_fp_saving = 0.0
print(f"  {'#':>3s} {'H:M':>6s} {'Cons_FP':>10s} {'Solar_kW':>10s} {'Solar_kWh':>10s} {'Saving':>10s} {'Acum':>10s}")
for i, (_, row) in enumerate(cons_fp_raw.sort_values('Timestamp').iterrows(), 1):
    h = int(row.hora)
    solar_kw = solar_for_hour.get(h, 0.0)
    solar_kwh = solar_kw * DT
    saving = min(row.Valor, solar_kwh)
    solar_fp_saving += saving
    h_str = f"{int(row.hora):02d}:{int(row.minuto):02d}"
    if solar_kw > 0 or i <= 5 or i >= len(cons_fp_raw) - 2:
        print(f"  {i:>3d} {h_str:>6s} {row.Valor:>10.1f} {solar_kw:>10.1f} {solar_kwh:>10.1f} {saving:>10.1f} {solar_fp_saving:>10.1f}")
    elif i == 6:
        print("  ... (slots noturnos sem solar omitidos) ...")

print(f"\n  TOTAL SOLAR FP SAVING: {solar_fp_saving:,.1f} kWh")
print()

# Demanda FP com solar
print("  DEMANDA FP COM SOLAR (max por slot):")
dem_fp_solar_max = 0.0
for _, row in dem_fp_raw.iterrows():
    h = int(row.hora)
    solar_kw = solar_for_hour.get(h, 0.0)
    net = max(0, row.Valor - solar_kw)
    if net > dem_fp_solar_max:
        dem_fp_solar_max = net
        print(
            f"    NOVO MAX: {int(row.hora):02d}:{int(row.minuto):02d}  Dem={row.Valor:.0f}kW - Solar={solar_kw:.0f}kW = {net:.0f}kW")

print(f"  Dem FP sem solar: {dem_fp_raw.Valor.max():.0f} kW")
print(f"  Dem FP com solar: {dem_fp_solar_max:.0f} kW")
print()

# ---------------------------------------------------------------------------
# FASE 3 — SIMULACAO BESS: TODOS OS 96 SLOTS
# ---------------------------------------------------------------------------
print("=" * W)
print("FASE 3: SIMULACAO BESS — TODOS OS SLOTS DO DIA (96+)")
print("=" * W)
print()

soc = 0.0
cons_hp_residual = 0.0
bess_charge_total = 0.0
bess_discharge_total = 0.0
dem_hp_resid_max = 0.0
dem_fp_bess_max = 0.0

all_ts = sorted(day['Timestamp'].unique())

header = (
    f"{'#':>3s} {'Timestamp':>22s} "
    f"{'Fase':>10s} "
    f"{'SOC_ini':>9s} "
    f"{'Acao_kW':>8s} {'Acao_kWh':>9s} "
    f"{'SOC_fim':>9s} "
    f"{'HP_cons':>9s} {'HP_BESS':>9s} {'HP_resid':>9s} "
    f"{'FP_cons':>9s} {'FP_dem':>8s} {'Solar':>7s} "
    f"{'Nota'}"
)
print(header)
print("-" * W)

for slot_num, ts in enumerate(all_ts, 1):
    slot = day[day.Timestamp == ts]
    t = pd.Timestamp(ts)
    hora = t.hour
    minuto = t.minute
    ts_str = str(ts)

    soc_antes = soc
    fase = ''
    acao_kw = 0.0
    acao_kwh = 0.0
    hp_cons = 0.0
    hp_bess = 0.0
    hp_resid = 0.0
    nota = ''

    # Extrair dados desse slot
    fp_cons_slot = slot[(slot.Grandeza == 'Consumo') & (
        slot.Medicao == 'Consumo ativo Fora de Ponta')]
    fp_dem_slot = slot[(slot.Grandeza == 'Demanda') & (
        slot.Medicao == 'Demanda ativa Fora de Ponta')]
    hp_cons_slot = slot[(slot.Grandeza == 'Consumo') & (
        slot.Medicao == 'Consumo ativo de Ponta')]
    hp_dem_slot = slot[(slot.Grandeza == 'Demanda') & (
        slot.Medicao == 'Demanda ativa de Ponta')]

    fp_cons_v = float(fp_cons_slot.Valor.iloc[0]) if len(
        fp_cons_slot) > 0 else 0.0
    fp_dem_v = float(fp_dem_slot.Valor.iloc[0]) if len(
        fp_dem_slot) > 0 else 0.0
    solar_kw = solar_for_hour.get(hora, 0.0)

    # ========== CARGA BESS ==========
    if BESS_CARGA_INICIO <= hora < BESS_CARGA_FIM:
        espaco = BESS_CAPACIDADE_KWH - soc
        p_charge = min(BESS_POTENCIA_CARGA, espaco / DT)
        e_charge = p_charge * DT
        soc += e_charge
        bess_charge_total += e_charge

        # Dem FP BESS tracking
        if len(fp_dem_slot) > 0:
            net_dem = max(0, fp_dem_v - solar_kw) + p_charge
            dem_fp_bess_max = max(dem_fp_bess_max, net_dem)

        fase = 'CARGA'
        acao_kw = p_charge
        acao_kwh = e_charge
        if espaco <= 0.01:
            nota = 'CHEIA! carga=0'
        elif espaco < BESS_POTENCIA_CARGA * DT:
            nota = f'espaco={espaco:.0f}kWh quase cheia'
        else:
            nota = f'espaco={espaco:.0f}kWh'

    # ========== DESCARGA BESS ==========
    if len(hp_cons_slot) > 0:
        cons_kwh = float(hp_cons_slot.Valor.iloc[0])
        dem_kw = float(hp_dem_slot.Valor.iloc[0]) if len(
            hp_dem_slot) > 0 else cons_kwh / DT

        bess_target_kw = dem_kw * (1 - BESS_GRID_MARGIN)
        max_discharge_kw = min(bess_target_kw, BESS_POTENCIA_SAIDA)
        max_discharge_kwh = max_discharge_kw * DT
        actual_discharge = min(soc, max_discharge_kwh)
        soc -= actual_discharge
        bess_discharge_total += actual_discharge

        residual_kwh = max(0.0, cons_kwh - actual_discharge)
        cons_hp_residual += residual_kwh
        dem_hp_resid_max = max(dem_hp_resid_max, residual_kwh / DT)

        fase = 'DESCARGA'
        acao_kw = actual_discharge / DT
        acao_kwh = actual_discharge
        hp_cons = cons_kwh
        hp_bess = actual_discharge
        hp_resid = residual_kwh
        five_pct = dem_kw * BESS_GRID_MARGIN * DT
        nota = (f"Dem={dem_kw:.0f} Tgt95={bess_target_kw:.0f} "
                f"MaxE={max_discharge_kwh:.1f} Act={actual_discharge:.1f} "
                f"5%grid={five_pct:.1f}")
    elif fase != 'CARGA':
        # FP fora de carga: tracking dem_fp_bess
        if not (BESS_CARGA_INICIO <= hora < BESS_CARGA_FIM):
            if len(fp_dem_slot) > 0:
                net_dem = max(0, fp_dem_v - solar_kw)
                dem_fp_bess_max = max(dem_fp_bess_max, net_dem)
        fase = 'STANDBY'
        nota = ''

    soc_fim = soc
    line = (
        f"{slot_num:>3d} {ts_str:>22s} "
        f"{fase:>10s} "
        f"{soc_antes:>9.1f} "
        f"{acao_kw:>8.0f} {acao_kwh:>9.1f} "
        f"{soc_fim:>9.1f} "
        f"{hp_cons:>9.1f} {hp_bess:>9.1f} {hp_resid:>9.1f} "
        f"{fp_cons_v:>9.1f} {fp_dem_v:>8.0f} {solar_kw:>7.0f} "
        f"{nota}"
    )
    print(line)

# ---------------------------------------------------------------------------
# FASE 4 — RESUMO E VERIFICACAO
# ---------------------------------------------------------------------------
print()
print("=" * W)
print("FASE 4: RESUMO DO DIA")
print("=" * W)
print(f"  SOC final:             {soc:>10.1f} kWh")
print(f"  Energia carregada:     {bess_charge_total:>10.1f} kWh")
print(f"  Energia descarregada:  {bess_discharge_total:>10.1f} kWh")
print(f"  HP total (medidor):    {cons_hp_raw.Valor.sum():>10.1f} kWh")
print(f"  HP coberto (BESS):     {bess_discharge_total:>10.1f} kWh")
print(f"  HP residual (grid):    {cons_hp_residual:>10.1f} kWh")
hp_sum = cons_hp_raw.Valor.sum()
if hp_sum > 0:
    print(
        f"  Cobertura:             {(bess_discharge_total / hp_sum) * 100:>10.1f} %")
print(f"  Dem HP resid max:      {dem_hp_resid_max:>10.1f} kW")
print(f"  Dem FP BESS max:       {dem_fp_bess_max:>10.1f} kW")
print(
    f"  BESS morreu?:          {'SIM' if soc <= 1.0 and cons_hp_residual > 100 else 'NAO'}")
print()

print("  VERIFICACAO ENERGETICA:")
print(f"    1) HP_total = HP_coberto_BESS + HP_residual_grid")
print(
    f"       {hp_sum:.1f} = {bess_discharge_total:.1f} + {cons_hp_residual:.1f}")
delta1 = abs(hp_sum - bess_discharge_total - cons_hp_residual)
print(f"       Erro: {delta1:.6f} kWh {'OK' if delta1 < 0.01 else 'ERRO!'}")
print()
print(f"    2) SOC_final = Carga_total - Descarga_total")
print(f"       {soc:.1f} = {bess_charge_total:.1f} - {bess_discharge_total:.1f}")
delta2 = abs(soc - (bess_charge_total - bess_discharge_total))
print(f"       Erro: {delta2:.6f} kWh {'OK' if delta2 < 0.01 else 'ERRO!'}")
print()
print(f"    3) Consumo FP liquido = FP_total - Solar_saving + BESS_carga")
cons_fp_net = max(0.0, cons_fp_raw.Valor.sum() -
                  solar_fp_saving + bess_charge_total)
print(f"       {cons_fp_net:,.1f} = {cons_fp_raw.Valor.sum():,.1f} - {solar_fp_saving:,.1f} + {bess_charge_total:,.1f}")
print()

# ---------------------------------------------------------------------------
# FASE 5 — ANALISE ZERO GRID DETALHADA
# ---------------------------------------------------------------------------
print("=" * W)
print("FASE 5: ANALISE DO ZERO GRID (5%) — SLOT A SLOT DE PONTA")
print("=" * W)
print()
print("  O BESS limita descarga a 95% da demanda. 5% SEMPRE fica no grid.")
print("  Isso evita injecao reversa e mantiene o medidor registrando consumo.")
print()
print(f"  {'#':>3s} {'H:M':>6s} {'Dem_kW':>8s} {'|':>1s} {'95%_kW':>8s} {'95%_kWh':>9s} "
      f"{'|':>1s} {'5%_kWh':>8s} {'|':>1s} {'Cons':>9s} {'BESS':>9s} {'Resid':>9s} "
      f"{'|':>1s} {'Resid==5%?':>10s}")
print("  " + "-" * 100)

soc_check = 0.0
total_5pct = 0.0
total_resid = 0.0
for ts in all_ts:
    slot = day[day.Timestamp == ts]
    hora = pd.Timestamp(ts).hour

    if BESS_CARGA_INICIO <= hora < BESS_CARGA_FIM:
        espaco = BESS_CAPACIDADE_KWH - soc_check
        p_charge = min(BESS_POTENCIA_CARGA, espaco / DT)
        soc_check += p_charge * DT

    hp_c = slot[(slot.Grandeza == 'Consumo') & (
        slot.Medicao == 'Consumo ativo de Ponta')]
    hp_d = slot[(slot.Grandeza == 'Demanda') & (
        slot.Medicao == 'Demanda ativa de Ponta')]

    if len(hp_c) > 0:
        cons_kwh = float(hp_c.Valor.iloc[0])
        dem_kw = float(hp_d.Valor.iloc[0]) if len(hp_d) > 0 else cons_kwh / DT
        minuto = pd.Timestamp(ts).minute
        h_str = f"{hora:02d}:{minuto:02d}"

        t95_kw = dem_kw * 0.95
        cap_kw = min(t95_kw, BESS_POTENCIA_SAIDA)
        t95_kwh = cap_kw * DT
        five_kwh = dem_kw * 0.05 * DT
        actual = min(soc_check, t95_kwh)
        soc_check -= actual
        resid = max(0, cons_kwh - actual)

        total_5pct += five_kwh
        total_resid += resid

        match = 'SIM' if abs(
            resid - five_kwh) < 1.0 else f'NAO (+{resid - five_kwh:.1f})'

        slot_i = len(hp_c)  # just for numbering
        print(f"  {h_str:>6s}   {dem_kw:>8.0f} | {t95_kw:>8.0f} {t95_kwh:>9.1f} "
              f"| {five_kwh:>8.1f} | {cons_kwh:>9.1f} {actual:>9.1f} {resid:>9.1f} "
              f"| {match:>10s}")

print("  " + "-" * 100)
print(f"  {'TOTAL':>6s}   {'':>8s} | {'':>8s} {'':>9s} "
      f"| {total_5pct:>8.1f} | {hp_sum:>9.1f} {bess_discharge_total:>9.1f} {total_resid:>9.1f} "
      f"| {'SIM' if abs(total_resid - total_5pct) < 5 else 'NAO'}")
print()
print(f"  Residual total: {total_resid:.1f} kWh")
print(f"  5% teorico:     {total_5pct:.1f} kWh")
print(f"  Diferenca:      {total_resid - total_5pct:.1f} kWh")
print()
print("  Se Resid == 5% em todos os slots => zero grid funcionando perfeitamente.")
print("  Se Resid > 5% em algum slot => SOC insuficiente (BESS morreu parcialmente).")
