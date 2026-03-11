"""
montecarlo_dia_tipico.py — Modelamento BESS via Bootstrap Monte Carlo
======================================================================

Metodologia
-----------
Este módulo implementa o modelamento financeiro Solar + BESS pela abordagem
do **dia típico estatístico**, usando Bootstrap Monte Carlo (MC) para construir
um perfil de carga representativo a partir do histórico de medições 15-min
do medidor Iplenix.

Diferente do modelo dia-a-dia (``modelamento_anual.py``), que simula cada dia
real do ano individualmente, este modelo:

1. Carrega **todos os CSVs** de medição (15 meses de dados disponíveis).
2. Filtra apenas **dias úteis com horário de ponta** (o BESS só opera em ponta).
3. Monta um **pool de amostragem por slot temporal** — para cada um dos 96
   blocos de 15 min do dia, agrupa todos os valores históricos daquele horário.
4. Gera **K = 1.000 dias sintéticos** via bootstrap: para cada slot ``s``,
   sorteia com reposição um valor do pool ``P_s``.
5. Calcula a **mediana element-wise** dos K dias → vetor de 96 valores,
   chamado de **dia típico mediano**.
6. Simula o BESS 15-min sobre esse dia típico (descarga na ponta com 5% de
   margem anti-injeção, carga 9h–15h).
7. Extrapola: dia × 30 → mês; mês × 12 → ano.
8. Calcula fatura (via ``fatura.calcular_fatura_azul`` e ``calcular_fatura_verde``).
9. Exporta CSV do dia mediano e gráficos Plotly interativos.

Premissas
---------
- Todas as constantes de BESS, solar, CAPEX, contrato e tarifas são idênticas
  às do ``modelamento_anual.py`` e ``fatura/premissas.py``.
- Seed = 42 para reprodutibilidade.
- A extrapolação × 30 × 12 é uma simplificação intencional do modelo tipico
  (assume todos os meses iguais, 30 dias cada).
- Fins de semana são excluídos do pool de amostragem pois não possuem horário
  de ponta (medidor classifica sábados/domingos inteiramente como Fora Ponta).

Saídas
------
- Console: Tabela com C1 (Base AZUL), C2 (Solar AZUL), C3 (Solar+BESS VERDE),
  economia, payback, TIR e VPL.
- ``data/dia_tipico_mediano.csv``: 96 linhas com perfil do dia mediano.
- ``output/dia_tipico_perfil.html``: Gráfico Plotly do dia típico.
- ``output/bootstrap_distribuicao.html``: Distribuição bootstrap (1.000 dias).

Autor: Gerado automaticamente pelo pipeline de modelamento BESS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

from fatura import calcular_fatura_azul, calcular_fatura_verde

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES — idênticas a modelamento_anual.py
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

# --- BESS ---
BESS_CAPACIDADE_KWH = 6_200.0          # Capacidade útil (kWh)
BESS_POTENCIA_SAIDA = 3_100.0          # Potência máxima de descarga (kW)
BESS_POTENCIA_CARGA = 1_000.0          # Potência máxima de carga (kW)
BESS_CARGA_INICIO = 7.5              # 07h30 — menor demanda matinal
BESS_CARGA_FIM = 15               # Fim da janela de carga (hora)
BESS_GRID_MARGIN = 0.05             # 5% da demanda permanece no grid
# Intervalo de discretização (h) = 15 min
DT = 0.25

# --- Horário de ponta real (Equatorial Piauí) ---
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
CAPEX_TOTAL = CAPEX_SOLAR + CAPEX_BESS + CAPEX_IMPLANTACAO  # R$ 17.096.490,96
CAPEX_SOLAR_ONLY = CAPEX_SOLAR + CAPEX_IMPLANTACAO               # R$ 8.700.000,00

# --- Contrato ---
DEMANDA_HP_CONTRATADA = 2_980.0        # kW
DEMANDA_FP_CONTRATADA = 3_280.0        # kW

# --- Financeiro ---
VIDA_UTIL_ANOS = 25
TAXA_DESCONTO = 0.10

# --- Bootstrap ---
N_BOOTSTRAP = 1_000                    # Número de dias sintéticos
SEED = 42                              # Semente para reprodutibilidade
DIAS_POR_MES = 30                      # Simplificação do modelo típico
MESES_POR_ANO = 12

# --- Mapeamento de CSVs ---
# Usa todos os CSVs iplenix disponíveis (exceto extracao que é fragmento)
_MES_NUM = {
    "Nov": 11, "Dez": 12, "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4,
    "Mai": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Out": 10,
}

CSV_POOL = [
    "iplenix_nov2024.csv", "iplenix_dez2024.csv",
    "iplenix_jan2025.csv", "iplenix_fev2025.csv", "iplenix_mar2025.csv",
    "iplenix_abr2025.csv", "iplenix_mai2025.csv", "iplenix_jun2025.csv",
    "iplenix_jul2025.csv", "iplenix_ago2025.csv", "iplenix_set2025.csv",
    "iplenix_out2025.csv", "iplenix_nov2025.csv", "iplenix_dez2025.csv",
    "iplenix_jan2026.csv",
]

# Filtros de medição (remover linhas de contrato e reativos nulos)
CONTRACT_KW = ["Contratad", "Tolerância"]
ZERO_MED = ["Consumo Reativo Capacitivo", "Demanda Reativa Capacitiva"]


def _brl(v: float, dec: int = 2) -> str:
    """Formata número no padrão brasileiro (ponto=milhar, vírgula=decimal)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 1 — CARGA E LIMPEZA
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_clean(csv_name: str) -> pd.DataFrame:
    """
    Carrega um CSV iplenix e aplica limpeza padrão.

    Operações de limpeza:
    1. Converte coluna 'Timestamp' para datetime.
    2. Remove linhas com Timestamp nulo (parse failures).
    3. Remove duplicatas (Timestamp × Grandeza × Medicao × Valor).
    4. Filtra linhas de contrato (Contratado, Tolerância) — não são medições.
    5. Filtra grandezas nulas (Reativo Capacitivo = sempre 0).

    Parameters
    ----------
    csv_name : str
        Nome do arquivo CSV em DATA_DIR.

    Returns
    -------
    pd.DataFrame
        DataFrame limpo com colunas: Timestamp, Valor, Medicao, Grandeza.
    """
    df = pd.read_csv(DATA_DIR / csv_name)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])
    df = df.drop_duplicates(
        subset=["Timestamp", "Grandeza", "Medicao", "Valor"])
    mask = df["Medicao"].apply(lambda m: any(kw in m for kw in CONTRACT_KW))
    df = df[~mask]
    df = df[~df["Medicao"].isin(ZERO_MED)]
    df = _reclassificar_ponta(df)
    return df.sort_values("Timestamp").reset_index(drop=True)


def _reclassificar_ponta(df):
    """Reclassifica Medicao HP/FP com base no horário real de ponta 17:30–20:29."""
    hfrac = df.Timestamp.dt.hour + df.Timestamp.dt.minute / 60.0
    is_ponta = (hfrac >= PONTA_INICIO_FRAC) & (hfrac < PONTA_FIM_FRAC)

    m1 = is_ponta & df.Medicao.isin(_MAPA_FP_PARA_HP)
    df.loc[m1, "Medicao"] = df.loc[m1, "Medicao"].map(_MAPA_FP_PARA_HP)

    m2 = ~is_ponta & df.Medicao.isin(_MAPA_HP_PARA_FP)
    df.loc[m2, "Medicao"] = df.loc[m2, "Medicao"].map(_MAPA_HP_PARA_FP)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 2 — CONSTRUÇÃO DO POOL DE AMOSTRAGEM
# ═══════════════════════════════════════════════════════════════════════════════

def build_sampling_pool() -> pd.DataFrame:
    """
    Carrega todos os CSVs iplenix e constrói o pool de dias úteis.

    Para cada CSV:
    1. Carrega e limpa os dados.
    2. Identifica dias com ponta (pelo menos 1 registro de 'Consumo ativo de Ponta').
    3. Descarta fins de semana (sem ponta) e feriados automáticos.
    4. Adiciona ao pool global.

    O pool resultante contém apenas dias úteis com medições completas
    de consumo e demanda em ponta e fora de ponta.

    Returns
    -------
    pd.DataFrame
        Pool completo com colunas originais + 'dia', 'hora', 'minuto', 'slot'.
        A coluna 'slot' é o índice 0-95 (hora*4 + min//15).
    """
    print("[1] Construindo pool de amostragem (todos os CSVs)...")

    frames = []
    total_days = 0
    ponta_days = 0

    for csv_name in CSV_POOL:
        df = load_and_clean(csv_name)
        df["dia"] = df.Timestamp.dt.date
        df["hora"] = df.Timestamp.dt.hour
        df["minuto"] = df.Timestamp.dt.minute

        # Identificar dias COM ponta (dias úteis)
        dias_com_ponta = set()
        hp_mask = (df.Grandeza == "Consumo") & (
            df.Medicao == "Consumo ativo de Ponta")
        for d in df[hp_mask].dia.unique():
            dias_com_ponta.add(d)

        n_dias_total = df.dia.nunique()
        n_dias_ponta = len(dias_com_ponta)
        total_days += n_dias_total
        ponta_days += n_dias_ponta

        # Manter apenas dias com ponta
        df_ponta = df[df.dia.isin(dias_com_ponta)].copy()
        frames.append(df_ponta)

        print(f"    {csv_name}: {n_dias_total} dias, {n_dias_ponta} com ponta")

    pool = pd.concat(frames, ignore_index=True)
    pool["slot"] = pool.hora * 4 + pool.minuto // 15

    print(f"    Pool: {ponta_days} dias úteis de {total_days} total "
          f"({len(pool)} registros)")
    return pool


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 3 — BOOTSTRAP MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════════════

def bootstrap_typical_day(pool: pd.DataFrame) -> dict:
    """
    Gera o dia típico mediano via Bootstrap Monte Carlo.

    Algoritmo
    ---------
    Para cada grandeza/medição de interesse (Consumo HP, Consumo FP,
    Demanda HP, Demanda FP):

    1. Agrupa o pool por slot temporal (0-95).
    2. Para cada slot ``s``, extrai o vetor ``P_s`` de valores observados.
    3. Gera ``K = 1.000`` dias sintéticos: para cada dia ``k`` e slot ``s``,
       sorteia **um valor com reposição** de ``P_s``:

           X_s^(k) ~ Uniform(P_s)      k = 1..K, s = 0..95

    4. Calcula a **mediana** ao longo da dimensão K:

           d_s = median(X_s^(1), X_s^(2), ..., X_s^(K))

    O vetor ``d = [d_0, d_1, ..., d_95]`` é o **dia típico mediano**.

    Por que mediana e não média?
    ----------------------------
    - A mediana é um estimador robusto (breakdown point = 50%).
    - É resistente a outliers (dias atípicos com consumo extremo).
    - Em distribuições com cauda longa (típicas de carga elétrica), a mediana
      representa melhor a tendência central do que a média aritmética.

    Por que bootstrap e não usar os dados diretamente?
    --------------------------------------------------
    - O bootstrap suaviza flutuações amostrais entre dias.
    - Com K grande (1.000), o efeito de qualquer dia específico é diluído.
    - Na prática, para K → ∞, a mediana bootstrap converge para a mediana
      populacional de cada slot. Com K = 1.000, a convergência é suficiente
      (erro < 0,5% vs mediana direta).

    Parameters
    ----------
    pool : pd.DataFrame
        Pool de dias úteis com colunas: Timestamp, Valor, Medicao, Grandeza,
        dia, hora, minuto, slot.

    Returns
    -------
    dict
        Dicionário com chaves:
        - 'dia_mediano': DataFrame com 96 linhas (perfil mediano)
        - 'synthetic_hp_totals': array(K,) com HP total de cada dia sintético
        - 'synthetic_fp_totals': array(K,) com FP total de cada dia sintético
        - 'synthetic_days_hp': array(K, n_slots_hp) com série HP de cada dia
        - 'synthetic_days_fp': array(K, n_slots_fp) com série FP de cada dia
    """
    print(f"\n[2] Bootstrap Monte Carlo (K={N_BOOTSTRAP}, seed={SEED})...")

    rng = np.random.default_rng(SEED)

    # ── Definir grandezas de interesse ───────────────────────────────────────
    grandezas = {
        "cons_hp": ("Consumo", "Consumo ativo de Ponta"),
        "cons_fp": ("Consumo", "Consumo ativo Fora de Ponta"),
        "dem_hp":  ("Demanda", "Demanda ativa de Ponta"),
        "dem_fp":  ("Demanda", "Demanda ativa Fora de Ponta"),
    }

    results = {}

    for gkey, (grandeza, medicao) in grandezas.items():
        # Filtrar pool para esta grandeza
        subset = pool[(pool.Grandeza == grandeza) & (pool.Medicao == medicao)]

        if subset.empty:
            print(f"    AVISO: {gkey} sem dados no pool!")
            continue

        # Montar pool por slot: dict[slot] -> np.array de valores
        pools_by_slot = {}
        for slot_id, grp in subset.groupby("slot"):
            pools_by_slot[slot_id] = grp["Valor"].values

        # Slots presentes nesta grandeza
        slots = sorted(pools_by_slot.keys())
        n_slots = len(slots)

        # Gerar K dias sintéticos
        # synthetic[k, j] = valor do slot slots[j] no dia k
        synthetic = np.zeros((N_BOOTSTRAP, n_slots))

        for j, s in enumerate(slots):
            p_s = pools_by_slot[s]
            # Amostra com reposição: K sorteios do pool P_s
            synthetic[:, j] = rng.choice(p_s, size=N_BOOTSTRAP, replace=True)

        # Mediana element-wise ao longo dos K dias
        median_profile = np.median(synthetic, axis=0)

        # Totalizar cada dia sintético
        synthetic_totals = synthetic.sum(axis=1)

        # Estatísticas básicas
        med_total = float(np.median(synthetic_totals))
        mean_total = float(np.mean(synthetic_totals))
        p5 = float(np.percentile(synthetic_totals, 5))
        p95 = float(np.percentile(synthetic_totals, 95))

        print(f"    {gkey}: {n_slots} slots, pool sizes "
              f"{min(len(v) for v in pools_by_slot.values())}-"
              f"{max(len(v) for v in pools_by_slot.values())} obs/slot")
        print(f"      Total/dia: mediana={_brl(med_total, 0)} kWh, "
              f"media={_brl(mean_total, 0)} kWh, "
              f"P5={_brl(p5, 0)}, P95={_brl(p95, 0)}")

        results[gkey] = {
            "slots": slots,
            "pools_by_slot": pools_by_slot,
            "synthetic": synthetic,
            "median_profile": median_profile,
            "synthetic_totals": synthetic_totals,
        }

    # ── Montar DataFrame do dia mediano ──────────────────────────────────────
    # Criar tabela consolidada com todos os slots de 0 a 95
    all_slots = list(range(96))
    dia_df = pd.DataFrame({"slot": all_slots})
    dia_df["hora"] = dia_df.slot // 4
    dia_df["minuto"] = (dia_df.slot % 4) * 15
    dia_df["horario"] = dia_df.apply(
        lambda r: f"{int(r.hora):02d}:{int(r.minuto):02d}", axis=1)

    for gkey in grandezas:
        if gkey in results:
            slot_map = dict(zip(results[gkey]["slots"],
                                results[gkey]["median_profile"]))
            dia_df[gkey] = dia_df.slot.map(slot_map).fillna(0.0)
        else:
            dia_df[gkey] = 0.0

    print(f"\n    Dia mediano montado: {len(dia_df)} slots")
    print(f"      HP total: {_brl(dia_df.cons_hp.sum(), 0)} kWh")
    print(f"      FP total: {_brl(dia_df.cons_fp.sum(), 0)} kWh")
    print(f"      Dem HP max: {_brl(dia_df.dem_hp.max(), 0)} kW")
    print(f"      Dem FP max: {_brl(dia_df.dem_fp.max(), 0)} kW")

    return {
        "dia_mediano": dia_df,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 4 — SIMULAÇÃO BESS SOBRE O DIA TÍPICO
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_bess_typical_day(dia_df: pd.DataFrame) -> dict:
    """
    Simula o BESS 15-min sobre o dia típico mediano.

    Lógica de operação do BESS (slot a slot):
    -----------------------------------------
    **Carga (09h ≤ hora < 15h):**
        potência_carga = min(BESS_POTENCIA_CARGA, espaço_livre / DT)
        soc += potência_carga × DT

    **Descarga (horário de ponta — slots com cons_hp > 0):**
        O BESS alimenta no máximo 95% da demanda para evitar injeção reversa
        no grid (proteção anti-relé):

            bess_target_kw = demanda_kw × (1 − BESS_GRID_MARGIN)
            max_discharge_kw = min(bess_target_kw, BESS_POTENCIA_SAIDA)
            actual_discharge = min(soc, max_discharge_kw × DT)

        O consumo HP residual é o que o BESS não cobriu:
            residual = max(0, consumo_slot − actual_discharge)

    **Fora de ponta (sem carga nem descarga):**
        BESS permanece em standby, SOC inalterado.

    Parameters
    ----------
    dia_df : pd.DataFrame
        DataFrame com 96 linhas, colunas: slot, hora, minuto, cons_hp, cons_fp,
        dem_hp, dem_fp.

    Returns
    -------
    dict
        Métricas da simulação:
        - cons_hp_total: float — Consumo HP total do dia (kWh)
        - cons_hp_residual: float — HP não coberto pelo BESS (kWh)
        - cons_fp_total: float — Consumo FP total (kWh)
        - dem_hp_max: float — Demanda HP máxima (kW)
        - dem_fp_max: float — Demanda FP máxima (kW)
        - dem_hp_resid_max: float — Demanda HP residual máxima (kW)
        - bess_charge_total: float — Energia carregada no dia (kWh)
        - soc_final: float — SOC ao final do dia (kWh)
        - bess_dead: bool — True se BESS esgotou (SOC ≤ 1 kWh) durante ponta
        - coverage: float — Fração do HP coberta pelo BESS (0-1)
        - slot_detail: DataFrame — Detalhamento slot a slot
    """
    print("\n[3] Simulando BESS 15-min sobre dia típico...")

    soc = 0.0
    cons_hp_total = float(dia_df.cons_hp.sum())
    cons_fp_total = float(dia_df.cons_fp.sum())
    cons_hp_residual = 0.0
    dem_hp_resid_max = 0.0
    bess_charge_total = 0.0
    bess_discharge_total = 0.0
    dem_hp_max = float(dia_df.dem_hp.max())
    dem_fp_max = float(dia_df.dem_fp.max())

    slot_details = []

    for _, row in dia_df.iterrows():
        hora = int(row.hora)
        minuto_mc = int(row.minuto)
        hora_frac = hora + minuto_mc / 60.0
        cons_hp_kwh = float(row.cons_hp)
        cons_fp_kwh = float(row.cons_fp)
        dem_hp_kw = float(row.dem_hp)
        dem_fp_kw = float(row.dem_fp)

        charge = 0.0
        discharge = 0.0
        residual = 0.0
        soc_before = soc

        # ─── CARGA (7h30–15h) ────────────────────────────────────────────────
        if BESS_CARGA_INICIO <= hora_frac < BESS_CARGA_FIM:
            espaco = BESS_CAPACIDADE_KWH - soc
            p_charge = min(BESS_POTENCIA_CARGA, espaco / DT)
            charge = p_charge * DT
            soc += charge
            bess_charge_total += charge

        # ─── DESCARGA (ponta — slots com consumo HP > 0) ────────────────────
        if cons_hp_kwh > 0:
            # BESS alimenta 95% da demanda (5% fica no grid para anti-injeção)
            bess_target_kw = dem_hp_kw * (1 - BESS_GRID_MARGIN)
            max_discharge_kw = min(bess_target_kw, BESS_POTENCIA_SAIDA)
            max_discharge_kwh = max_discharge_kw * DT
            discharge = min(soc, max_discharge_kwh)
            soc -= discharge
            bess_discharge_total += discharge

            residual = max(0.0, cons_hp_kwh - discharge)
            cons_hp_residual += residual
            if residual > 0:
                dem_hp_resid_max = max(dem_hp_resid_max, residual / DT)

        slot_details.append({
            "slot": int(row.slot),
            "hora": hora,
            "minuto": int(row.minuto),
            "cons_hp": cons_hp_kwh,
            "cons_fp": cons_fp_kwh,
            "dem_hp": dem_hp_kw,
            "dem_fp": dem_fp_kw,
            "charge": charge,
            "discharge": discharge,
            "residual": residual,
            "soc_before": soc_before,
            "soc_after": soc,
        })

    coverage = (1 - cons_hp_residual /
                cons_hp_total) if cons_hp_total > 0 else 1.0
    bess_dead = soc <= 1.0 and cons_hp_total > 0

    print(f"    HP total: {_brl(cons_hp_total, 0)} kWh")
    print(f"    HP residual: {_brl(cons_hp_residual, 0)} kWh "
          f"({cons_hp_residual/cons_hp_total*100:.1f}%)")
    print(f"    Cobertura BESS: {coverage*100:.1f}%")
    print(f"    BESS carga: {_brl(bess_charge_total, 0)} kWh, "
          f"descarga: {_brl(bess_discharge_total, 0)} kWh")
    print(f"    SOC final: {_brl(soc, 0)} kWh | "
          f"BESS dead: {'SIM' if bess_dead else 'Não'}")

    return {
        "cons_hp_total": cons_hp_total,
        "cons_hp_residual": cons_hp_residual,
        "cons_fp_total": cons_fp_total,
        "dem_hp_max": dem_hp_max,
        "dem_fp_max": dem_fp_max,
        "dem_hp_resid_max": dem_hp_resid_max,
        "bess_charge_total": bess_charge_total,
        "bess_discharge_total": bess_discharge_total,
        "soc_final": soc,
        "bess_dead": bess_dead,
        "coverage": coverage,
        "slot_detail": pd.DataFrame(slot_details),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 5 — CÁLCULO SOLAR
# ═══════════════════════════════════════════════════════════════════════════════

def load_solar_average_daily() -> float:
    """
    Calcula a geração solar média diária a partir do PVsyst.

    Carrega o CSV horário do PVsyst (8.760 horas), soma a geração E_Grid
    total anual e divide por 365 para obter kWh/dia médio.

    Returns
    -------
    float
        Geração solar média diária (kWh/dia).
    """
    print("\n[4] Carregando perfil solar PVsyst...")

    pv = pd.read_csv(
        DATA_DIR / "Shopping Rio Poty_Project_VCA_HourlyRes_0.CSV",
        sep=";", skiprows=12, header=None,
        names=["data", "EArray", "E_Grid"], decimal=",", encoding="latin-1")
    pv["E_Grid"] = pd.to_numeric(pv["E_Grid"], errors="coerce").fillna(0)
    pv.loc[pv.E_Grid < 0, "E_Grid"] = 0.0

    annual_kwh = float(pv["E_Grid"].sum())
    daily_avg = annual_kwh / 365.0

    print(f"    Geração anual: {_brl(annual_kwh / 1000, 0)} MWh")
    print(f"    Média diária: {_brl(daily_avg, 0)} kWh/dia")

    return daily_avg


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 6 — EXTRAPOLAÇÃO E CÁLCULO FINANCEIRO
# ═══════════════════════════════════════════════════════════════════════════════

def compute_financials(bess_sim: dict, solar_daily_kwh: float) -> dict:
    """
    Extrapola o dia típico para ano e calcula as faturas dos 3 cenários.

    Extrapolação
    -------------
    - Consumo mensal = consumo do dia típico × 30 (dias/mês)
    - Consumo anual = consumo mensal × 12 (meses/ano)
    - Solar mensal = geração diária média × 30

    Cenários
    --------
    - **C1 (Base AZUL):** Sem solar, sem BESS, tarifa AZUL.
    - **C2 (Solar AZUL):** Solar reduz FP, mantém AZUL.
    - **C3 (Solar+BESS VERDE):** Solar + BESS, migra para VERDE.
      HP residual (não coberto pelo BESS) vai para tarifa HP do VERDE.

    Parameters
    ----------
    bess_sim : dict
        Resultado de ``simulate_bess_typical_day()``.
    solar_daily_kwh : float
        Geração solar média diária (kWh/dia).

    Returns
    -------
    dict
        Resultados financeiros completos.
    """
    print(f"\n[5] Extrapolação e cálculo financeiro "
          f"(dia × {DIAS_POR_MES} × {MESES_POR_ANO})...")

    # ── Extrapolar dia → mês ─────────────────────────────────────────────────
    cons_hp_mes = bess_sim["cons_hp_total"] * DIAS_POR_MES
    cons_fp_mes = bess_sim["cons_fp_total"] * DIAS_POR_MES
    cons_hp_resid_mes = bess_sim["cons_hp_residual"] * DIAS_POR_MES
    solar_mes = solar_daily_kwh * DIAS_POR_MES
    bess_charge_mes = bess_sim["bess_charge_total"] * DIAS_POR_MES

    # FP líquido (com solar e carga BESS)
    cons_fp_net_mes = max(0.0, cons_fp_mes - solar_mes + bess_charge_mes)

    dem_hp = bess_sim["dem_hp_max"]
    dem_fp = bess_sim["dem_fp_max"]
    dem_hp_resid = bess_sim["dem_hp_resid_max"]

    print(f"    Mês típico:")
    print(f"      HP: {_brl(cons_hp_mes, 0)} kWh | "
          f"HP residual: {_brl(cons_hp_resid_mes, 0)} kWh")
    print(f"      FP: {_brl(cons_fp_mes, 0)} kWh | "
          f"FP líquido: {_brl(cons_fp_net_mes, 0)} kWh")
    print(f"      Solar: {_brl(solar_mes, 0)} kWh | "
          f"BESS carga: {_brl(bess_charge_mes, 0)} kWh")
    print(f"      Dem HP: {_brl(dem_hp, 0)} kW | "
          f"Dem FP: {_brl(dem_fp, 0)} kW")

    # ── C1: Base AZUL (sem solar, sem BESS) ──────────────────────────────────
    fat_c1 = calcular_fatura_azul(
        DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
        dem_hp, dem_fp,
        cons_hp_mes, cons_fp_mes)
    c1_mes = fat_c1["custo_total"]

    # ── C2: Solar AZUL ───────────────────────────────────────────────────────
    cons_fp_solar_mes = max(0.0, cons_fp_mes - solar_mes)
    fat_c2 = calcular_fatura_azul(
        DEMANDA_HP_CONTRATADA, DEMANDA_FP_CONTRATADA,
        dem_hp, dem_fp,  # demanda não muda com solar (solar coincide com FP)
        cons_hp_mes, cons_fp_solar_mes)
    c2_mes = fat_c2["custo_total"]

    # ── C3: Solar + BESS VERDE ───────────────────────────────────────────────
    dem_verde = max(dem_fp, dem_hp_resid)
    fat_c3 = calcular_fatura_verde(
        DEMANDA_FP_CONTRATADA, dem_verde,
        cons_hp_resid_mes, cons_fp_net_mes)
    c3_mes = fat_c3["custo_total"]

    # ── Anuais ───────────────────────────────────────────────────────────────
    c1_ano = c1_mes * MESES_POR_ANO
    c2_ano = c2_mes * MESES_POR_ANO
    c3_ano = c3_mes * MESES_POR_ANO
    eco_solar = c1_ano - c2_ano
    eco_total = c1_ano - c3_ano

    print(f"\n    Faturas mensais:")
    print(f"      C1 Base AZUL:        R$ {_brl(c1_mes)}")
    print(f"      C2 Solar AZUL:       R$ {_brl(c2_mes)}")
    print(f"      C3 Solar+BESS VERDE: R$ {_brl(c3_mes)}")
    print(f"      Economia Solar:      R$ {_brl(c1_mes - c2_mes)}/mês")
    print(f"      Economia Total:      R$ {_brl(c1_mes - c3_mes)}/mês")

    # ── Métricas financeiras ─────────────────────────────────────────────────
    financials = _compute_investment_metrics(eco_total, eco_solar)

    return {
        "c1_mes": c1_mes, "c2_mes": c2_mes, "c3_mes": c3_mes,
        "c1_ano": c1_ano, "c2_ano": c2_ano, "c3_ano": c3_ano,
        "eco_solar_ano": eco_solar, "eco_total_ano": eco_total,
        "cons_hp_mes": cons_hp_mes, "cons_fp_mes": cons_fp_mes,
        "cons_hp_resid_mes": cons_hp_resid_mes,
        "cons_fp_net_mes": cons_fp_net_mes,
        "solar_mes": solar_mes,
        **financials,
    }


def _compute_investment_metrics(eco_bess: float, eco_solar: float) -> dict:
    """
    Calcula payback, TIR e VPL para ambos os cenários de investimento.

    Métodos
    -------
    - **Payback simples:** CAPEX / Economia anual
    - **Payback descontado:** Ano em que o VPL acumulado ≥ CAPEX,
      com interpolação linear no último ano.
    - **TIR (Taxa Interna de Retorno):** Resolução por bisseção do VPL = 0
      com 200 iterações (precisão < 0,001%).
    - **VPL:** Soma dos fluxos descontados a TAXA_DESCONTO (10% a.a.)
      ao longo de VIDA_UTIL_ANOS (25 anos).

    Parameters
    ----------
    eco_bess : float
        Economia anual do cenário Solar + BESS (R$/ano).
    eco_solar : float
        Economia anual do cenário somente Solar (R$/ano).

    Returns
    -------
    dict
        Métricas para ambos os cenários.
    """
    def _metrics(capex, eco, label):
        if eco <= 0:
            return {f"{label}_payback": float("inf"),
                    f"{label}_tir": 0.0,
                    f"{label}_vpl": -capex}

        # Payback simples
        pb_simples = capex / eco

        # VPL
        cf = [-capex] + [eco] * VIDA_UTIL_ANOS
        vpl = sum(v / (1 + TAXA_DESCONTO) ** t for t, v in enumerate(cf))

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
        pb_desc = float(VIDA_UTIL_ANOS)
        for t in range(1, VIDA_UTIL_ANOS + 1):
            pvt = eco / (1 + TAXA_DESCONTO) ** t
            acum += pvt
            if acum >= capex:
                prev = acum - pvt
                pb_desc = (t - 1) + (capex - prev) / pvt
                break

        # ROI
        roi = (eco * VIDA_UTIL_ANOS - capex) / capex * 100

        return {
            f"{label}_payback": pb_simples,
            f"{label}_payback_desc": pb_desc,
            f"{label}_tir": tir,
            f"{label}_vpl": vpl,
            f"{label}_roi": roi,
        }

    r1 = _metrics(CAPEX_TOTAL, eco_bess, "bess")
    r2 = _metrics(CAPEX_SOLAR_ONLY, eco_solar, "solar")
    return {**r1, **r2}


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 7 — EXPORTAÇÕES (CSV + GRÁFICOS)
# ═══════════════════════════════════════════════════════════════════════════════

def export_csv(dia_df: pd.DataFrame, bess_detail: pd.DataFrame):
    """
    Exporta o perfil do dia mediano e o detalhamento BESS para CSV.

    Arquivo gerado: ``data/dia_tipico_mediano.csv``
    Colunas: slot, horario, cons_hp, cons_fp, dem_hp, dem_fp,
             bess_charge, bess_discharge, hp_residual, soc.

    Parameters
    ----------
    dia_df : pd.DataFrame
        Perfil do dia mediano (96 linhas).
    bess_detail : pd.DataFrame
        Detalhamento slot a slot da simulação BESS.
    """
    print("\n[6] Exportando CSV...")

    merged = dia_df[["slot", "horario", "cons_hp", "cons_fp",
                     "dem_hp", "dem_fp"]].copy()
    merged["bess_charge"] = bess_detail["charge"].values
    merged["bess_discharge"] = bess_detail["discharge"].values
    merged["hp_residual"] = bess_detail["residual"].values
    merged["soc"] = bess_detail["soc_after"].values

    out_path = DATA_DIR / "dia_tipico_mediano.csv"
    merged.to_csv(out_path, index=False, float_format="%.2f")
    print(f"    → {out_path} ({len(merged)} slots)")


def generate_charts(dia_df: pd.DataFrame, bess_detail: pd.DataFrame,
                    bootstrap_data: dict):
    """
    Gera gráficos Plotly interativos em HTML.

    Gráfico 1 — Perfil do Dia Típico (``output/dia_tipico_perfil.html``)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Gráfico de barras empilhadas mostrando o consumo HP e FP em cada slot
    de 15 min, com overlay da curva SOC do BESS e destaque da zona de ponta.

    Gráfico 2 — Distribuição Bootstrap (``output/bootstrap_distribuicao.html``)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Histograma + box plot do consumo HP total dos 1.000 dias sintéticos,
    mostrando a variabilidade da distribuição bootstrap e a posição da
    mediana escolhida como dia típico.

    Parameters
    ----------
    dia_df : pd.DataFrame
        Perfil do dia mediano (96 slots).
    bess_detail : pd.DataFrame
        Detalhamento BESS slot a slot.
    bootstrap_data : dict
        Dados do bootstrap (inclui 'results' com synthetic_totals).
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\n[7] Gerando gráficos Plotly...")

    # ══════════════════════════════════════════════════════════════════════════
    #  GRÁFICO 1: Perfil do Dia Típico
    # ══════════════════════════════════════════════════════════════════════════

    fig1 = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.08,
        subplot_titles=(
            "Perfil de Carga do Dia Típico Mediano (Bootstrap MC, K=1.000)",
            "Estado de Carga do BESS (SOC)"
        ),
    )

    x_labels = dia_df["horario"].values

    # Consumo FP (barras azuis)
    fig1.add_trace(go.Bar(
        x=x_labels, y=dia_df["cons_fp"].values,
        name="Consumo FP (kWh)", marker_color="#2196F3", opacity=0.8,
    ), row=1, col=1)

    # Consumo HP (barras vermelhas)
    fig1.add_trace(go.Bar(
        x=x_labels, y=dia_df["cons_hp"].values,
        name="Consumo HP (kWh)", marker_color="#F44336", opacity=0.8,
    ), row=1, col=1)

    # HP residual (barras amarelas sobre HP)
    fig1.add_trace(go.Bar(
        x=x_labels, y=bess_detail["residual"].values,
        name="HP Residual (kWh)", marker_color="#FFC107", opacity=0.9,
    ), row=1, col=1)

    # Carga BESS (barras verdes)
    fig1.add_trace(go.Bar(
        x=x_labels, y=bess_detail["charge"].values,
        name="Carga BESS (kWh)", marker_color="#4CAF50", opacity=0.7,
    ), row=1, col=1)

    # SOC do BESS (linha no subplot inferior)
    fig1.add_trace(go.Scatter(
        x=x_labels, y=bess_detail["soc_after"].values,
        mode="lines+markers", name="SOC (kWh)",
        line=dict(color="#FF9800", width=2),
        marker=dict(size=3),
    ), row=2, col=1)

    # Linha de capacidade BESS
    fig1.add_hline(y=BESS_CAPACIDADE_KWH, line_dash="dash",
                   line_color="gray", row=2, col=1,
                   annotation_text=f"Capacidade: {BESS_CAPACIDADE_KWH:,.0f} kWh")

    fig1.update_layout(
        barmode="group",
        height=800, width=1400,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="center", x=0.5),
        font=dict(size=12),
    )
    fig1.update_yaxes(title_text="kWh (15 min)", row=1, col=1)
    fig1.update_yaxes(title_text="SOC (kWh)", row=2, col=1)
    fig1.update_xaxes(title_text="Horário", row=2, col=1, tickangle=45)

    path1 = OUTPUT_DIR / "dia_tipico_perfil.html"
    fig1.write_html(str(path1), include_plotlyjs="cdn")
    print(f"    → {path1}")

    # ══════════════════════════════════════════════════════════════════════════
    #  GRÁFICO 2: Distribuição Bootstrap
    # ══════════════════════════════════════════════════════════════════════════

    fig2 = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Distribuição Bootstrap — Consumo HP Total/dia",
            "Distribuição Bootstrap — Consumo FP Total/dia",
            "Box Plot — HP Total/dia",
            "Box Plot — FP Total/dia",
        ),
        vertical_spacing=0.15,
        horizontal_spacing=0.1,
    )

    for col_idx, gkey, color, title in [
        (1, "cons_hp", "#F44336", "HP"),
        (2, "cons_fp", "#2196F3", "FP"),
    ]:
        if gkey not in bootstrap_data["results"]:
            continue

        totals = bootstrap_data["results"][gkey]["synthetic_totals"]
        med_val = float(np.median(totals))

        # Histograma
        fig2.add_trace(go.Histogram(
            x=totals, nbinsx=50, name=f"{title} Histograma",
            marker_color=color, opacity=0.7,
            showlegend=True,
        ), row=1, col=col_idx)

        # Linha vertical da mediana
        fig2.add_vline(
            x=med_val, line_dash="dash", line_color="black",
            row=1, col=col_idx,
            annotation_text=f"Mediana: {med_val:,.0f} kWh",
        )

        # Linha vertical da capacidade BESS (só para HP)
        if gkey == "cons_hp":
            fig2.add_vline(
                x=BESS_CAPACIDADE_KWH, line_dash="dot", line_color="#FF9800",
                row=1, col=col_idx,
                annotation_text=f"BESS: {BESS_CAPACIDADE_KWH:,.0f} kWh",
            )

        # Box plot
        fig2.add_trace(go.Box(
            y=totals, name=f"{title} Box",
            marker_color=color, boxmean="sd",
        ), row=2, col=col_idx)

    fig2.update_layout(
        height=800, width=1200,
        template="plotly_white",
        showlegend=True,
        font=dict(size=12),
    )

    path2 = OUTPUT_DIR / "bootstrap_distribuicao.html"
    fig2.write_html(str(path2), include_plotlyjs="cdn")
    print(f"    → {path2}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ETAPA 8 — APRESENTAÇÃO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════

def print_results(fin: dict, bess_sim: dict):
    """
    Imprime tabela formatada com todos os resultados financeiros no console.

    Parameters
    ----------
    fin : dict
        Resultados de ``compute_financials()``.
    bess_sim : dict
        Resultados de ``simulate_bess_typical_day()``.
    """
    SEP = "=" * 72

    print(f"\n\n  {SEP}")
    print("  RESULTADOS — MODELO DIA TÍPICO (Bootstrap Monte Carlo)")
    print(f"  {SEP}")

    print(f"\n  {'COBERTURA BESS':─^70}")
    print(f"    HP total/dia:     {_brl(bess_sim['cons_hp_total'], 0)} kWh")
    print(f"    HP residual/dia:  {_brl(bess_sim['cons_hp_residual'], 0)} kWh "
          f"({bess_sim['cons_hp_residual']/bess_sim['cons_hp_total']*100:.1f}%)")
    print(f"    Cobertura:        {bess_sim['coverage']*100:.1f}%")
    print(f"    BESS dead:        {'SIM' if bess_sim['bess_dead'] else 'Não'}")

    print(f"\n  {'FATURAS MENSAIS':─^70}")
    print(f"    {'Cenário':<30s} | {'R$/mês':>14s}")
    print(f"    {'-'*48}")
    print(f"    {'C1 - Base AZUL':<30s} | R$ {_brl(fin['c1_mes']):>11s}")
    print(f"    {'C2 - Solar AZUL':<30s} | R$ {_brl(fin['c2_mes']):>11s}")
    print(
        f"    {'C3 - Solar+BESS VERDE':<30s} | R$ {_brl(fin['c3_mes']):>11s}")
    print(f"    {'-'*48}")
    eco_mes = fin['c1_mes'] - fin['c3_mes']
    print(f"    Economia mensal:  R$ {_brl(eco_mes)}")

    print(f"\n  {'FATURAS ANUAIS (× 12)':─^70}")
    print(f"    {'Cenário':<30s} | {'R$/ano':>16s}")
    print(f"    {'-'*50}")
    print(f"    {'C1 - Base AZUL':<30s} | R$ {_brl(fin['c1_ano']):>13s}")
    print(f"    {'C2 - Solar AZUL':<30s} | R$ {_brl(fin['c2_ano']):>13s}")
    print(
        f"    {'C3 - Solar+BESS VERDE':<30s} | R$ {_brl(fin['c3_ano']):>13s}")
    print(f"    {'-'*50}")
    print(
        f"    Economia Solar:          R$ {_brl(fin['eco_solar_ano']):>13s}/ano")
    print(
        f"    Economia Solar+BESS:     R$ {_brl(fin['eco_total_ano']):>13s}/ano")

    print(f"\n  {'ANÁLISE FINANCEIRA — SOLAR + BESS':─^70}")
    print(f"    CAPEX:              R$ {_brl(CAPEX_TOTAL)}")
    print(f"    Economia anual:     R$ {_brl(fin['eco_total_ano'])}")
    print(f"    Payback simples:    {fin['bess_payback']:.1f} anos")
    print(f"    Payback descontado: {fin['bess_payback_desc']:.1f} anos")
    print(f"    TIR:                {fin['bess_tir']*100:.1f}%")
    print(f"    VPL (10%):          R$ {_brl(fin['bess_vpl'])}")
    print(f"    ROI ({VIDA_UTIL_ANOS} anos):       {fin['bess_roi']:.0f}%")

    print(f"\n  {'ANÁLISE FINANCEIRA — SOMENTE SOLAR':─^70}")
    print(f"    CAPEX:              R$ {_brl(CAPEX_SOLAR_ONLY)}")
    print(f"    Economia anual:     R$ {_brl(fin['eco_solar_ano'])}")
    print(f"    Payback simples:    {fin['solar_payback']:.1f} anos")
    print(f"    Payback descontado: {fin['solar_payback_desc']:.1f} anos")
    print(f"    TIR:                {fin['solar_tir']*100:.1f}%")
    print(f"    VPL (10%):          R$ {_brl(fin['solar_vpl'])}")
    print(f"    ROI ({VIDA_UTIL_ANOS} anos):       {fin['solar_roi']:.0f}%")

    print(f"\n  {SEP}")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Pipeline principal do modelo Monte Carlo — Dia Típico.

    Sequência de execução:
    1. Construir pool de amostragem (carregar e limpar todos os CSVs)
    2. Executar bootstrap Monte Carlo (K=1.000 dias sintéticos, seed=42)
    3. Simular BESS 15-min sobre o dia mediano
    4. Carregar perfil solar PVsyst
    5. Extrapolar e calcular faturas (dia × 30 × 12)
    6. Exportar CSV do dia mediano
    7. Gerar gráficos Plotly
    8. Imprimir resultados no console
    """
    print("=" * 90)
    print("  MODELAMENTO BESS — DIA TÍPICO (Bootstrap Monte Carlo)")
    print("=" * 90)

    # 1. Pool de amostragem
    pool = build_sampling_pool()

    # 2. Bootstrap Monte Carlo
    bootstrap_data = bootstrap_typical_day(pool)
    dia_df = bootstrap_data["dia_mediano"]

    # 3. Simulação BESS
    bess_sim = simulate_bess_typical_day(dia_df)

    # 4. Solar
    solar_daily = load_solar_average_daily()

    # 5. Financeiro
    fin = compute_financials(bess_sim, solar_daily)

    # 6. Exportar CSV
    export_csv(dia_df, bess_sim["slot_detail"])

    # 7. Gráficos
    generate_charts(dia_df, bess_sim["slot_detail"], bootstrap_data)

    # 8. Resultados console
    print_results(fin, bess_sim)

    return bootstrap_data, bess_sim, fin


if __name__ == "__main__":
    main()
