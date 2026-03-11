# Documentação Técnica — Modelamento Financeiro Solar + BESS

**Repositório:** `kira-bess-modelamento`
**Última atualização:** Junho 2025
**Perfil:** Shopping center — Mercado Livre de Energia

---

## Índice

1. [Premissas Comuns](#1-premissas-comuns)
2. [Modelo A — Dia Típico (Bootstrap Monte Carlo)](#2-modelo-a--dia-típico-bootstrap-monte-carlo)
3. [Modelo B — Iteração Dia a Dia (15 min)](#3-modelo-b--iteração-dia-a-dia-15-min)
4. [Cálculo de Fatura (Pacote `fatura/`)](#4-cálculo-de-fatura-pacote-fatura)
5. [Comparativo de Resultados](#5-comparativo-de-resultados)
6. [Estrutura do Repositório](#6-estrutura-do-repositório)
7. [Glossário](#7-glossário)

---

## 1. Premissas Comuns

Ambos os modelos compartilham as mesmas premissas de equipamento, contrato,
CAPEX e tarifas. Qualquer alteração deve ser feita nos arquivos-fonte
(`modelamento_anual.py`, `montecarlo_dia_tipico.py`, `fatura/premissas.py`)
para manter consistência.

### 1.1 Sistema Proposto

| Componente | Especificação | Observação |
|---|---|---|
| Solar FV | 1.890 kWp | Perfil PVsyst (8.760 h) |
| BESS — Capacidade | 6.200 kWh úteis | Descontando DoD e degradação |
| BESS — Potência descarga | 3.100 kW | C-rate ≈ 0,5C |
| BESS — Potência carga | 1.000 kW | C-rate ≈ 0,16C |
| BESS — Janela de carga | 09h–15h (24 slots × 15 min) | Fora de ponta, 6.000 kWh/dia máx |
| BESS — Janela de descarga | ~18h47–21h32 (12 slots × 15 min) | Horário de ponta (automático via medidor) |
| BESS — Margem anti-injeção | 5% da demanda permanece no grid | Proteção contra relé de injeção reversa |

### 1.2 Contrato de Demanda

| Parâmetro | Valor |
|---|---|
| Demanda HP contratada | 2.980 kW |
| Demanda FP contratada | 3.280 kW |

### 1.3 CAPEX

| Item | Valor (R$) |
|---|---|
| Solar FV (1.890 kWp) | 5.700.000,00 |
| BESS (6.200 kWh / 3,1 MW) | 8.396.490,96 |
| Engenharia + Implantação | 3.000.000,00 |
| **CAPEX Total (Solar + BESS)** | **17.096.490,96** |
| CAPEX Somente Solar | 8.700.000,00 |

### 1.4 Parâmetros Financeiros

| Parâmetro | Valor | Uso |
|---|---|---|
| Vida útil | 25 anos | VPL, ROI |
| Taxa de desconto | 10% a.a. | VPL, payback descontado |

### 1.5 Premissas Tarifárias

#### 1.5.1 Estrutura Tributária

O faturamento de energia no Brasil (ACR/ACL) utiliza impostos calculados
**por dentro** (gross-up): o valor final já inclui o imposto, que é calculado
dividindo a base pela fração complementar do tributo.

| Tributo | Alíquota | Descrição |
|---|---|---|
| PIS | 0,7216% | Programa de Integração Social |
| COFINS | 3,3320% | Contribuição para Financiamento da Seguridade Social |
| ICMS | 22,50% | Imposto sobre Circulação de Mercadorias e Serviços |

Fatores de gross-up derivados:

```
FATOR_TRIBUTADO          = (1 − ICMS) × (1 − PIS − COFINS) ≈ 0,7436
FATOR_ISENTO_ICMS        = (1 − PIS − COFINS)                ≈ 0,9595
FATOR_COMERCIALIZADORA   = (1 − ICMS)                        ≈ 0,7750
```

Exemplo: uma base de R$ 1.000 resulta em:
- Tributado: R$ 1.000 / 0,7436 = R$ 1.344,81 (imposto embutido = R$ 344,81)
- Isento ICMS: R$ 1.000 / 0,9595 = R$ 1.042,21
- Comercializadora: R$ 1.000 / 0,775 = R$ 1.290,32

#### 1.5.2 Tarifa AZUL (Cenários C1 e C2)

| Componente | Valor | Unidade |
|---|---|---|
| Demanda HP | 88,82 | R$/kW |
| Demanda FP | 32,50 | R$/kW |
| TUSD Consumo HP | 140,21 | R$/MWh |
| TUSD Consumo FP | 140,21 | R$/MWh |
| Desconto Fonte Incentivada | 50% | Sobre demanda (I-5) |

> **Nota AZUL:** TUSD HP = TUSD FP (R$ 140,21/MWh). A diferenciação ponta vs
> fora-ponta ocorre **apenas na demanda** (R$ 88,82 vs R$ 32,50/kW).

#### 1.5.3 Tarifa VERDE (Cenário C3 — Solar + BESS)

| Componente | Valor | Unidade |
|---|---|---|
| Demanda Única (FP) | 32,50 | R$/kW |
| TUSD Consumo HP | 2.296,63 | R$/MWh |
| TUSD Consumo FP | 140,21 | R$/MWh |
| Desconto Fonte Incentivada | 50% | Sobre demanda + diferencial HP |

> **Nota VERDE:** Não existe demanda de ponta. A ponta é penalizada via **energia**
> (TUSD HP = 16,4× TUSD FP). A tarifa HP efetiva com desconto:
>
> `tarifa_hp_efetiva = 140,21 + (2.296,63 − 140,21) × 0,5 = R$ 1.218,42/MWh`
>
> Isso torna o VERDE vantajoso quando o BESS cobre a maior parte do HP.

#### 1.5.4 Comercializadora (TE)

| Componente | Valor | Unidade |
|---|---|---|
| TE Base | 0,308 | R$/kWh (sem imposto) |
| Tributação | Apenas ICMS | (sem PIS/COFINS) |

#### 1.5.5 Heurística de Faturamento (Split Tributário)

A distribuidora fatura a demanda com split automático entre tributada e isenta:

| Parcela | Tributação | Quando |
|---|---|---|
| Demanda medida (usada) | ICMS + PIS + COFINS | Sempre |
| Demanda não usada (contratada − medida) | Só PIS + COFINS | Quando contrat. > medida |
| TUSD Energia (HP e FP) | ICMS + PIS + COFINS | Sempre |
| Ultrapassagem | 200% (2× tarifa cheia) | Quando medida > contrat. |

### 1.6 Dados de Entrada

| Dado | Fonte | Granularidade | Volume |
|---|---|---|---|
| Consumo e demanda | 15 CSVs iplenix (Nov/24 a Jan/26) | 15 minutos | 505 dias, ~187k leituras |
| Geração solar | PVsyst (Shopping Rio Poty) | Horária | 8.760 h |
| Classificação ponta | Automática pelo medidor | Por leitura | 12 slots/dia útil |

Estrutura do CSV iplenix:

| Coluna | Tipo | Exemplo |
|---|---|---|
| Timestamp | datetime | `2025-11-03 18:47:27` |
| Valor | float | `2841.12` |
| Medicao | string | `Demanda ativa de Ponta` |
| Grandeza | string | `Demanda` |

As 4 medições relevantes:
- **Consumo ativo de Ponta (HP)** — energia em kWh/slot
- **Consumo ativo Fora de Ponta (FP)** — energia em kWh/slot
- **Demanda ativa de Ponta (HP)** — potência em kW
- **Demanda ativa Fora de Ponta (FP)** — potência em kW

> **Fins de semana:** O medidor classifica sábados/domingos/feriados como
> inteiramente Fora de Ponta (0 registros de HP). O BESS não opera nesses dias.

---

## 2. Modelo A — Dia Típico (Bootstrap Monte Carlo)

**Arquivo:** `montecarlo_dia_tipico.py`

### 2.1 Visão Geral

Este modelo constrói um **dia típico estatístico** a partir de toda a base
histórica e simula o BESS sobre esse único dia, extrapolando o resultado
para 12 meses idênticos. É mais simples e gera gráficos intuitivos para
apresentação a clientes.

### 2.2 Algoritmo Bootstrap

#### 2.2.1 Construção do Pool de Amostragem

1. Carrega todos os 15 CSVs iplenix do `DATA_DIR`.
2. Aplica pipeline de limpeza (remove contrato, reativos nulos, duplicatas).
3. Filtra apenas **dias úteis com horário de ponta** (pelo menos 1 registro
   de "Consumo ativo de Ponta"). Descarta fins de semana automaticamente.
4. Calcula coluna `slot = hora × 4 + minuto // 15` (0–95).
5. Resultado: pool de **307 dias úteis** com ~118k registros.

#### 2.2.2 Bootstrap Monte Carlo

Para cada grandeza de interesse (Consumo HP, Consumo FP, Demanda HP, Demanda FP):

1. **Agrupa** o pool por slot temporal: para cada slot `s`, extrai o vetor
   de todos os valores observados `P_s = {v₁, v₂, ..., vₙ}`.

2. **Gera K = 1.000 dias sintéticos** (seed = 42):

   ```
   Para k = 1, 2, ..., 1000:
       Para cada slot s presente nesta grandeza:
           X_s^(k) = sample_with_replacement(P_s)
   ```

   Ou seja, para cada dia sintético e cada slot, sorteia **um valor** com
   reposição do pool daquele slot.

3. **Calcula a mediana element-wise** ao longo dos K dias:

   ```
   d_s = median(X_s^(1), X_s^(2), ..., X_s^(K))    para todo s
   ```

   O vetor `d = [d_0, d_1, ..., d_95]` é o **dia típico mediano**.

#### 2.2.3 Por que Mediana (não Média)?

- **Robustez estatística:** A mediana tem breakdown point = 50% (resiste a
  até 50% de outliers), enquanto a média é deslocada por 1 único outlier.
- **Distribuições assimétricas:** O consumo elétrico tipicamente apresenta
  cauda direita longa (dias de pico). A mediana representa melhor a
  "operação normal" do que a média aritmética.
- **Convergência bootstrap:** Para K → ∞, a mediana dos K sorteios converge
  para a mediana populacional de cada slot. Com K = 1.000, o erro é < 0,5%.

#### 2.2.4 Por que Bootstrap (não Mediana Direta)?

O bootstrap com K = 1.000 poderia parecer redundante se usássemos a mediana
direta dos valores por slot. De fato, para estimadores como a mediana, o
resultado é muito próximo. A vantagem do bootstrap é:

1. **Permite análise de incerteza:** Os K = 1.000 totais diários dão uma
   distribuição empírica do consumo HP/dia, que é visualizada nos histogramas.
2. **Suaviza bordas:** Slots de ponta com poucas observações (3 na borda)
   se beneficiam da reamostragem.
3. **Extensibilidade:** Se o modelo evoluir para usar média, percentis P75/P95,
   ou intervalos de confiança, o framework bootstrap já está pronto.

### 2.3 Simulação BESS no Dia Típico

A simulação percorre os 96 slots do dia mediano:

1. **Standby (00h–09h):** SOC = 0. BESS inicia vazio.
2. **Carga (09h–15h):**
   - `p_charge = min(1.000 kW, (6.200 − SOC) / 0,25)`
   - `SOC += p_charge × 0,25`
   - 24 slots × 250 kWh/slot = 6.000 kWh máximo (limitado pela capacidade).
3. **Ponta (~18h47–21h32):**
   - Para cada slot com `cons_hp > 0`:
     - `bess_target_kw = dem_hp × (1 − 0,05)` → 95% da demanda
     - `max_discharge_kw = min(bess_target_kw, 3.100)`
     - `discharge_kwh = min(SOC, max_discharge_kw × 0,25)`
     - `SOC -= discharge_kwh`
     - `residual = max(0, cons_hp − discharge_kwh)`
4. **Standby (21h32–24h):** Fim do ciclo.

### 2.4 Extrapolação

A extrapolação é a simplificação central deste modelo:

```
Consumo_mensal = Consumo_dia × 30
Consumo_anual  = Consumo_mensal × 12
```

Assume todos os meses iguais com 30 dias úteis. Não captura:
- Variação sazonal de consumo (verão vs inverno)
- Meses com diferente número de dias úteis
- Feriados

### 2.5 Resultados — Dia Típico Mediano

| Métrica do Dia | Valor |
|---|---|
| Consumo HP total/dia | 8.099 kWh |
| Consumo FP total/dia | 39.799 kWh |
| Demanda HP máxima | 1.916 kW |
| Demanda FP máxima | 2.247 kW |
| BESS carga/dia | 6.000 kWh |
| BESS descarga/dia | 6.000 kWh |
| HP residual/dia | 2.099 kWh (25,9%) |
| Cobertura BESS | 74,1% |
| BESS dead | SIM (SOC → 0 antes do fim da ponta) |

### 2.6 Resultados Financeiros — Modelo A

| Métrica | Valor |
|---|---|
| C1 — Base AZUL | R$ 1.116.943/mês → **R$ 13.403.316/ano** |
| C2 — Solar AZUL | R$ 966.010/mês → R$ 11.592.117/ano |
| C3 — Solar+BESS VERDE | R$ 888.724/mês → **R$ 10.664.691/ano** |
| **Economia mensal** | **R$ 228.219** |
| **Economia anual** | **R$ 2.738.625** |

#### Análise Financeira — Solar + BESS

| Métrica | Valor |
|---|---|
| CAPEX | R$ 17.096.491 |
| Economia anual | R$ 2.738.625 |
| **Payback simples** | **6,2 anos** |
| Payback descontado | 10,3 anos |
| TIR | 15,6% |
| VPL (10%) | R$ 7.762.117 |
| ROI (25 anos) | 300% |

#### Análise Financeira — Somente Solar

| Métrica | Valor |
|---|---|
| CAPEX | R$ 8.700.000 |
| Economia anual | R$ 1.811.199 |
| **Payback simples** | **4,8 anos** |
| TIR | 20,6% |
| VPL (10%) | R$ 7.740.325 |

### 2.7 Saídas Geradas

| Arquivo | Descrição |
|---|---|
| `data/dia_tipico_mediano.csv` | 96 linhas — perfil do dia mediano com BESS |
| `output/dia_tipico_perfil.html` | Gráfico Plotly — consumo HP/FP + SOC do BESS |
| `output/bootstrap_distribuicao.html` | Histograma + box plot das 1.000 amostras |

### 2.8 Limitações

1. **Dia Frankenstein:** Os slots são amostrados independentemente — o slot das
   18h pode vir de janeiro e o das 19h de julho. Não preserva correlação
   temporal intra-dia.
2. **Mês único × 12:** Não captura sazonalidade de geração solar, consumo ou
   demanda de pico (Set/Out com >3.000 kW).
3. **Demanda mediana:** A mediana suaviza picos reais. Nunca gera ultrapassagem
   de contrato (mediana HP = 1.916 kW << contratada 2.980 kW).
4. **Extrapolação 30 × 12:** Assume 360 dias úteis/ano (na realidade são ~244).
   A inversão (muitos dias × demanda mediana baixa) pode subestimar ou
   superestimar conforme o caso.

---

## 3. Modelo B — Iteração Dia a Dia (15 min)

**Arquivo:** `modelamento_anual.py`

### 3.1 Visão Geral

Este modelo simula o BESS **para cada dia individual** do ano, utilizando
dados de 15 minutos reais (3 meses) e ajustados (9 meses). Calcula faturas
**mensais** separadamente, capturando toda a variabilidade sazonal e diária.

### 3.2 Carga de Dados

#### 3.2.1 Meses Reais (pós-instalação)

| Mês | CSV | Leituras | Tipo |
|---|---|---|---|
| Nov/25 | `iplenix_nov2025.csv` | ~27k | Real |
| Dez/25 | `iplenix_dez2025.csv` | ~28k | Real |
| Jan/26 | `iplenix_jan2026.csv` | ~28k | Real |

Esses 3 meses representam o padrão de carga **após** a instalação do sistema
solar e são usados "as is", sem ajuste.

#### 3.2.2 Meses Ajustados (pré-instalação)

| Mês | CSV | Tipo |
|---|---|---|
| Fev/25 | `iplenix_fev2025.csv` | Ajustado |
| Mar/25 | `iplenix_mar2025.csv` | Ajustado |
| Abr/25 | `iplenix_abr2025.csv` | Ajustado |
| Mai/25 | `iplenix_mai2025.csv` | Ajustado |
| Jun/25 | `iplenix_jun2025.csv` | Ajustado |
| Jul/25 | `iplenix_jul2025.csv` | Ajustado |
| Ago/25 | `iplenix_ago2025.csv` | Ajustado |
| Set/25 | `iplenix_set2025.csv` | Ajustado |
| Out/25 | `iplenix_out2025.csv` | Ajustado |

### 3.3 Delta-Correction (Ajuste Sazonal)

#### 3.3.1 Motivação

Os meses Fev–Out/25 foram medidos **antes** da instalação solar. Para projetar
como seria o consumo com solar, precisamos ajustar esses dados para o perfil
pós-instalação.

#### 3.3.2 Algoritmo

Para 3 pares de meses iguais (Nov Pré/Pós, Dez Pré/Pós, Jan Pré/Pós):

```
Para cada par (pós, pré) e cada (Grandeza, Medicao):
    Delta_Mediana = mediana(valores_pós) / mediana(valores_pré)
    Delta_P95     = P95(valores_pós) / P95(valores_pré)
```

A mediana dos 3 deltas é o fator final.

#### 3.3.3 Aplicação

Para cada mês pré-carga (Fev–Out):

```
P90 = percentil_90(valores do mês)

Para cada leitura:
    Se Valor ≤ P90:
        Valor_ajustado = Valor × Delta_Mediana
    Se Valor > P90:
        Valor_ajustado = Valor × Delta_P95
```

**Justificativa do threshold P90 com dual delta:**
- Valores ≤ P90 (90% da distribuição) representam operação normal → Delta_Mediana
  captura a mudança na tendência central.
- Valores > P90 (10% superiores) representam picos → Delta_P95 preserva a
  estrutura dos extremos, que são cruciais para demanda faturada.
- Isso evita que picos sejam suavizados pela mediana ou que a massa central
  seja distorcida pelo P95.

### 3.4 Perfil Solar PVsyst

O CSV do PVsyst (`Shopping Rio Poty_Project_VCA_HourlyRes_0.CSV`) contém
8.760 linhas (1/hora) com:

| Coluna | Descrição | Unidade |
|---|---|---|
| EArray | Energia no array DC | kWh/h |
| E_Grid | Energia injetada no grid AC | kWh/h |

Processamento:
1. Valores negativos de E_Grid (consumo noturno de inversores) → zerados.
2. Agrega `EArray` por (mês, hora) → média horária por mês (para sim. BESS).
3. Agrega `E_Grid` por mês → geração total mensal (para faturamento).

Geração anual total: **~3.134 MWh** (E_Grid).

### 3.5 Simulação BESS — Dia a Dia

Para cada um dos **357 dias** do ano:

#### 3.5.1 Classificação do Dia

- **Dia útil (com ponta):** Pelo menos 1 registro de "Consumo ativo de Ponta".
  São ~244 dias. O BESS opera normalmente.
- **Fim de semana / feriado (sem ponta):** 0 registros HP. São ~113 dias.
  O BESS fica em standby.

#### 3.5.2 Ciclo do BESS (dia útil)

```
SOC = 0 kWh  (BESS inicia vazio cada dia)

Para cada timestamp ts do dia (≈192 registros, 4 medições × 96 slots):
    hora = ts.hour

    # ───── CARGA (09h ≤ hora < 15h) ─────
    Se 9 ≤ hora < 15:
        espaço = 6.200 − SOC
        p_charge = min(1.000, espaço / 0.25)  kW
        SOC += p_charge × 0.25  kWh
        dem_FP_BESS = dem_FP_original − solar + p_charge

    # ───── DESCARGA (slot com HP > 0) ─────
    Se Consumo_HP deste slot > 0:
        bess_target_kw = Dem_HP × (1 − 0.05)    # 95% da demanda
        max_kw = min(bess_target_kw, 3.100)
        descarga_kwh = min(SOC, max_kw × 0.25)
        SOC −= descarga_kwh
        residual = cons_HP − descarga_kwh
```

#### 3.5.3 Margem Anti-Injeção (5%)

O BESS alimenta no máximo **95% da demanda medida** em cada slot. Os 5%
restantes são consumidos do grid. Isso evita que, em transientes de
carga/descarga, o BESS injete energia na rede e dispare relés de
proteção anti-ilha.

Sem essa margem, o BESS poderia cobrir 100% da demanda instantânea.
Mas se no instante seguinte a carga diminuir levemente, a inércia de
descarga do BESS causaria injeção reversa momentânea.

### 3.6 Faturamento — 12 Meses Individuais

Para cada mês, agrega:
- Consumo HP total (kWh/mês)
- Consumo FP total (kWh/mês)
- Demanda HP máxima (kW)
- Demanda FP máxima (kW)
- HP residual (kWh/mês) = consumo HP não coberto pelo BESS

E calcula 3 cenários de fatura:

#### C1 — Base AZUL

Fatura AZUL com consumo e demanda originais, sem solar e sem BESS.
Representa a baseline de custo do shopping.

#### C2 — Solar AZUL

Fatura AZUL com consumo FP reduzido pela geração solar.
A demanda FP pode reduzir levemente (solar durante o dia reduz pico FP).
A demanda HP não muda (solar não gera durante ponta/noite).

#### C3 — Solar + BESS VERDE

Fatura VERDE com:
- **Consumo HP** = HP residual (pós-BESS), muito reduzido
- **Consumo FP** = FP − solar + BESS_charge (a carga do BESS adiciona consumo FP)
- **Demanda** = max(dem_FP_com_BESS, dem_HP_residual) — demanda única no VERDE

A vantagem do VERDE aparece na eliminação da demanda HP (R$ 88,82/kW → R$ 0),
compensando a TUSD HP cara (R$ 2.296,63/MWh) graças à redução drástica do HP
pelo BESS.

### 3.7 Cobertura do BESS

| Métrica | Valor |
|---|---|
| Dias simulados | 357 |
| Dias com ponta (úteis) | 244 |
| Fins de semana (sem ponta) | 113 |
| Dias com HP residual | 244 (todos — pela margem de 5%) |
| Dias com BESS dead (SOC → 0) | 18 |
| Cobertura BESS média | 94,0% |

### 3.8 Consumo Anual

| Grandeza | kWh/ano | Observação |
|---|---|---|
| Consumo HP total | 1.426.495 | Antes do BESS |
| HP coberto pelo BESS | 1.340.943 | 94,0% |
| **HP residual** | **85.551** | 6,0% → vai para TUSD HP VERDE |
| Consumo FP total | 13.376.917 | Antes de solar |
| Geração solar | 3.133.823 | PVsyst E_Grid |
| FP líquido (−solar +BESS_charge) | 11.822.543 | Para faturamento |

### 3.9 Resultados Mensais

| Mês | C1 AZUL (R$) | C2 Solar (R$) | C3 VERDE+BESS (R$) | HP kWh | HP Resid kWh |
|---|---|---|---|---|---|
| Nov | 1.107.803 | 952.694 | 748.985 | 128.837 | 10.102 |
| Dez | 1.101.424 | 947.328 | 753.075 | 124.656 | 8.228 |
| Jan | 985.506 | 839.674 | 662.142 | 118.197 | 6.284 |
| Fev | 974.067 | 834.673 | 645.704 | 115.639 | 5.825 |
| Mar | 1.028.408 | 883.338 | 693.775 | 114.213 | 6.115 |
| Abr | 1.006.649 | 862.916 | 675.314 | 114.593 | 5.740 |
| Mai | 1.032.610 | 889.684 | 703.175 | 119.837 | 5.847 |
| Jun | 1.000.899 | 857.865 | 669.008 | 114.114 | 5.858 |
| Jul | 1.019.462 | 864.660 | 681.273 | 130.938 | 6.492 |
| Ago | 798.076 | 623.270 | 484.436 | 78.833 | 3.844 |
| Set | 1.071.252 | 896.788 | 679.616 | 129.970 | 10.033 |
| Out | 1.121.515 | 944.579 | 743.510 | 136.668 | 11.183 |
| **ANO** | **12.247.670** | **10.397.467** | **8.140.012** | **1.426.495** | **85.551** |

### 3.10 Dias Críticos (BESS Esgotou)

Os 18 dias em que o BESS atingiu SOC = 0 antes de cobrir toda a ponta:

| Dia | DdS | HP Total kWh | HP Resid kWh | Dem HP kW |
|---|---|---|---|---|
| 2025-09-19 | Sexta | 9.735 | 3.535 | 3.288 |
| 2025-10-31 | Sexta | 9.067 | 2.867 | 3.094 |
| 2025-10-10 | Sexta | 8.588 | 2.388 | 2.694 |
| 2025-11-20 | Quinta | 8.332 | 2.132 | 2.527 |
| 2025-11-19 | Quarta | 7.952 | 1.752 | 2.415 |
| 2025-12-18 | Quinta | 7.447 | 1.247 | 2.180 |
| 2025-12-30 | Terça | 7.343 | 1.143 | 2.202 |
| 2025-09-17 | Quarta | 7.194 | 994 | 2.693 |

> Todos os dias com BESS dead são **dias úteis**. Nenhum fim de semana
> apresentou consumo HP.

### 3.11 Distribuição do Consumo HP Diário

| Percentil | kWh/dia | Status |
|---|---|---|
| P10 | ~3.800 | ✅ BESS cobre facilmente |
| P25 | ~4.600 | ✅ BESS cobre facilmente |
| P50 | ~5.600 | ✅ BESS cobre |
| P75 | ~6.200 | ⚠ Limite da capacidade |
| P90 | ~6.800 | ❌ BESS esgota |
| P95 | ~7.300 | ❌ BESS esgota |
| Max | ~9.735 | ❌ BESS esgota (3.535 kWh residual) |

### 3.12 Resultados Financeiros — Solar + BESS

| Métrica | Valor |
|---|---|
| C1 — Base AZUL | R$ 12.247.670/ano |
| C3 — Solar+BESS VERDE | R$ 8.140.012/ano |
| **Economia anual** | **R$ 4.107.657** |
| **Payback simples** | **4,2 anos** |
| Payback descontado | 5,7 anos |
| TIR | 23,9% |
| VPL (10%) | R$ 20.188.879 |
| ROI (25 anos) | ~500% |

### 3.13 Resultados Financeiros — Somente Solar

| Métrica | Valor |
|---|---|
| C1 — Base AZUL | R$ 12.247.670/ano |
| C2 — Solar AZUL | R$ 10.397.467/ano |
| **Economia anual** | **R$ 1.850.202** |
| **Payback simples** | **4,7 anos** |
| TIR | 21,1% |
| VPL (10%) | R$ 8.094.361 |

### 3.14 Saídas Geradas

| Arquivo | Descrição |
|---|---|
| `data/bess_simulacao_diaria.csv` | 357 linhas — métricas BESS dia a dia |
| `data/modelamento_anual_resultado.csv` | 12 linhas — resultados mensais |

---

## 4. Cálculo de Fatura (Pacote `fatura/`)

### 4.1 Arquitetura

```
fatura/
├── __init__.py          # Exporta calcular_fatura_azul e calcular_fatura_verde
├── premissas.py         # Constantes tarifárias e tributárias
├── calculo_azul.py      # calcular_fatura_azul()
├── calculo_verde.py     # calcular_fatura_verde()
├── comparar.py          # Comparação AZUL vs VERDE
├── decompor.py          # Decomposição dos componentes da fatura
├── simular_azul.py      # Simulação parametrizada AZUL
├── simular_verde.py     # Simulação parametrizada VERDE
├── validar_azul.py      # Validação contra fatura real
└── tests/
    ├── test_azul.py     # Testes unitários AZUL
    ├── test_verde.py    # Testes unitários VERDE
    └── test_premissas.py
```

### 4.2 Fluxo de Cálculo — AZUL (`calculo_azul.py`)

```
Entrada: dem_HP_contrat, dem_FP_contrat, dem_HP_medida, dem_FP_medida,
         cons_HP_kWh, cons_FP_kWh

BLOCO 1 — Distribuidora (TUSD):
│
├─ Split tributário:
│   dem_faturada = max(contratada, medida)
│   tributada = medida  →  gross-up: base / FATOR_TRIBUTADO
│   isenta = faturada − medida  →  gross-up: base / FATOR_ISENTO_ICMS
│
├─ Desconto fonte incentivada (50% sobre demanda):
│   base_dem = dem × tarifa × (1 − 0.50)
│
├─ TUSD Energia:
│   valor_tusd_hp = (cons_HP/1000 × AZUL_TUSD_HP) / FATOR_TRIBUTADO
│   valor_tusd_fp = (cons_FP/1000 × AZUL_TUSD_FP) / FATOR_TRIBUTADO
│
├─ BEN (Benefício Ajuste Tributário):
│   ben_liquido = desconto_fonte_total (soma dos 50%)
│   impostos_ben = soma_itens_demanda(gross-up) − soma_itens_demanda(base)
│   ben_bruto = ben_liquido + impostos_ben
│
└─ Total_Distribuidora = soma_itens + encargos + ben_bruto − ben_liquido

BLOCO 2 — Comercializadora (TE):
│   base = (cons_HP + cons_FP) × 0,308 R$/kWh
└─  total = base / FATOR_COMERCIALIZADORA  (só ICMS)

BLOCO 3 — Custo Global:
    custo_total = Total_Distribuidora + Total_Comercializadora
```

### 4.3 Fluxo de Cálculo — VERDE (`calculo_verde.py`)

```
Entrada: dem_contrat (única, FP), dem_medida, cons_HP_kWh, cons_FP_kWh

BLOCO 1 — Distribuidora (TUSD):
│
├─ Demanda única: mesmo split tributário do AZUL
│
├─ TUSD Energia FP: base = cons_FP/1000 × VERDE_TUSD_FP
│
├─ TUSD Energia HP (com desconto 50% do diferencial):
│   tarifa_efetiva = VERDE_TUSD_FP + (VERDE_TUSD_HP − VERDE_TUSD_FP) × 0.5
│                  = 140,21 + (2.296,63 − 140,21) × 0,5 = R$ 1.218,42/MWh
│   base = cons_HP/1000 × tarifa_efetiva
│
├─ BEN: inclui desconto fonte (50% demanda) + desconto HP (50% diferencial)
│   desconto_hp = cons_HP_MWh × (VERDE_TUSD_HP − VERDE_TUSD_FP) × 0.5
│   ben_liquido = desconto_fonte + desconto_hp
│
└─ Total_Distribuidora = soma_itens + encargos + ben_bruto − ben_liquido

BLOCO 2 e 3: idêntico ao AZUL
```

### 4.4 Diferença Chave: AZUL vs VERDE

| Aspecto | AZUL | VERDE |
|---|---|---|
| Demandas contratadas | 2 (HP + FP) | 1 (FP) |
| Custo demanda HP | R$ 88,82/kW | R$ 0/kW |
| TUSD energia HP | R$ 140,21/MWh | R$ 2.296,63/MWh (efetiva ~R$ 1.218/MWh) |
| TUSD energia FP | R$ 140,21/MWh | R$ 140,21/MWh |
| Ideal para | Consumo HP alto | Consumo HP mínimo (BESS cobrindo) |

---

## 5. Comparativo de Resultados

### 5.1 Modelo A (MC) vs Modelo B (Dia a Dia)

| Métrica | Modelo A (MC) | Modelo B (Dia a Dia) | Delta |
|---|---|---|---|
| C1 AZUL (ano) | R$ 13.403.316 | R$ 12.247.670 | +R$ 1.155.646 |
| C3 VERDE+BESS (ano) | R$ 10.664.691 | R$ 8.140.012 | +R$ 2.524.679 |
| **Economia anual** | **R$ 2.738.625** | **R$ 4.107.657** | **−R$ 1.369.032** |
| **Payback simples** | **6,2 anos** | **4,2 anos** | **+2,0 anos** |
| TIR | 15,6% | 23,9% | −8,3 pp |
| Cobertura BESS | 74,1% | 94,0% | −19,9 pp |
| HP residual/dia (mediano) | 2.099 kWh | ~351 kWh (85.551/244) | +1.748 kWh |

### 5.2 Fontes da Diferença

1. **HP residual muito maior no MC (+1.748 kWh/dia):**
   O dia mediano do MC tem 8.099 kWh de HP, mas o BESS só carrega 6.000 kWh.
   No dia a dia, muitos dias têm HP < 6.000 kWh e o BESS cobre tudo. A mediana
   captura um "dia médio-alto" onde o BESS sempre é insuficiente, enquanto na
   realidade a maioria dos dias é coberta integralmente.

2. **Extrapolação × 30 × 12 vs faturamento mensal real:**
   O MC assume 30 dias úteis/mês (360/ano), mas realisticamente são 244 dias
   úteis + 113 fins de semana. O modelo dia a dia fatura cada mês com os
   dias reais, incluindo meses mais curtos e menos dias úteis (Ago com 14 dias
   úteis vs Out com 23).

3. **Demanda constante vs variável:**
   O MC usa demanda mediana (1.916 kW HP, 2.247 kW FP), nunca gerando
   ultrapassagem. O dia a dia captura meses com demanda > 2.980 kW (Set, Out),
   que geram multa de ultrapassagem.

4. **Sem sazonalidade solar:**
   O MC usa geração solar média diária (8.586 kWh). O dia a dia usa geração
   real por mês — Ago tem mais sol que Jun.

### 5.3 Quando Usar Cada Modelo

| Situação | Modelo Recomendado |
|---|---|
| Proposta comercial rápida | A (Monte Carlo) — payback conservador |
| Análise detalhada/due diligence | B (Dia a Dia) — mais realista |
| Apresentação visual para cliente | A — gráfico do dia típico intuitivo |
| Dimensionamento do BESS | B — identifica dias críticos |
| Negociação de contrato de demanda | B — mostra ultrapassagens |

### 5.4 Conclusão

O modelo dia a dia (B) é **mais otimista** e realista, com payback de 4,2 anos
vs 6,2 do MC (A). A diferença se deve principalmente à simplificação do MC
de usar um único dia mediano — que concentra HP acima da capacidade do BESS —
enquanto na realidade a maioria dos dias tem HP menor que a capacidade.

O MC funciona como estimativa **conservadora** (pessimista), útil para
proposta comercial onde se quer um piso de performance. O dia a dia é a
referência para decisão de investimento.

---

## 6. Estrutura do Repositório

```
kira-bess-modelamento/
├── modelamento_anual.py          # Modelo B — Dia a Dia (15 min)
├── montecarlo_dia_tipico.py      # Modelo A — Monte Carlo (dia típico)
├── DOCUMENTACAO_MODELAMENTO.md   # Esta documentação
├── requirements.txt              # pandas, numpy, plotly
│
├── fatura/                       # Pacote de cálculo de fatura
│   ├── __init__.py
│   ├── premissas.py              # Constantes tarifárias
│   ├── calculo_azul.py           # Heurística AZUL
│   ├── calculo_verde.py          # Heurística VERDE
│   ├── comparar.py               # Comparação AZUL vs VERDE
│   ├── decompor.py               # Decomposição de fatura
│   ├── simular_azul.py           # Simulação parametrizada
│   ├── simular_verde.py          # Simulação parametrizada
│   ├── validar_azul.py           # Validação contra fatura real
│   └── tests/
│       ├── test_azul.py
│       ├── test_verde.py
│       └── test_premissas.py
│
├── data/                         # Dados de entrada e saída
│   ├── iplenix_*.csv             # 15 CSVs de medição (15 min)
│   ├── Shopping Rio Poty_*.CSV   # PVsyst (8.760 h)
│   ├── bess_simulacao_diaria.csv # Saída Modelo B (357 dias)
│   ├── modelamento_anual_resultado.csv  # Saída Modelo B (12 meses)
│   └── dia_tipico_mediano.csv    # Saída Modelo A (96 slots)
│
└── output/                       # Gráficos gerados
    ├── dia_tipico_perfil.html    # Dia típico — HP/FP + SOC
    └── bootstrap_distribuicao.html # Histograma Bootstrap
```

### 6.1 Como Executar

```bash
# Instalar dependências
pip install -r requirements.txt

# Modelo A — Monte Carlo (dia típico)
python montecarlo_dia_tipico.py

# Modelo B — Dia a Dia (15 min)
python modelamento_anual.py

# Testes
pytest fatura/tests/ -v
```

---

## 7. Glossário

| Termo | Definição |
|---|---|
| **BESS** | Battery Energy Storage System — sistema de armazenamento por bateria |
| **Bootstrap MC** | Método estatístico de reamostragem com reposição |
| **C-rate** | Taxa de carga/descarga relativa à capacidade (1C = carga em 1h) |
| **Delta-correction** | Ajuste sazonal por razão de percentis entre períodos |
| **DT** | Intervalo de tempo = 0,25h (15 minutos) |
| **FP** | Fora de Ponta — período com tarifa mais barata |
| **Grid margin** | Fração da demanda mantida no grid (5%) para evitar injeção |
| **Gross-up** | Cálculo de imposto "por dentro" (base / fator complementar) |
| **HP** | Horário de Ponta — período com tarifa mais cara (~18h30–21h30) |
| **Injeção reversa** | Fluxo de energia do consumidor para a rede (proibido) |
| **PVsyst** | Software de simulação de geração fotovoltaica |
| **SOC** | State of Charge — nível de carga da bateria (kWh) |
| **Split tributário** | Separação da demanda em parcelas tributada e isenta ICMS |
| **TE** | Tarifa de Energia — componente da comercializadora |
| **TIR** | Taxa Interna de Retorno |
| **TUSD** | Tarifa de Uso do Sistema de Distribuição |
| **VPL** | Valor Presente Líquido |
