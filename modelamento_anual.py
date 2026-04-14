"""
modelamento_anual.py — Simulação BESS 15-min, dia a dia
=======================================================

Este módulo implementa o **modelo dia-a-dia** de simulação financeira
Solar + BESS. Diferente do modelo Monte Carlo (``montecarlo_dia_tipico.py``),
que trabalha com um dia típico estatístico, este módulo simula **cada dia
individualmente**, preservando toda a variabilidade sazonal e diária.

Fluxo de Execução
-----------------
1. **Carga de dados** (``load_full_year``):
   - 3 meses reais pós-carga (Nov/25, Dez/25, Jan/26) carregados diretamente.
   - 9 meses pré-carga (Fev/25 a Out/25) têm seus valores ajustados via
     delta-correction sazonal (``compute_deltas_avg`` + ``ajustar_serie``).
   - Total: 12 meses (~357 dias, >100k leituras 15-min).

2. **Perfil solar** (``load_solar_profile``):
   - Carrega CSV horário do PVsyst (8.760 horas, 1.890 kWp).
   - Agrega por (mês, hora) para obter geração média kWh/h por mês.

3. **Simulação BESS dia a dia** (``simulate_bess_day``):
   - Para cada dia, percorre todos os slots 15-min cronologicamente.
   - Carga: 07h30–15h a 1.000 kW (máx 7.500 kWh/dia, limitado por cap 6.200 kWh).
   - Descarga: durante ponta (slots com Consumo HP > 0), cobrindo até 95% da
     demanda medida (5% permanece no grid como margem anti-injeção).
   - Potência max descarga: 3.100 kW por slot.
   - SOC carry-over: SOC final do dia anterior é o SOC inicial do dia seguinte.

4. **Faturamento** (via ``fatura/``):
   - Para cada mês, agrega consumo/demanda e calcula 3 cenários:
     - **C1 — Base AZUL**: Sem solar, sem BESS, tarifa AZUL padrão.
     - **C2 — Solar AZUL**: Solar reduz consumo FP, mantém AZUL.
     - **C3 — Solar + BESS VERDE**: Solar + BESS, migração para VERDE.

5. **Análise financeira**: Payback, TIR (bisseção), VPL, ROI.

Delta-Correction (Ajuste Sazonal)
---------------------------------
Comparamos 3 pares de meses iguais (Nov Pré vs Pós, Dez Pré vs Pós,
Jan Pré vs Pós) para estimar como a carga mudou após a instalação do
sistema. Para cada (Grandeza, Mediçao), calculamos:

    Delta_Mediana = mediana_pos / mediana_pre
    Delta_P95 = P95_pos / P95_pre

A mediana dos 3 pares é usada como fator de ajuste. Para cada mês
pré-carga, valores ≤ P90 são multiplicados por Delta_Mediana, e
valores > P90 por Delta_P95 (preservando outliers).

Saídas
------
- Console: Tabela mês a mês, outliers, top-20 piores dias, distribuição HP.
- ``data/bess_simulacao_diaria.csv``: 357 dias com detalhamento.
- ``data/modelamento_anual_resultado.csv``: 12 meses com C1, C2, C3.

Premissas Compartilhadas
------------------------
- BESS: 6.200 kWh cap, 3.100 kW descarga, 1.000 kW carga, 5% grid margin.
- Solar: 1.890 kWp (PVsyst), ~3.134 MWh/ano.
- CAPEX: Solar R$5,7M + BESS R$8,4M + Implantação R$3M = R$17,1M.
- Contrato: Dem HP 2.980 kW, Dem FP 3.280 kW.
- Financeiro: 25 anos, taxa desconto 10%.

Autor: Pipeline de modelamento BESS — Kira Energia.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from fatura import calcular_fatura_azul, calcular_fatura_verde
from fatura.premissas import VERDE_TUSD_HP, VERDE_TUSD_FP, FATOR_TRIBUTADO

DATA_DIR = Path("data")

# --- BESS ---
BESS_CAPACIDADE_KWH = 6_200.0
BESS_POTENCIA_SAIDA = 3_100.0
BESS_POTENCIA_CARGA = 1_000.0
BESS_CARGA_INICIO = 7.5   # 07h30 — aproveita menor demanda matinal
BESS_CARGA_FIM = 15
BESS_GRID_MARGIN = 0.05   # 5 % da demanda fica no grid (anti-injeção)
# kW — cap heurístico de demanda FP nos fins de semana (ajustável)
BESS_WEEKEND_DEM_CAP = 2_800.0
DT = 0.25  # 15 min em horas

# --- Horário de ponta real (Equatorial Piauí) ---
# O medidor iplenix classifica HP como 18:30–21:30, mas o horário real da
# distribuidora é 17:30–20:29.  Reclassificamos em load_and_clean().
PONTA_INICIO_FRAC = 17.5   # 17 h 30 min  (inclusive)
PONTA_FIM_FRAC = 20.5   # 20 h 30 min  (exclusive → último slot 20:29)

_MAPA_FP_PARA_HP = {
    "Consumo ativo Fora de Ponta": "Consumo ativo de Ponta",
    "Demanda ativa Fora de Ponta": "Demanda ativa de Ponta",
}
_MAPA_HP_PARA_FP = {v: k for k, v in _MAPA_FP_PARA_HP.items()}

# --- Solar ---
SOLAR_KWP = 1_890

# --- CAPEX ---
CAPEX_SOLAR = 5_700_000.00
CAPEX_BESS = 8_396_490.96
CAPEX_IMPLANTACAO = 3_000_000.00
CAPEX_TOTAL = CAPEX_SOLAR + CAPEX_BESS + CAPEX_IMPLANTACAO
CAPEX_SOLAR_ONLY = CAPEX_SOLAR + CAPEX_IMPLANTACAO

# --- Contrato ---
DEMANDA_HP_CONTRATADA = 2_980.0
DEMANDA_FP_CONTRATADA = 3_280.0

# --- Financeiro ---
VIDA_UTIL_ANOS = 25
TAXA_DESCONTO = 0.10

# --- Mapeamento de meses ---
MESES_REAIS = [
    ("Nov", "iplenix_nov2025.csv"),
    ("Dez", "iplenix_dez2025.csv"),
    ("Jan", "iplenix_jan2026.csv"),
]
MESES_AJUSTAR = [
    ("Fev", "iplenix_fev2025.csv"),
    ("Mar", "iplenix_mar2025.csv"),
    ("Abr", "iplenix_abr2025.csv"),
    ("Mai", "iplenix_mai2025.csv"),
    ("Jun", "iplenix_jun2025.csv"),
    ("Jul", "iplenix_jul2025.csv"),
    ("Ago", "iplenix_ago2025.csv"),
    ("Set", "iplenix_set2025.csv"),
    ("Out", "iplenix_out2025.csv"),
]
PARES_DELTA = [
    ("Nov", "iplenix_nov2025.csv", "iplenix_nov2024.csv"),
    ("Dez", "iplenix_dez2025.csv", "iplenix_dez2024.csv"),
    ("Jan", "iplenix_jan2026.csv", "iplenix_jan2025.csv"),
]
ORDEM_ANO = ["Nov", "Dez", "Jan", "Fev", "Mar",
             "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out"]
_MES_NUM = {"Nov": 11, "Dez": 12, "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4,
            "Mai": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Out": 10}
CONTRACT_KW = ["Contratad", "Tolerância"]
# Medições reativas que não são usadas na simulação
ZERO_MED = [
    "Consumo Reativo Capacitivo", "Demanda Reativa Capacitiva",
    "Consumo Reativo", "Demanda Reativa",
]


def _brl(v, dec=2):
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ===== 1. CARGA E LIMPEZA =====
def load_and_clean(csv_name):
    """
    Carrega um CSV iplenix e aplica pipeline de limpeza padrão.

    Pipeline de limpeza:

    1. Converte 'Timestamp' para datetime (coerce → NaT em erros).
    2. Remove linhas com Timestamp nulo.
    3. Remove duplicatas exatas (Timestamp × Grandeza × Medicao × Valor).
    4. Remove linhas de contrato/tolerância (não são medições reais).
    5. Remove grandezas sempre-zero (Reativo Capacitivo/Capacitiva).
    6. Ordena cronologicamente.

    Estrutura esperada do CSV iplenix::

        Timestamp            | Valor   | Medicao                        | Grandeza
        2025-11-01 00:17:27 | 537.81  | Consumo ativo Fora de Ponta    | Consumo
        2025-11-03 18:47:27 | 2841.12 | Demanda ativa de Ponta         | Demanda

    Parameters
    ----------
    csv_name : str
        Nome do arquivo CSV dentro de ``DATA_DIR`` (ex: 'iplenix_nov2025.csv').

    Returns
    -------
    pd.DataFrame
        DataFrame limpo com colunas: Timestamp, Valor, Medicao, Grandeza.
    """
    df = pd.read_csv(DATA_DIR / csv_name)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])
    # Discretizar para o minuto (iPlenix grava duplicatas ±1 s)
    df["Timestamp"] = df["Timestamp"].dt.floor("min")
    df = df.drop_duplicates(
        subset=["Timestamp", "Grandeza", "Medicao"])
    mask = df["Medicao"].apply(lambda m: any(kw in m for kw in CONTRACT_KW))
    df = df[~mask]
    df = df[~df["Medicao"].isin(ZERO_MED)]
    df = _reclassificar_ponta(df)
    return df.sort_values("Timestamp").reset_index(drop=True)


def _reclassificar_ponta(df):
    """Reclassifica Medicao HP/FP com base no horário real de ponta 17:30–20:29."""
    hfrac = df.Timestamp.dt.hour + df.Timestamp.dt.minute / 60.0
    is_ponta = (hfrac >= PONTA_INICIO_FRAC) & (hfrac < PONTA_FIM_FRAC)

    # FP → HP (dentro da ponta real mas classificado como FP pelo medidor)
    m1 = is_ponta & df.Medicao.isin(_MAPA_FP_PARA_HP)
    df.loc[m1, "Medicao"] = df.loc[m1, "Medicao"].map(_MAPA_FP_PARA_HP)

    # HP → FP (fora da ponta real mas classificado como HP pelo medidor)
    m2 = ~is_ponta & df.Medicao.isin(_MAPA_HP_PARA_FP)
    df.loc[m2, "Medicao"] = df.loc[m2, "Medicao"].map(_MAPA_HP_PARA_FP)

    return df


def compute_deltas_avg():
    """
    Calcula fatores de ajuste sazonal (Delta) a partir de 3 pares de meses.

    Para cada par (mês pós-carga vs mês pré-carga equivalente), calcula:

    - **Delta_Mediana** = mediana(valores_pos) / mediana(valores_pre)
    - **Delta_P95** = P95(valores_pos) / P95(valores_pre)

    Esses deltas são calculados por (Grandeza, Medicao) — ou seja, separadamente
    para Consumo HP, Consumo FP, Demanda HP, Demanda FP.

    Os 3 pares são: Nov 2025 vs Nov 2024, Dez 2025 vs Dez 2024, Jan 2026 vs
    Jan 2025. A mediana dos 3 deltas é o fator final.

    Justificativa estatística:
    - Delta_Mediana captura a mudança na tendência central (robusto a outliers).
    - Delta_P95 captura a mudança nos extremos (preserva picos de demanda).
    - Usar 3 pares + mediana reduz ruído sazonal e aleatoriedade.

    Returns
    -------
    pd.DataFrame
        Colunas: Grandeza, Medicao, Delta_Mediana, Delta_P95.
        Uma linha por combinação (Grandeza, Medicao).
    """
    all_d = []
    for mes, csv_pos, csv_pre in PARES_DELTA:
        dpos = load_and_clean(csv_pos)
        dpre = load_and_clean(csv_pre)
        for gr in dpos["Grandeza"].unique():
            for med in dpos[dpos.Grandeza == gr]["Medicao"].unique():
                vpos = dpos[(dpos.Grandeza == gr) & (
                    dpos.Medicao == med)]["Valor"]
                vpre = dpre[(dpre.Grandeza == gr) & (
                    dpre.Medicao == med)]["Valor"]
                if vpre.empty or vpos.empty:
                    continue
                mp, mo = vpre.median(), vpos.median()
                pp, po = vpre.quantile(0.95), vpos.quantile(0.95)
                all_d.append({
                    "Grandeza": gr, "Medicao": med,
                    "Delta_Mediana": mo / mp if mp else np.nan,
                    "Delta_P95": po / pp if pp else np.nan, "Mes": mes,
                })
    df = pd.DataFrame(all_d)
    return df.groupby(["Grandeza", "Medicao"], as_index=False).agg(
        Delta_Mediana=("Delta_Mediana", "median"),
        Delta_P95=("Delta_P95", "median"))


def ajustar_serie(df, deltas):
    """
    Aplica ajuste sazonal (delta-correction) a uma série de medições.

    Para cada (Grandeza, Medicao) presente no DataFrame ``deltas``:

    1. Calcula P90 da série original.
    2. Valores ≤ P90: multiplicados por ``Delta_Mediana``.
    3. Valores > P90: multiplicados por ``Delta_P95`` (preserva a fração
       do perfil correspondente a picos de demanda).

    A lógica de threshold P90 com dual delta é um compromisso entre:
    - Ajustar a massa central da distribuição (maioria dos slots)
    - Preservar a estrutura dos picos (que determinam demanda faturada)

    Parameters
    ----------
    df : pd.DataFrame
        Série de medições com colunas: Grandeza, Medicao, Valor.
    deltas : pd.DataFrame
        Fatores de ajuste de ``compute_deltas_avg()``.

    Returns
    -------
    pd.DataFrame
        DataFrame com coluna Valor ajustada (mesmo shape).
    """
    df = df.copy()
    df["Valor_Orig"] = df["Valor"]
    for _, row in deltas.iterrows():
        mask = (df.Grandeza == row.Grandeza) & (df.Medicao == row.Medicao)
        subset = df.loc[mask, "Valor"]
        if subset.empty or pd.isna(row.Delta_Mediana):
            continue
        p90 = subset.quantile(0.90)
        mc = mask & (df.Valor <= p90)
        df.loc[mc, "Valor"] = df.loc[mc, "Valor"] * row.Delta_Mediana
        mp = mask & (df.Valor_Orig > p90)
        dp95 = row.Delta_P95 if not pd.isna(
            row.Delta_P95) else row.Delta_Mediana
        df.loc[mp, "Valor"] = df.loc[mp, "Valor_Orig"] * dp95
    df.drop(columns=["Valor_Orig"], inplace=True)
    return df


# ===== 2. CARREGAR ANO =====
def load_full_year():
    """
    Carrega os 12 meses do ano modelado a partir dos CSVs iplenix.

    Composição do ano:

    - **3 meses reais** (pós-instalação): Nov/25, Dez/25, Jan/26.
      Carregados sem ajuste — representam o padrão de carga real após
      a instalação do sistema solar.
    - **9 meses ajustados** (pré-instalação): Fev/25 a Out/25.
      Carregados dos CSVs originais e ajustados via ``ajustar_serie()``
      com deltas calculados por ``compute_deltas_avg()``.

    Colunas adicionadas ao DataFrame:
    - ``Mes``: Abreviação 3 letras (Nov, Dez, Jan, ...).
    - ``Tipo``: 'Real' ou 'Ajustado'.
    - ``dia``: Data (date) para agrupamento por dia.
    - ``hora``, ``minuto``, ``hora_frac``: Componentes temporais.

    Returns
    -------
    pd.DataFrame
        Ano completo (~357 dias, >100k leituras).
    """
    print("[1] Carregando ano completo (15-min)...")
    deltas = compute_deltas_avg()
    frames = []
    for mes, csv in MESES_REAIS:
        df = load_and_clean(csv)
        df["Mes"] = mes
        df["Tipo"] = "Real"
        frames.append(df)
        print(f"    {mes}: {len(df):>6d} leituras (real)")
    for mes, csv in MESES_AJUSTAR:
        df = load_and_clean(csv)
        df = ajustar_serie(df, deltas)
        df["Mes"] = mes
        df["Tipo"] = "Ajustado"
        frames.append(df)
        print(f"    {mes}: {len(df):>6d} leituras (ajustado)")
    year = pd.concat(frames, ignore_index=True)
    year["dia"] = year.Timestamp.dt.date
    year["hora"] = year.Timestamp.dt.hour
    year["minuto"] = year.Timestamp.dt.minute
    year["hora_frac"] = year.hora + year.minuto / 60.0
    print(f"    Total: {len(year)} leituras, {year.dia.nunique()} dias")
    return year


# ===== 3. SOLAR PVSYST =====
def load_solar_profile():
    """
    Carrega o perfil de geração solar do PVsyst e agrega por (mês, hora).

    O CSV do PVsyst contém 8.760 linhas (1 por hora do ano), com:
    - ``EArray``: Energia no array DC (kWh/h).
    - ``E_Grid``: Energia injetada no grid AC (kWh/h) — usada para faturamento.

    Processamento:
    1. Valores negativos de E_Grid (consumo noturno de inversores) são zerados.
    2. Agrega ``EArray`` por (mês, hora) → média horária por mês.
    3. Agrega ``E_Grid`` por mês → geração total mensal (kWh).

    A média horária por mês é usada no ``simulate_bess_day()`` para:
    - Reduzir consumo FP slot a slot (solar coincide com horário fora-ponta).
    - Calcular demanda FP líquida (dem_original - solar_kW).

    Returns
    -------
    tuple[pd.Series, dict]
        - ``solar_profile``: Series indexada por (mes_num, hora) com kWh/h médio.
        - ``solar_monthly``: Dict {mes_nome: total_kwh} para os 12 meses.
    """
    print("[2] Carregando perfil solar PVsyst...")
    pv = pd.read_csv(
        DATA_DIR / "Shopping Rio Poty_Project_VCA_HourlyRes_0.CSV",
        sep=";", skiprows=12, header=None,
        names=["data", "EArray", "E_Grid"], decimal=",", encoding="latin-1")
    pv["data"] = pv["data"].str.strip()
    pv["dt"] = pd.to_datetime(pv["data"], format="%d/%m/%y %H:%M")
    pv["hora"] = pv["dt"].dt.hour
    pv["mes"] = pv["dt"].dt.month
    pv["EArray"] = pd.to_numeric(pv["EArray"], errors="coerce").fillna(0)
    pv["E_Grid"] = pd.to_numeric(pv["E_Grid"], errors="coerce").fillna(0)
    pv.loc[pv.E_Grid < 0, "E_Grid"] = 0.0
    pv.loc[pv.EArray < 0, "EArray"] = 0.0
    solar_profile = pv.groupby(["mes", "hora"])["EArray"].mean()
    monthly_kwh = pv.groupby("mes")["E_Grid"].sum()
    solar_monthly = {m: float(monthly_kwh.get(
        _MES_NUM[m], 0)) for m in ORDEM_ANO}
    annual = sum(solar_monthly.values())
    print(f"    Geracao anual: {_brl(annual/1000, 0)} MWh")
    return solar_profile, solar_monthly


# ===== 4. SIMULACAO BESS 15-MIN POR DIA =====
def simulate_bess_day(day_data, solar_by_hour, initial_soc=0.0,
                      collect_timeline=False):
    """
    Simula a operação do BESS slot a slot (15 min) para um único dia.

    Cronologia do dia:

    1. **00:00–07:30**: Standby. SOC = carry-over do dia anterior.
    2. **07:30–15:00**: Carga a 1.000 kW (30 slots × 0,25h = 7.500 kWh max,
       limitado pela cap 6.200 kWh).
       Se SOC atingir 6.200 kWh, carga reduzida ao espaço livre.
    3. **~17:30–20:29**: Ponta. BESS descarrega cobrindo até 95% da demanda.
       Os 5% restantes (grid margin) evitam injeção reversa no grid.
    4. **20:30–24:00**: Standby. SOC residual passa para o dia seguinte.

    Lógica de descarga (ponta)::

        bess_target_kw = dem_medida_kw × (1 − 0.05)
        max_discharge_kw = min(bess_target_kw, 3100)
        actual_discharge_kwh = min(SOC, max_discharge_kw × 0.25)
        SOC -= actual_discharge_kwh
        residual_kwh = max(0, consumo_slot − actual_discharge_kwh)

    Para dias **sem ponta** (fins de semana/feriados):

    - **Fim de semana** (sáb/dom): BESS faz peak-shaving FP — carrega durante
      07h30–15h (limitado para demanda ≤ 2.800 kW) e descarrega se a demanda
      líquida (FP − solar) exceder 2.800 kW em qualquer slot.
    - **Feriados em dia útil**: BESS permanece idle, SOC carrega.

    Solar (cenários C2 e C3):
    - Reduz consumo FP slot a slot (``cons_fp - solar_kw × DT``).
    - Reduz demanda FP efetiva (``dem_fp - solar_kw``).
    - Não afeta ponta (solar não gera à noite).
    - A carga do BESS durante 7h30–15h adiciona consumo ao grid FP.

    Parameters
    ----------
    day_data : pd.DataFrame
        Todos os registros de um dia (Timestamp, Valor, Medicao, Grandeza,
        hora, minuto, etc.).
    solar_by_hour : pd.Series ou dict
        Geração solar média (kWh/h) indexada por hora (0–23) para o mês
        correspondente.

    Returns
    -------
    dict
        - ``cons_hp_total``: Consumo HP total do dia (kWh).
        - ``cons_hp_residual``: HP não coberto pelo BESS (kWh).
        - ``cons_fp_total``: Consumo FP total (kWh).
        - ``cons_fp_net``: FP líquido (FP − solar + BESS_charge).
        - ``dem_hp_max``: Demanda HP máxima (kW).
        - ``dem_fp_max``: Demanda FP máxima sem solar (kW).
        - ``dem_fp_solar``: Demanda FP máxima com solar (kW).
        - ``dem_fp_bess``: Demanda FP máxima com solar + BESS charge (kW).
        - ``dem_hp_resid``: Demanda HP residual máxima (kW).
        - ``bess_dead``: True se SOC ≤ 1 kWh durante ponta.
        - ``solar_saving``: Economia FP por solar (kWh).
        - ``bess_charge_kwh``: Energia carregada no BESS (kWh).
    """
    cons_hp = day_data[(day_data.Grandeza == "Consumo") & (
        day_data.Medicao == "Consumo ativo de Ponta")]
    cons_fp = day_data[(day_data.Grandeza == "Consumo") & (
        day_data.Medicao == "Consumo ativo Fora de Ponta")]
    dem_hp = day_data[(day_data.Grandeza == "Demanda") & (
        day_data.Medicao == "Demanda ativa de Ponta")]
    dem_fp = day_data[(day_data.Grandeza == "Demanda") & (
        day_data.Medicao == "Demanda ativa Fora de Ponta")]

    cons_hp_total = float(cons_hp["Valor"].sum()) if len(cons_hp) > 0 else 0.0
    cons_fp_total = float(cons_fp["Valor"].sum())
    dem_hp_max = float(dem_hp["Valor"].max()) if len(dem_hp) > 0 else 0.0
    dem_fp_max = float(dem_fp["Valor"].max()) if len(dem_fp) > 0 else 0.0

    first_ts = pd.Timestamp(day_data["Timestamp"].iloc[0])
    is_weekend = first_ts.dayofweek >= 5  # Sab=5, Dom=6

    if is_weekend:
        # No fim de semana não existe HP — tudo é FP
        cons_fp_total += cons_hp_total
        cons_hp_total = 0.0
        dem_fp_max = max(dem_fp_max, dem_hp_max)
        dem_hp_max = 0.0

    # Solar savings em consumo FP (solar não gera em 17:30-20:29)
    solar_fp_saving = 0.0
    for _, row in cons_fp.iterrows():
        h = int(row.hora)
        solar_kw = float(solar_by_hour.get(h, 0.0))
        solar_fp_saving += min(row.Valor, solar_kw * DT)

    # Demanda FP com solar
    dem_fp_solar_max = 0.0
    for _, row in dem_fp.iterrows():
        h = int(row.hora)
        solar_kw = float(solar_by_hour.get(h, 0.0))
        net = max(0, row.Valor - solar_kw)
        dem_fp_solar_max = max(dem_fp_solar_max, net)
    if is_weekend:
        # Include HP-window demand (solar = 0 there)
        dem_fp_solar_max = max(dem_fp_solar_max, float(
            dem_hp["Valor"].max()) if len(dem_hp) > 0 else 0.0)
    if dem_fp_solar_max == 0.0:
        dem_fp_solar_max = dem_fp_max

    has_ponta = cons_hp_total > 0

    if not has_ponta and not is_weekend:
        # Feriado em dia útil: BESS permanece idle, SOC carrega
        result = {
            "cons_hp_total": 0.0, "cons_hp_residual": 0.0,
            "cons_fp_total": cons_fp_total,
            "cons_fp_net": max(0, cons_fp_total - solar_fp_saving),
            "dem_hp_max": 0.0, "dem_fp_max": dem_fp_max,
            "dem_fp_solar": dem_fp_solar_max, "dem_fp_bess": dem_fp_solar_max,
            "dem_hp_resid": 0.0, "bess_dead": False,
            "solar_saving": solar_fp_saving, "bess_charge_kwh": 0.0,
            "soc_final": initial_soc,
        }
        if collect_timeline:
            tl = []
            soc_np = initial_soc
            for ts in sorted(day_data["Timestamp"].unique()):
                slot = day_data[day_data.Timestamp == ts]
                h = pd.Timestamp(ts).hour
                fp_dem = slot[(slot.Grandeza == "Demanda") & (
                    slot.Medicao == "Demanda ativa Fora de Ponta")]
                fp_con = slot[(slot.Grandeza == "Consumo") & (
                    slot.Medicao == "Consumo ativo Fora de Ponta")]
                d_fp = float(fp_dem.Valor.iloc[0]) if len(fp_dem) > 0 else 0.0
                c_fp = float(fp_con.Valor.iloc[0]) if len(fp_con) > 0 else 0.0
                sol = float(solar_by_hour.get(h, 0.0))
                bruta = d_fp
                solar_liq = max(0.0, bruta - sol)
                tl.append({
                    "timestamp": str(ts), "dem_hp_kw": 0.0,
                    "dem_fp_kw": d_fp, "solar_kw": sol,
                    "soc_kwh": round(soc_np, 1), "bess_kw": 0.0,
                    "cons_hp_kwh": 0.0, "cons_fp_kwh": c_fp,
                    "demanda_bruta_kw": round(bruta, 1),
                    "demanda_solar_kw": round(solar_liq, 1),
                    "demanda_liquida_kw": round(solar_liq, 1),
                })
            result["timeline"] = tl
        return result

    if is_weekend:
        # === FIM DE SEMANA: BESS faz peak-shaving FP cap 2800 kW ===
        # Tudo é FP — meter labels HP/FP mesclados em demanda total.
        soc = initial_soc
        bess_charge_total = 0.0
        bess_discharge_total = 0.0
        dem_fp_bess_max = 0.0
        timeline = [] if collect_timeline else None

        all_ts = sorted(day_data["Timestamp"].unique())
        for ts in all_ts:
            slot = day_data[day_data.Timestamp == ts]
            hora = pd.Timestamp(ts).hour
            minuto = pd.Timestamp(ts).minute
            hora_frac = hora + minuto / 60.0

            # Weekend: merge HP + FP (tudo é FP)
            fp_slot_dem = slot[(slot.Grandeza == "Demanda") & (
                slot.Medicao == "Demanda ativa Fora de Ponta")]
            hp_slot_dem = slot[(slot.Grandeza == "Demanda") & (
                slot.Medicao == "Demanda ativa de Ponta")]
            fp_slot_con = slot[(slot.Grandeza == "Consumo") & (
                slot.Medicao == "Consumo ativo Fora de Ponta")]
            hp_slot_con = slot[(slot.Grandeza == "Consumo") & (
                slot.Medicao == "Consumo ativo de Ponta")]
            d_fp = float(fp_slot_dem.Valor.iloc[0]) if len(
                fp_slot_dem) > 0 else 0.0
            d_hp = float(hp_slot_dem.Valor.iloc[0]) if len(
                hp_slot_dem) > 0 else 0.0
            d_total = d_fp + d_hp  # tudo é FP no fim de semana
            c_fp = float(fp_slot_con.Valor.iloc[0]) if len(
                fp_slot_con) > 0 else 0.0
            c_hp = float(hp_slot_con.Valor.iloc[0]) if len(
                hp_slot_con) > 0 else 0.0
            c_total = c_fp + c_hp
            solar_kw = float(solar_by_hour.get(hora, 0.0))
            bess_kw = 0.0

            net_demand = max(0, d_total - solar_kw)

            if BESS_CARGA_INICIO <= hora_frac < BESS_CARGA_FIM:
                if net_demand <= BESS_WEEKEND_DEM_CAP:
                    # Espaço para carregar sem estourar 2800
                    espaco = BESS_CAPACIDADE_KWH - soc
                    headroom = BESS_WEEKEND_DEM_CAP - net_demand
                    p_charge = min(BESS_POTENCIA_CARGA, headroom, espaco / DT)
                    p_charge = max(0.0, p_charge)
                    soc += p_charge * DT
                    bess_charge_total += p_charge * DT
                    bess_kw = p_charge
                    final_demand = net_demand + p_charge
                else:
                    # Demanda > 2800 mesmo na janela de carga → descarrega
                    excess = net_demand - BESS_WEEKEND_DEM_CAP
                    discharge_kw = min(excess, BESS_POTENCIA_SAIDA, soc / DT)
                    soc -= discharge_kw * DT
                    bess_discharge_total += discharge_kw * DT
                    bess_kw = -discharge_kw
                    final_demand = net_demand - discharge_kw
            else:
                # Fora da janela de carga: descarrega se demanda > 2800
                if net_demand > BESS_WEEKEND_DEM_CAP:
                    excess = net_demand - BESS_WEEKEND_DEM_CAP
                    discharge_kw = min(excess, BESS_POTENCIA_SAIDA, soc / DT)
                    soc -= discharge_kw * DT
                    bess_discharge_total += discharge_kw * DT
                    bess_kw = -discharge_kw
                    final_demand = net_demand - discharge_kw
                else:
                    final_demand = net_demand

            dem_fp_bess_max = max(dem_fp_bess_max, final_demand)

            if collect_timeline:
                bruta = d_total
                solar_liq = max(0.0, bruta - solar_kw)
                rede = max(0.0, bruta - solar_kw + bess_kw)
                timeline.append({
                    "timestamp": str(ts),
                    "dem_hp_kw": 0.0,
                    "dem_fp_kw": round(d_total, 1),
                    "solar_kw": round(solar_kw, 1),
                    "soc_kwh": round(soc, 1),
                    "bess_kw": round(bess_kw, 1),
                    "cons_hp_kwh": 0.0,
                    "cons_fp_kwh": round(c_total, 2),
                    "demanda_bruta_kw": round(bruta, 1),
                    "demanda_solar_kw": round(solar_liq, 1),
                    "demanda_liquida_kw": round(rede, 1),
                })

        if dem_fp_bess_max == 0.0:
            dem_fp_bess_max = dem_fp_solar_max

        cons_fp_net_wk = max(0.0, cons_fp_total - solar_fp_saving
                             + bess_charge_total - bess_discharge_total)
        result = {
            "cons_hp_total": 0.0, "cons_hp_residual": 0.0,
            "cons_fp_total": cons_fp_total,
            "cons_fp_net": cons_fp_net_wk,
            "dem_hp_max": 0.0, "dem_fp_max": dem_fp_max,
            "dem_fp_solar": dem_fp_solar_max, "dem_fp_bess": dem_fp_bess_max,
            "dem_hp_resid": 0.0, "bess_dead": False,
            "solar_saving": solar_fp_saving,
            "bess_charge_kwh": bess_charge_total,
            "soc_final": soc,
        }
        if collect_timeline:
            result["timeline"] = timeline
        return result

    # Dia com ponta: BESS carrega 7h30-15h, descarrega durante ponta
    soc = initial_soc
    cons_hp_residual = 0.0
    dem_hp_resid_max = 0.0
    bess_charge_total = 0.0
    dem_fp_bess_max = 0.0
    timeline = [] if collect_timeline else None

    all_ts = sorted(day_data["Timestamp"].unique())

    # Precomputar slots HP para descarga SOC-proporcional
    hp_timestamps = set()
    for ts in all_ts:
        slot_pre = day_data[day_data.Timestamp == ts]
        hp_check = slot_pre[(slot_pre.Grandeza == "Consumo") & (
            slot_pre.Medicao == "Consumo ativo de Ponta")]
        if len(hp_check) > 0:
            hp_timestamps.add(ts)
    total_hp_slots = len(hp_timestamps)
    spent_hp_slots = 0

    for ts in all_ts:
        slot = day_data[day_data.Timestamp == ts]
        hora = pd.Timestamp(ts).hour
        minuto = pd.Timestamp(ts).minute
        hora_frac = hora + minuto / 60.0

        # Extrair dados do slot para timeline
        fp_slot_dem = slot[(slot.Grandeza == "Demanda") & (
            slot.Medicao == "Demanda ativa Fora de Ponta")]
        fp_slot_con = slot[(slot.Grandeza == "Consumo") & (
            slot.Medicao == "Consumo ativo Fora de Ponta")]
        hp_slot_cons = slot[(slot.Grandeza == "Consumo") & (
            slot.Medicao == "Consumo ativo de Ponta")]
        hp_slot_dem = slot[(slot.Grandeza == "Demanda") & (
            slot.Medicao == "Demanda ativa de Ponta")]

        d_fp = float(fp_slot_dem.Valor.iloc[0]) if len(
            fp_slot_dem) > 0 else 0.0
        c_fp = float(fp_slot_con.Valor.iloc[0]) if len(
            fp_slot_con) > 0 else 0.0
        d_hp = float(hp_slot_dem.Valor.iloc[0]) if len(
            hp_slot_dem) > 0 else 0.0
        c_hp = float(hp_slot_cons.Valor.iloc[0]) if len(
            hp_slot_cons) > 0 else 0.0
        solar_kw = float(solar_by_hour.get(hora, 0.0))
        bess_kw = 0.0  # positive = charge, negative = discharge

        # === CARGA BESS (7h30-15h) ===
        if BESS_CARGA_INICIO <= hora_frac < BESS_CARGA_FIM:
            espaco = BESS_CAPACIDADE_KWH - soc
            p_charge = min(BESS_POTENCIA_CARGA, espaco / DT)
            # A4: Headroom — limitar carga para que dem_FP não ultrapasse BESS_POTENCIA_SAIDA
            dem_liquida = max(0, d_fp - solar_kw)
            headroom = max(0, BESS_POTENCIA_SAIDA - dem_liquida)
            p_charge = min(p_charge, headroom)
            soc += p_charge * DT
            bess_charge_total += p_charge * DT
            bess_kw = p_charge

            if len(fp_slot_dem) > 0:
                net = max(0, d_fp - solar_kw + p_charge)
                dem_fp_bess_max = max(dem_fp_bess_max, net)

        # === DESCARGA BESS (ponta) — SOC-proporcional ===
        if len(hp_slot_cons) > 0:
            cons_kwh = c_hp
            dem_kw = d_hp if d_hp > 0 else cons_kwh / DT

            # BESS alimenta no máximo 95% da demanda (5% fica no grid p/ anti-injeção)
            bess_target_kw = dem_kw * (1 - BESS_GRID_MARGIN)
            # A2: Budget SOC-proporcional — distribuir SOC uniformemente entre slots restantes
            remaining_hp_slots = total_hp_slots - spent_hp_slots
            if remaining_hp_slots > 0:
                budget_kw = soc / (remaining_hp_slots * DT)
            else:
                budget_kw = BESS_POTENCIA_SAIDA
            max_discharge_kw = min(
                bess_target_kw, BESS_POTENCIA_SAIDA, budget_kw)
            max_discharge_kwh = max_discharge_kw * DT
            actual_discharge = min(soc, max_discharge_kwh)
            soc -= actual_discharge
            bess_kw = -(actual_discharge / DT)
            spent_hp_slots += 1

            residual_kwh = max(0.0, cons_kwh - actual_discharge)
            cons_hp_residual += residual_kwh
            dem_hp_resid_max = max(
                dem_hp_resid_max, dem_kw - actual_discharge / DT)
        else:
            # FP slot fora de carga BESS
            if not (BESS_CARGA_INICIO <= hora_frac < BESS_CARGA_FIM):
                if len(fp_slot_dem) > 0:
                    net = max(0, d_fp - solar_kw)
                    dem_fp_bess_max = max(dem_fp_bess_max, net)

        if collect_timeline:
            bruta = d_hp + d_fp
            solar_liq = max(0.0, bruta - solar_kw)
            rede = max(0.0, bruta - solar_kw + bess_kw)
            timeline.append({
                "timestamp": str(ts),
                "dem_hp_kw": round(d_hp, 1),
                "dem_fp_kw": round(d_fp, 1),
                "solar_kw": round(solar_kw, 1),
                "soc_kwh": round(soc, 1),
                "bess_kw": round(bess_kw, 1),
                "cons_hp_kwh": round(c_hp, 2),
                "cons_fp_kwh": round(c_fp, 2),
                "demanda_bruta_kw": round(bruta, 1),
                "demanda_solar_kw": round(solar_liq, 1),
                "demanda_liquida_kw": round(rede, 1),
            })

    if dem_fp_bess_max == 0.0:
        dem_fp_bess_max = dem_fp_solar_max

    cons_fp_net = max(0.0, cons_fp_total - solar_fp_saving + bess_charge_total)

    result = {
        "cons_hp_total": cons_hp_total,
        "cons_hp_residual": cons_hp_residual,
        "cons_fp_total": cons_fp_total,
        "cons_fp_net": cons_fp_net,
        "dem_hp_max": dem_hp_max,
        "dem_fp_max": dem_fp_max,
        "dem_fp_solar": dem_fp_solar_max,
        "dem_fp_bess": dem_fp_bess_max,
        "dem_hp_resid": dem_hp_resid_max,
        "bess_dead": soc <= 1.0 and cons_hp_total > 0,
        "solar_saving": solar_fp_saving,
        "bess_charge_kwh": bess_charge_total,
        "soc_final": soc,
    }
    if collect_timeline:
        result["timeline"] = timeline
    return result


# ===== 5. ITERACAO DIA-A-DIA =====
def compute_year():
    """
    Pipeline principal: itera todos os dias do ano e calcula resultados.

    Sequência completa:

    1. ``load_full_year()`` → DataFrame com 12 meses (3 reais + 9 ajustados).
    2. ``load_solar_profile()`` → Perfil solar PVsyst por (mês, hora).
    3. Para cada dia: ``simulate_bess_day()`` → métricas BESS.
    4. Para cada mês: agrega consumo/demanda e calcula 3 faturas.
    5. Totaliza ano: C1 vs C2 vs C3, economia, payback, TIR, VPL.
    6. Análise de outliers: dias onde BESS não cobre 100% do HP.
    7. Exporta CSVs: ``bess_simulacao_diaria.csv`` e ``modelamento_anual_resultado.csv``.

    Cenários de faturamento mensal:

    - **C1 (Base AZUL):** Fatura AZUL com demanda original, consumo original.
    - **C2 (Solar AZUL):** Fatura AZUL com consumo FP reduzido por solar.
    - **C3 (Solar+BESS VERDE):** Fatura VERDE com HP residual (pós-BESS),
      FP líquido (FP − solar + BESS_charge), demanda VERDE = max(dem_FP_BESS, dem_HP_resid).

    Returns
    -------
    tuple[pd.DataFrame, list[dict]]
        - ``df_days``: DataFrame com 1 linha por dia (357 dias).
        - ``monthly``: Lista de 12 dicts (um por mês) com C1, C2, C3.
    """
    print("=" * 90)
    print("  MODELAMENTO ANUAL - SIMULACAO BESS 15 MIN, DIA A DIA")
    print("=" * 90)

    year = load_full_year()
    solar_profile, solar_monthly = load_solar_profile()

    print()
    print("[3] Simulando BESS 15-min para cada dia do ano...")

    dias = sorted(year.dia.unique())
    day_results = []
    all_timeline = []
    soc_carryover = 0.0

    for i, dia in enumerate(dias):
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
        solar_s = pd.Series(solar_for_month)

        res = simulate_bess_day(day_data, solar_s, initial_soc=soc_carryover,
                                collect_timeline=True)
        soc_carryover = res["soc_final"]
        if "timeline" in res:
            all_timeline.extend(res.pop("timeline"))
        day_results.append({"dia": dia, "mes": mes, "tipo": tipo, **res})

        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(dias)} dias...")

    df_days = pd.DataFrame(day_results)
    df_days["dia"] = pd.to_datetime(df_days["dia"])
    df_days["dow"] = df_days.dia.dt.day_name()
    df_days["has_ponta"] = df_days.cons_hp_total > 0
    df_days["has_overflow"] = df_days.cons_hp_residual > 0

    n_total = len(df_days)
    n_ponta = int(df_days.has_ponta.sum())
    n_over = int(df_days.has_overflow.sum())
    print(
        f"    {n_total} dias simulados, {n_ponta} com ponta, {n_over} com HP residual")

    # ==================================================================
    #  FATURAS MES A MES
    # ==================================================================
    print()
    print("[4] Calculando faturas mes a mes...")
    print()
    SEP = "-" * 115
    hdr = (f"  {'Mes':<5s}|{'C1 AZUL':>14s}|{'C2 Solar':>14s}|"
           f"{'C3 VERDE+BESS':>14s}|{'HP orig':>10s}|{'HP resid':>10s}|"
           f"{'Dias':>5s}|{'Over':>5s}|{'BESS dead':>9s}")
    print(hdr)
    print(f"  {SEP}")

    monthly = []
    total_c1 = total_c2 = total_c3 = 0.0

    for mes in ORDEM_ANO:
        dm = df_days[df_days.mes == mes]
        if len(dm) == 0:
            continue

        cons_hp = float(dm.cons_hp_total.sum())
        cons_fp = float(dm.cons_fp_total.sum())
        cons_hp_resid = float(dm.cons_hp_residual.sum())
        cons_fp_net = float(dm.cons_fp_net.sum())
        solar_gen = solar_monthly[mes]
        n_p = int(dm.has_ponta.sum())
        n_o = int(dm.has_overflow.sum())
        n_bd = int(dm.bess_dead.sum())

        dem_hp_max = float(dm.dem_hp_max.max())
        dem_fp_max = float(dm.dem_fp_max.max())
        dem_fp_solar = float(dm.dem_fp_solar.max())
        dem_fp_bess = float(dm.dem_fp_bess.max())
        dem_hp_resid = float(dm.dem_hp_resid.max())

        # C1: Base AZUL
        fat_c1 = calcular_fatura_azul(
            DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
            dem_hp_max, dem_fp_max, cons_hp, cons_fp)

        # C2: Solar AZUL
        cons_fp_solar = max(0.0, cons_fp - solar_gen)
        fat_c2 = calcular_fatura_azul(
            DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
            dem_hp_max, dem_fp_solar, cons_hp, cons_fp_solar)

        # C3: Solar + BESS VERDE
        dem_verde = max(dem_fp_bess, dem_hp_resid)
        fat_c3 = calcular_fatura_verde(
            DEMANDA_FP_CONTRATADA, dem_verde, cons_hp_resid, cons_fp_net)

        c1 = fat_c1["custo_total"]
        c2 = fat_c2["custo_total"]
        c3 = fat_c3["custo_total"]
        total_c1 += c1
        total_c2 += c2
        total_c3 += c3

        row_str = (f"  {mes:<5s}| R$ {_brl(c1):>10s} | R$ {_brl(c2):>10s} | "
                   f"R$ {_brl(c3):>10s} | {_brl(cons_hp, 0):>8s} | "
                   f"{_brl(cons_hp_resid, 0):>8s} |{n_p:>4d} |{n_o:>4d} |{n_bd:>7d}  ")
        print(row_str)

        monthly.append({
            "mes": mes, "c1": c1, "c2": c2, "c3": c3,
            "cons_hp": cons_hp, "cons_fp": cons_fp,
            "cons_hp_resid": cons_hp_resid, "cons_fp_net": cons_fp_net,
            "solar_gen": solar_gen, "dem_hp": dem_hp_max, "dem_fp": dem_fp_max,
            "dem_verde": dem_verde, "dem_hp_resid": dem_hp_resid,
            "n_ponta": n_p, "n_overflow": n_o, "n_bess_dead": n_bd,
        })

    print(f"  {SEP}")
    hp_t = sum(m["cons_hp"] for m in monthly)
    hp_r = sum(m["cons_hp_resid"] for m in monthly)
    np_ = sum(m["n_ponta"] for m in monthly)
    no_ = sum(m["n_overflow"] for m in monthly)
    nb_ = sum(m["n_bess_dead"] for m in monthly)
    tot_str = (f"  {'TOTAL':<5s}| R$ {_brl(total_c1):>10s} | R$ {_brl(total_c2):>10s} | "
               f"R$ {_brl(total_c3):>10s} | {_brl(hp_t, 0):>8s} | "
               f"{_brl(hp_r, 0):>8s} |{np_:>4d} |{no_:>4d} |{nb_:>7d}  ")
    print(tot_str)

    # ==================================================================
    #  COMPARATIVO ANUAL
    # ==================================================================
    eco_solar = total_c1 - total_c2
    eco_total = total_c1 - total_c3

    print(f"\n\n  {'='*72}")
    print("  COMPARATIVO ANUAL")
    print(f"  {'='*72}")
    print(f"  {'Cenario':<30s} | {'Anual':>16s} | {'R$/mes medio':>14s}")
    print(f"  {'-'*65}")
    print(f"  {'C1 - Base AZUL':<30s} | R$ {_brl(total_c1):>13s} | R$ {_brl(total_c1/12):>11s}")
    print(f"  {'C2 - Solar AZUL':<30s} | R$ {_brl(total_c2):>13s} | R$ {_brl(total_c2/12):>11s}")
    print(f"  {'C3 - Solar+BESS VERDE':<30s} | R$ {_brl(total_c3):>13s} | R$ {_brl(total_c3/12):>11s}")
    print(f"  {'-'*65}")
    print(f"  Economia Solar:          R$ {_brl(eco_solar):>13s}/ano")
    print(f"  Economia Solar+BESS:     R$ {_brl(eco_total):>13s}/ano")

    # ==================================================================
    #  OUTLIERS
    # ==================================================================
    overflow = df_days[df_days.has_overflow].sort_values(
        "cons_hp_residual", ascending=False)

    print(f"\n\n  {'='*95}")
    print(
        f"  DIAS OUTLIER - BESS NAO COBRIU 100% DA PONTA ({len(overflow)} dias)")
    print(f"  {'='*95}")
    print(
        f"  HP residual total: {_brl(float(overflow.cons_hp_residual.sum()), 0)} kWh/ano")
    tarifa_hp_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP - VERDE_TUSD_FP) * 0.5
    custo_res = float(overflow.cons_hp_residual.sum()) / \
        1000 * tarifa_hp_efetiva / FATOR_TRIBUTADO
    print(f"  Custo TUSD HP residual: R$ {_brl(custo_res)}/ano")
    print()
    hdr2 = (f"  {'Dia':<12s}|{'DoW':<10s}|{'Mes':<5s}|{'HP Total':>10s}|"
            f"{'BESS Used':>10s}|{'HP Resid':>10s}|{'Dem HP kW':>10s}|{'BESS dead':>9s}")
    print(hdr2)
    print(f"  {'-'*82}")
    for _, r in overflow.iterrows():
        ds = r.dia.strftime("%Y-%m-%d")
        bess_used = r.cons_hp_total - r.cons_hp_residual
        bd = "SIM" if r.bess_dead else "nao"
        print(f"  {ds}|{r.dow:<10s}|{r.mes:<5s}|"
              f" {_brl(r.cons_hp_total, 0):>8s} |"
              f" {_brl(bess_used, 0):>8s} |"
              f" {_brl(r.cons_hp_residual, 0):>8s} |"
              f" {r.dem_hp_max:>8,.0f} |{bd:>7s}  ")

    # ==================================================================
    #  TOP 20
    # ==================================================================
    top = df_days[df_days.has_ponta].nlargest(20, "cons_hp_total")

    print(f"\n\n  {'='*90}")
    print("  TOP 20 PIORES DIAS - MAIOR CONSUMO PONTA")
    print(f"  {'='*90}")
    hdr3 = (f"  {'#':<4s}|{'Dia':<12s}|{'DoW':<10s}|{'Mes':<5s}|"
            f"{'HP kWh':>10s}|{'BESS':>10s}|{'Residual':>10s}|{'Covered':>10s}")
    print(hdr3)
    print(f"  {'-'*75}")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        ds = r.dia.strftime("%Y-%m-%d")
        covered = r.cons_hp_total - r.cons_hp_residual
        pct = covered / r.cons_hp_total * 100 if r.cons_hp_total > 0 else 100
        print(f"  {i:<4d}|{ds}|{r.dow:<10s}|{r.mes:<5s}|"
              f" {_brl(r.cons_hp_total, 0):>8s} |"
              f" {_brl(covered, 0):>8s} |"
              f" {_brl(r.cons_hp_residual, 0):>8s} |"
              f" {pct:>8.1f}% ")

    # ==================================================================
    #  DISTRIBUICAO
    # ==================================================================
    hp_vals = df_days[df_days.has_ponta].cons_hp_total.values

    print(f"\n\n  {'='*72}")
    print("  DISTRIBUICAO DO CONSUMO PONTA DIARIO")
    print(f"  {'='*72}")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        v = np.percentile(hp_vals, p)
        ok = "ok" if v <= BESS_CAPACIDADE_KWH else "BESS!"
        print(f"    P{p:>2d}: {_brl(v, 0):>8s} kWh   {ok}")
    print(f"    Max: {_brl(hp_vals.max(), 0):>8s} kWh")
    bess_daily_e = BESS_POTENCIA_CARGA * (BESS_CARGA_FIM - BESS_CARGA_INICIO)
    print(
        f"    BESS: {_brl(BESS_CAPACIDADE_KWH, 0):>8s} kWh cap  /  {_brl(bess_daily_e, 0)} kWh/dia charge")

    # ==================================================================
    #  ANALISE FINANCEIRA
    # ==================================================================
    print(f"\n\n  {'='*72}")
    print("  ANALISE FINANCEIRA")
    print(f"  {'='*72}")

    def _analise(capex, eco, label):
        if eco <= 0:
            print(f"\n  {label}: economia <= 0, inviavel.")
            return
        payback = capex / eco
        cf = [-capex] + [eco] * VIDA_UTIL_ANOS
        vpl = sum(v / (1 + TAXA_DESCONTO)**t for t, v in enumerate(cf))
        roi = (eco * VIDA_UTIL_ANOS - capex) / capex * 100
        lo, hi = -0.5, 5.0
        for _ in range(200):
            m = (lo + hi) / 2
            s = sum(v / (1 + m)**t for t, v in enumerate(cf))
            if s > 0:
                lo = m
            else:
                hi = m
        tir = (lo + hi) / 2
        acum = 0.0
        pd_y = float(VIDA_UTIL_ANOS)
        for t in range(1, VIDA_UTIL_ANOS + 1):
            pvt = eco / (1 + TAXA_DESCONTO) ** t
            acum += pvt
            if acum >= capex:
                prev = acum - pvt
                pd_y = (t - 1) + (capex - prev) / pvt
                break
        print(f"\n  {label}")
        print(f"    CAPEX:              R$ {_brl(capex)}")
        print(f"    Economia anual:     R$ {_brl(eco)}")
        print(f"    Payback simples:    {payback:.1f} anos")
        print(f"    Payback descontado: {pd_y:.1f} anos")
        print(f"    TIR:                {tir*100:.1f}%")
        print(f"    VPL (10%):          R$ {_brl(vpl)}")
        print(f"    ROI ({VIDA_UTIL_ANOS} anos):       {roi:.0f}%")

    _analise(CAPEX_TOTAL, eco_total, "SOLAR + BESS (migracao VERDE)")
    _analise(CAPEX_SOLAR_ONLY, eco_solar, "SOMENTE SOLAR (mantem AZUL)")

    # ==================================================================
    #  EXPORTAR
    # ==================================================================
    export_cols = [
        "dia", "mes", "tipo", "dow", "has_ponta", "has_overflow",
        "cons_hp_total", "cons_hp_residual", "cons_fp_total", "cons_fp_net",
        "dem_hp_max", "dem_fp_max", "dem_hp_resid",
        "solar_saving", "bess_charge_kwh", "bess_dead",
    ]
    df_days[export_cols].to_csv(DATA_DIR / "bess_simulacao_diaria.csv",
                                index=False, float_format="%.2f")
    print(
        f"\n\n  Exportado: data/bess_simulacao_diaria.csv ({len(df_days)} dias)")
    pd.DataFrame(monthly).to_csv(DATA_DIR / "modelamento_anual_resultado.csv",
                                 index=False, float_format="%.2f")
    print("  Exportado: data/modelamento_anual_resultado.csv")

    # Timeline 15-min (para gráfico interativo)
    if all_timeline:
        df_tl = pd.DataFrame(all_timeline)
        df_tl.to_csv(DATA_DIR / "bess_timeline_15min.csv",
                     index=False, float_format="%.1f")
        print(
            f"  Exportado: data/bess_timeline_15min.csv ({len(df_tl)} slots)")

    return df_days, monthly


if __name__ == "__main__":
    compute_year()
