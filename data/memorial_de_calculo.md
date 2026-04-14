# Memorial de Cálculo — Simulação BESS + Solar

**Gerado automaticamente** a partir do código-fonte de `kira-bess-modelamento`
**Commit:** `16a350a8b69838b0b82b737a6e61d064e86be8aa`
**Data de geração:** 2026-03-11
**Unidade Consumidora:** Shopping Rio Poty — Teresina/PI

---

## 1. Sistema Proposto

### 1.1 BESS (Battery Energy Storage System)

| Parâmetro | Valor | Variável no código |
|---|---|---|
| Capacidade útil | 6.200 kWh | `BESS_CAPACIDADE_KWH` |
| Potência de descarga | 3.100 kW | `BESS_POTENCIA_SAIDA` |
| Potência de carga | 1.000 kW | `BESS_POTENCIA_CARGA` |
| Janela de carga | 07h30–15h00 (30 slots de 15 min) | `BESS_CARGA_INICIO=7.5`, `BESS_CARGA_FIM=15` |
| Energia máx. carga/dia | 7.500 kWh (limitada pela cap de 6.200 kWh) | `BESS_POTENCIA_CARGA × (BESS_CARGA_FIM − BESS_CARGA_INICIO)` |
| Janela de ponta | 17h30–20h29 (12 slots de 15 min) | `PONTA_INICIO_FRAC=17.5`, `PONTA_FIM_FRAC=20.5` |
| Margem anti-injeção | 5% da demanda permanece no grid | `BESS_GRID_MARGIN=0.05` |
| Resolução temporal | 15 min (0,25 h) | `DT=0.25` |
| Cap demanda FP (fins de semana) | 2.800 kW | `BESS_WEEKEND_DEM_CAP` |

**Comportamento em fins de semana:** Nos fins de semana (sáb/dom), o BESS opera em modo **peak-shaving FP**. Toda a carga é classificada como Fora de Ponta. O BESS carrega durante a janela 07h30–15h se a demanda líquida (FP − solar) estiver abaixo de 2.800 kW, e descarrega sempre que a demanda líquida exceder 2.800 kW em qualquer slot. O objetivo é manter a demanda FP ≤ 2.800 kW.

### 1.2 Solar Fotovoltaico

| Parâmetro | Valor | Variável no código |
|---|---|---|
| Potência instalada | 1.890 kWp | `SOLAR_KWP` |
| Fonte do perfil | PVsyst (CSV horário, 8.760 h) | `Shopping Rio Poty_Project_VCA_HourlyRes_0.CSV` |
| Geração anual estimada | ~3.134 MWh/ano | Agregado de `E_Grid` por mês |
| Geração pico médio | ~1.225 kW | Média anual do máximo horário |

---

## 2. Contrato de Demanda

| Parâmetro | Valor | Variável no código |
|---|---|---|
| Demanda HP contratada | 2.980 kW | `DEMANDA_HP_CONTRATADA` |
| Demanda FP contratada | 3.280 kW | `DEMANDA_FP_CONTRATADA` |

---

## 3. CAPEX

| Item | Valor (R$) | Variável no código |
|---|---|---|
| Solar FV | R$ 5.700.000,00 | `CAPEX_SOLAR` |
| BESS | R$ 8.396.490,96 | `CAPEX_BESS` |
| Implantação / Engenharia | R$ 3.000.000,00 | `CAPEX_IMPLANTACAO` |
| **Total Solar + BESS** | **R$ 17.096.490,96** | `CAPEX_TOTAL` |
| Total Somente Solar | R$ 8.700.000,00 | `CAPEX_SOLAR_ONLY` |

**Parâmetros financeiros:** Vida útil = 25 anos (`VIDA_UTIL_ANOS`), taxa de desconto = 10% a.a. (`TAXA_DESCONTO`).

---

## 4. Premissas Tarifárias

Todas as constantes extraídas de `fatura/premissas.py`.

### 4.1 Impostos

| Tributo | Alíquota | Variável |
|---|---|---|
| PIS | 0,7216% | `PIS = 0.007216` |
| COFINS | 3,3320% | `COFINS = 0.033320` |
| ICMS | 22,50% | `ICMS = 0.2250` |
| PIS + COFINS | 4,0536% | `PIS_COFINS = 0.040536` |

### 4.2 Fatores de Gross-up

Os impostos são aplicados como **gross-up** (por dentro): o valor final já inclui o imposto.

| Fator | Fórmula | Valor |
|---|---|---|
| Fator Tributado (ICMS + PIS/COFINS) | $(1 - \text{ICMS}) \times (1 - \text{PIS\_COFINS})$ | 0,743585 |
| Fator Isento ICMS (só PIS/COFINS) | $1 - \text{PIS\_COFINS}$ | 0,959464 |
| Fator Comercializadora (só ICMS) | $1 - \text{ICMS}$ | 0,7750 |

Fórmulas de gross-up:

$$\text{Valor\_tributado} = \frac{\text{Base}}{(1 - \text{ICMS}) \times (1 - \text{PIS} - \text{COFINS})}$$

$$\text{Valor\_isento\_ICMS} = \frac{\text{Base}}{1 - \text{PIS} - \text{COFINS}}$$

$$\text{Valor\_comercializadora} = \frac{\text{Base}}{1 - \text{ICMS}}$$

### 4.3 Tarifa AZUL

| Componente | Valor | Variável |
|---|---|---|
| Demanda HP (Ponta) | R$ 88,82/kW | `AZUL_DEMANDA_HP` |
| Demanda FP (Fora Ponta) | R$ 32,50/kW | `AZUL_DEMANDA_FP` |
| TUSD HP | R$ 140,21/MWh | `AZUL_TUSD_HP` |
| TUSD FP | R$ 140,21/MWh | `AZUL_TUSD_FP` |

### 4.4 Tarifa VERDE

| Componente | Valor | Variável |
|---|---|---|
| Demanda Única (FP) | R$ 32,50/kW | `VERDE_DEMANDA_UNICA` |
| TUSD HP | R$ 2.296,63/MWh | `VERDE_TUSD_HP` |
| TUSD FP | R$ 140,21/MWh | `VERDE_TUSD_FP` |

**Tarifa HP efetiva com desconto de fonte incentivada:**

$$\text{Tarifa\_HP\_efetiva} = \text{TUSD\_FP} + (\text{TUSD\_HP} - \text{TUSD\_FP}) \times 0{,}5 = 140{,}21 + (2296{,}63 - 140{,}21) \times 0{,}5 = \text{R\$ 1.218,42/MWh}$$

### 4.5 Desconto de Fonte Incentivada

| Parâmetro | Valor | Variável |
|---|---|---|
| Desconto | 50% (I-5: solar, eólica, biomassa, PCH ≤ 30 MW) | `DESCONTO_FONTE_INCENTIVADA = 0.50` |

### 4.6 Comercializadora (TE)

| Parâmetro | Valor | Variável |
|---|---|---|
| TE base (sem imposto) | R$ 0,306/kWh | `TE_COMERCIALIZADORA = 0.306` |
| Tributação | Apenas ICMS (sem PIS/COFINS) | Fórmula: `base / FATOR_COMERCIALIZADORA` |

---

## 5. Modelo A — Dia Típico (Monte Carlo)

Implementado em `montecarlo_dia_tipico.py`.

### 5.1 Algoritmo Bootstrap

1. **Pool de amostragem:** Carrega todos os 15 CSVs iplenix disponíveis (Nov/2024 a Jan/2026). Filtra apenas **dias úteis com horário de ponta** (o BESS só opera em ponta).

2. **Amostragem por slot:** Para cada um dos 96 blocos de 15 min do dia, agrupa todos os valores históricos daquele horário → pool $P_s$.

3. **Geração de dias sintéticos:** $K = 1.000$ dias (`N_BOOTSTRAP = 1_000`), seed = 42 (`SEED = 42`). Para cada dia $k$ e slot $s$:

$$X_s^{(k)} \sim \text{Uniform}(P_s) \quad k = 1..K, \; s = 0..95$$

4. **Dia típico mediano:** Mediana element-wise ao longo dos K dias:

$$d_s = \text{median}(X_s^{(1)}, X_s^{(2)}, \ldots, X_s^{(K)})$$

5. **Simulação BESS** sobre o dia típico: descarga na ponta (17h30–20h29) com 5% de margem anti-injeção, carga 07h30–15h.

6. **Extrapolação:** dia × 30 → mês; mês × 12 → ano (`DIAS_POR_MES = 30`, `MESES_POR_ANO = 12`).

### 5.2 Justificativa da Mediana

- Estimador robusto (breakdown point = 50%), resistente a outliers.
- Com $K = 1.000$, a convergência é suficiente (erro < 0,5% vs mediana direta).
- Em distribuições com cauda longa (típicas de carga elétrica), a mediana representa melhor a tendência central do que a média.

### 5.3 Limitações

- Extrapolação × 30 × 12 simplificada (assume todos os meses iguais).
- Fins de semana excluídos do pool (sem horário de ponta no medidor).

---

## 6. Modelo B — Dia a Dia (15 min)

Implementado em `modelamento_anual.py`. Este é o **modelo oficial** para resultados financeiros.

### 6.1 Carga de Dados

| Tipo | Meses | Tratamento |
|---|---|---|
| **Reais** (pós-instalação) | Nov/2025, Dez/2025, Jan/2026 | Carregados diretamente, sem ajuste |
| **Ajustados** (pré-instalação) | Fev/2025 a Out/2025 | Ajustados via delta-correction |

**Total:** 12 meses, ~357 dias, >100.000 leituras de 15 min.

### 6.2 Delta-Correction (Ajuste Sazonal)

**Motivação:** Os 9 meses pré-instalação refletem a carga antiga (antes do sistema solar). Para projetar como seria a carga nesses meses **com o sistema instalado**, aplicamos um fator de correção derivado dos 3 meses reais.

**Algoritmo:**

1. Compara 3 pares de meses iguais:
   - Nov/2025 (pós) vs Nov/2024 (pré)
   - Dez/2025 (pós) vs Dez/2024 (pré)
   - Jan/2026 (pós) vs Jan/2025 (pré)

2. Para cada par e cada (Grandeza, Medicao):

$$\Delta_{\text{Mediana}} = \frac{\text{mediana}(\text{pós})}{\text{mediana}(\text{pré})}$$

$$\Delta_{P95} = \frac{P95(\text{pós})}{P95(\text{pré})}$$

3. O fator final = mediana dos 3 pares.

4. **Aplicação** (`ajustar_serie`):
   - Valores ≤ P90 da série: multiplicados por $\Delta_{\text{Mediana}}$
   - Valores > P90: multiplicados por $\Delta_{P95}$ (preserva outliers / picos de demanda)

### 6.3 Classificação de Dias

| Tipo | Definição | Comportamento BESS |
|---|---|---|
| **Dia útil com ponta** | Pelo menos 1 registro de Consumo HP > 0 | Carga 07h30–15h, descarga na ponta |
| **Fim de semana** (sáb/dom) | `dayofweek >= 5` | Peak-shaving FP com cap 2.800 kW |
| **Feriado em dia útil** | Sem ponta, mas não é fim de semana | BESS permanece idle, SOC carrega |

### 6.4 Ciclo BESS — Dia Útil

1. **00:00–07:30 — Standby.** SOC = carry-over do dia anterior.

2. **07:30–15:00 — Carga** a 1.000 kW (30 slots × 0,25h = 7.500 kWh máx, limitado pela capacidade de 6.200 kWh). Se SOC atingir 6.200 kWh, carga é reduzida ao espaço livre. Headroom: carga é limitada para que a demanda FP não ultrapasse `BESS_POTENCIA_SAIDA` (3.100 kW).

3. **17:30–20:29 — Descarga (ponta).** BESS descarrega cobrindo até 95% da demanda medida. Os 5% restantes permanecem no grid como margem anti-injeção.

   - **Distribuição SOC-proporcional:** O SOC disponível é distribuído uniformemente entre os slots HP restantes:

$$\text{budget\_kw} = \frac{\text{SOC}}{\text{slots\_HP\_restantes} \times DT}$$

$$\text{descarga\_kw} = \min(\text{bess\_target}, \; \text{BESS\_POTENCIA\_SAIDA}, \; \text{budget\_kw})$$

4. **20:30–24:00 — Standby.** SOC residual passa para o dia seguinte.

### 6.5 Comportamento BESS em Fins de Semana

Nos fins de semana, o BESS faz **peak-shaving FP** (não há horário de ponta):

- **Janela de carga (07h30–15h):** Se a demanda líquida (FP − solar) ≤ 2.800 kW, carrega respeitando o headroom até 2.800 kW. Se > 2.800 kW na janela de carga, descarrega para reduzir a demanda.
- **Fora da janela de carga:** Descarrega se demanda líquida > 2.800 kW.
- **Objetivo:** Manter demanda FP ≤ 2.800 kW em todos os slots do fim de semana.

### 6.6 Faturamento — Cenários C1 / C2 / C3

Para cada mês, agrega consumo/demanda e calcula 3 cenários:

| Cenário | Descrição | Modalidade | Solar | BESS |
|---|---|---|---|---|
| **C1 — Base** | Sem solar, sem BESS | AZUL | Não | Não |
| **C2 — Solar** | Solar reduz consumo e demanda FP | AZUL | Sim | Não |
| **C3 — Solar + BESS** | Solar + BESS, migração tarifária | VERDE | Sim | Sim |

Demanda VERDE no C3: $\text{dem\_verde} = \max(\text{dem\_fp\_bess}, \; \text{dem\_hp\_resid})$

---

## 7. Cálculo de Fatura

### 7.1 Fatura AZUL (`fatura/calculo_azul.py`)

**Split tributário automático:**

| Parcela | Tributação |
|---|---|
| Demanda medida (usada) | Tributada (ICMS + PIS/COFINS) |
| Demanda não usada (contratada − medida) | Isenta ICMS (só PIS/COFINS) |
| Ultrapassagem (medida − contratada, se > 0) | 2× tarifa cheia, sem desconto fonte |
| TUSD Energia (HP e FP) | Sempre tributada |

**Componentes:**

1. **Demanda faturada:** $\text{dem\_faturada} = \max(\text{contratada}, \; \text{medida})$
2. **Bases de demanda (sem imposto, com desconto fonte 50%):**

$$\text{base\_trib} = kW_{\text{tributada}} \times \text{tarifa} \times (1 - 0{,}50)$$

$$\text{base\_isenta} = kW_{\text{isenta}} \times \text{tarifa} \times (1 - 0{,}50)$$

$$\text{base\_ultra} = kW_{\text{ultrapassagem}} \times \text{tarifa} \times 2$$

3. **Bases de energia TUSD:**

$$\text{base\_tusd} = \text{consumo\_MWh} \times \text{TUSD\_R\$/MWh}$$

4. **Gross-up:** Cada base é dividida pelo fator correspondente.

5. **BEN (Benefício Tarifário):**

$$\text{ben\_líquido} = \text{desconto\_fonte\_total}$$

$$\text{impostos\_ben} = \sum \text{valor\_demandas} - \sum \text{base\_demandas}$$

$$\text{ben\_bruto} = \text{ben\_líquido} + \text{impostos\_ben}$$

6. **Total Distribuidora:**

$$\text{Total\_Dist} = \sum \text{Itens} + \text{Encargos} + \text{Ben\_Bruto} - \text{Ben\_Líquido}$$

7. **Total Comercializadora (TE):**

$$\text{Total\_Comerc} = \frac{\text{consumo\_total\_kWh} \times \text{TE}}{1 - \text{ICMS}}$$

8. **Custo Total:** $\text{Custo} = \text{Total\_Dist} + \text{Total\_Comerc}$

### 7.2 Fatura VERDE (`fatura/calculo_verde.py`)

**Diferença fundamental:** No VERDE, a ponta é cara na **energia** (TUSD HP = R$ 2.296,63/MWh, 16× maior que FP), não na demanda.

**Componentes:**

1. **Demanda única faturada:** $\text{dem\_faturada} = \max(\text{contratada}, \; \text{medida})$
2. **Bases de demanda:** Idênticas ao AZUL, mas com tarifa única FP (R$ 32,50/kW).
3. **TUSD Energia HP (com desconto fonte diferencial):**

$$\text{tarifa\_HP\_efetiva} = \text{TUSD\_FP} + (\text{TUSD\_HP} - \text{TUSD\_FP}) \times 0{,}5 = \text{R\$ 1.218,42/MWh}$$

$$\text{desconto\_HP} = \text{consumo\_HP\_MWh} \times (\text{TUSD\_HP} - \text{TUSD\_FP}) \times 0{,}5$$

4. **BEN:** $\text{ben\_líquido} = \text{desconto\_fonte\_total} + \text{desconto\_HP}$
5. **Distribuidora e Comercializadora:** Mesma mecânica do AZUL.

---

## 8. Resultados Financeiros

Dados extraídos de `data/audit_data.json`.

### 8.1 Comparativo de Custos Anuais

| Cenário | Custo Anual | Custo Mensal Médio |
|---|---|---|
| **C1 — Base AZUL** | R$ 12.298.004,98 | R$ 1.024.834,00 |
| **C2 — Solar AZUL** | R$ 10.455.211,74 | R$ 871.268,00 |
| **C3 — Solar + BESS VERDE** | R$ 8.013.258,87 | R$ 667.772,00 |

> Nota: C1 anual = soma das 12 linhas de `modelamento_anual_resultado.csv`.

### 8.2 Decomposição da Economia

| Componente | Valor Mensal | Valor Anual |
|---|---|---|
| Economia Solar (C1→C2) | R$ 153.566,00 | R$ 1.842.793,00 |
| Economia BESS (C2→C3) | R$ 203.496,00 | R$ 2.441.953,00 |
| **Economia Total (C1→C3)** | **R$ 357.062,00** | **R$ 4.284.746,00** |

### 8.3 Indicadores Financeiros — Solar + BESS

| Indicador | Valor |
|---|---|
| CAPEX | R$ 17.096.490,96 |
| Economia anual | R$ 4.284.746,00 |
| Payback simples | 4,0 anos |
| Payback descontado (10% a.a.) | 5,4 anos |
| TIR | 25,0% |
| VPL (10% a.a., 25 anos) | R$ 21.796.320,95 |
| ROI (25 anos) | 527% |

### 8.4 Indicadores Financeiros — Somente Solar

| Indicador | Valor |
|---|---|
| CAPEX | R$ 8.700.000,00 |
| Economia anual | R$ 1.842.793,00 |
| Payback simples | 4,7 anos |
| VPL (10% a.a., 25 anos) | R$ 8.027.107,98 |
| TIR | 21,0% |
| ROI (25 anos) | 430% |

---

## 9. Resultados Mensais

Dados de `data/modelamento_anual_resultado.csv` (12 meses, modelo dia-a-dia).

| Mês | C1 (R$) | C2 (R$) | C3 (R$) | Economia C1→C3 | Dem HP (kW) | Dem FP (kW) | Dias BESS |
|---|---|---|---|---|---|---|---|
| Nov | R$ 1.103.574,82 | R$ 945.944,54 | R$ 735.408,32 | R$ 368.166,50 | 2.902,07 | 2.829,11 | 21 |
| Dez | R$ 1.091.230,64 | R$ 937.090,86 | R$ 731.729,75 | R$ 359.500,89 | 2.995,67 | 3.191,99 | 22 |
| Jan | R$ 982.821,30 | R$ 837.518,32 | R$ 656.850,28 | R$ 325.971,02 | 2.425,91 | 2.517,59 | 20 |
| Fev | R$ 972.491,06 | R$ 833.707,24 | R$ 637.377,69 | R$ 335.113,37 | 2.348,73 | 2.480,13 | 20 |
| Mar | R$ 1.026.933,20 | R$ 882.497,66 | R$ 685.630,59 | R$ 341.302,61 | 2.465,48 | 2.612,55 | 21 |
| Abr | R$ 1.004.987,67 | R$ 861.880,39 | R$ 666.063,23 | R$ 338.924,44 | 2.313,76 | 2.498,83 | 22 |
| Mai | R$ 1.030.916,67 | R$ 888.615,60 | R$ 696.531,55 | R$ 334.385,12 | 2.296,57 | 2.505,58 | 22 |
| Jun | R$ 999.365,39 | R$ 856.954,89 | R$ 656.672,28 | R$ 342.693,11 | 2.375,40 | 2.513,89 | 21 |
| Jul | R$ 1.019.519,41 | R$ 866.476,63 | R$ 672.863,71 | R$ 346.655,70 | 2.333,32 | 2.684,18 | 23 |
| Ago | R$ 789.073,44 | R$ 615.032,88 | R$ 476.697,10 | R$ 312.376,34 | 1.973,28 | 2.474,94 | 14 |
| Set | R$ 1.132.082,50 | R$ 960.646,65 | R$ 664.419,31 | R$ 467.663,19 | 3.328,40 | 3.308,85 | 22 |
| Out | R$ 1.145.008,88 | R$ 968.846,08 | R$ 733.015,06 | R$ 411.993,82 | 3.132,23 | 3.054,99 | 22 |

**Totais anuais:**

| Métrica | Valor |
|---|---|
| C1 Total | R$ 12.298.004,98 |
| C2 Total | R$ 10.455.211,74 |
| C3 Total | R$ 8.013.258,87 |
| Economia Total (C1→C3) | R$ 4.284.746,11 |
| Dias com ponta (BESS ativo) | 250 de 357 |

---

## 10. Cobertura e Confiabilidade do BESS

| Métrica | Valor | Fonte |
|---|---|---|
| Dias simulados | 357 | `audit_data.json → _meta.dias_simulados` |
| Dias com ponta | 250 | `audit_data.json → _meta.dias_com_ponta` |
| Dias com esgotamento BESS | 13 | `audit_data.json → _meta.dias_bess_dead` |
| Cobertura HP (% do consumo HP coberto pelo BESS) | 94,1% | `audit_data.json → _meta.cobertura_bess_pct` |
| HP residual total (não coberto) | 86.652 kWh/ano | `audit_data.json → outliers.hp_residual_anual_kwh` |

### 10.1 Dias com Esgotamento (Outliers)

| Data | Dia da Semana | Mês | HP Total (kWh) | HP Residual (kWh) | Dem HP (kW) | Cobertura |
|---|---|---|---|---|---|---|
| 2025-09-19 | Sexta | Set | 9.801 | 3.601 | 3.328 | 63,3% |
| 2025-10-31 | Sexta | Out | 9.181 | 2.981 | 3.132 | 67,5% |
| 2025-10-10 | Sexta | Out | 8.280 | 2.080 | 2.968 | 74,9% |
| 2025-11-20 | Quinta | Nov | 8.125 | 1.925 | 2.902 | 76,3% |
| 2025-12-30 | Terça | Dez | 7.640 | 1.440 | 2.996 | 81,2% |
| 2025-12-18 | Quinta | Dez | 7.449 | 1.249 | 2.520 | 83,2% |
| 2025-03-27 | Quinta | Mar | 7.226 | 1.026 | 2.465 | 85,8% |
| 2025-07-10 | Quinta | Jul | 5.627 | 779 | 1.945 | 86,2% |
| 2025-11-19 | Quarta | Nov | 6.842 | 642 | 2.527 | 90,6% |
| 2025-06-12 | Quinta | Jun | 6.830 | 630 | 2.375 | 90,8% |
| 2026-01-22 | Quinta | Jan | 6.824 | 624 | 2.412 | 90,9% |
| 2025-07-24 | Quinta | Jul | 6.747 | 547 | 2.333 | 91,9% |
| 2025-11-14 | Sexta | Nov | 6.593 | 393 | 2.527 | 94,0% |

Critério de esgotamento: SOC ≤ 1 kWh durante horário de ponta com consumo HP > 0 (`bess_dead = soc <= 1.0 and cons_hp_total > 0`).

---

## 11. Glossário

| Termo | Definição |
|---|---|
| **BESS** | Battery Energy Storage System — sistema de armazenamento de energia por baterias |
| **HP** | Horário de Ponta — período de maior custo tarifário (17h30–20h29 na Equatorial Piauí) |
| **FP** | Fora de Ponta — todos os horários exceto HP |
| **TUSD** | Tarifa de Uso do Sistema de Distribuição — componente da fatura relativo ao uso da rede elétrica |
| **TE** | Tarifa de Energia — componente relativo à geração/comercialização de energia |
| **Gross-up** | Cálculo de imposto "por dentro": o valor final já inclui o imposto na base de cálculo |
| **BEN** | Benefício Tarifário — ajuste tributário na fatura que neutraliza o efeito fiscal do desconto de fonte incentivada |
| **SOC** | State of Charge — nível de carga da bateria (kWh) |
| **Peak-shaving** | Técnica de corte de picos de demanda usando descarga de baterias |
| **Anti-injeção** | Margem de segurança (5%) para evitar que o BESS injete energia na rede |
| **PVsyst** | Software de simulação de geração fotovoltaica |
| **CAPEX** | Capital Expenditure — investimento inicial |
| **VPL** | Valor Presente Líquido — soma dos fluxos de caixa descontados |
| **TIR** | Taxa Interna de Retorno — taxa de desconto que zera o VPL |
| **ROI** | Return on Investment — retorno sobre o investimento |
| **C1** | Cenário 1 — base (sem solar, sem BESS, tarifa AZUL) |
| **C2** | Cenário 2 — somente solar (tarifa AZUL) |
| **C3** | Cenário 3 — solar + BESS (tarifa VERDE) |
| **Delta-correction** | Ajuste estatístico aplicado aos meses pré-instalação para projetar a carga pós-instalação |
| **Bootstrap Monte Carlo** | Técnica de reamostragem estatística para construir um dia típico a partir de dados históricos |
| **I-5** | Classificação ANEEL para fontes incentivadas com 50% de desconto na TUSD de demanda |
| **Carry-over** | SOC residual do dia anterior que é transferido como SOC inicial do dia seguinte |
| **Modelo A** | Modelo de dia típico (Monte Carlo) — simplificado, extrapolação × 30 × 12 |
| **Modelo B** | Modelo dia a dia (15 min) — oficial, simula cada dia individualmente |
| **Split tributário** | Separação automática da demanda faturada em parcelas tributada, isenta e ultrapassagem |
