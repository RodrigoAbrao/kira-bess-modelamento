# Kira BESS Modelamento

Modelamento financeiro avançado para sistema **Solar + BESS** (Battery Energy Storage System) com **duas metodologias** complementares de simulação.

## 📊 Visão Geral

Este repositório contém modelos profundamente documentados para análise de viabilidade financeira de um sistema híbrido Solar FV + BESS para shopping center no Mercado Livre de Energia.

### Sistema Proposto

- **Solar FV:** 1.890 kWp (perfil PVsyst)
- **BESS:** 6.200 kWh úteis / 3.100 kW descarga / 1.000 kW carga
- **CAPEX Total:** R$ 17,1 milhões
- **Dataset:** 15 CSVs iplenix (Nov/24–Jan/26) + PVsyst 8.760h

## 🎯 Modelos Implementados

### Modelo A — Dia Típico (Bootstrap Monte Carlo)

**Arquivo:** `montecarlo_dia_tipico.py`

Bootstrap com **K = 1.000 dias sintéticos** → mediana element-wise → simulação BESS no dia típico mediano → extrapolação anual (30 dias/mês × 12).

**Resultados:**
- ✅ Cobertura BESS: **74,1%**
- 💰 Economia anual: **R$ 2,74 milhões**
- 📈 Payback: **6,2 anos** | TIR: **15,6%** | VPL: **R$ 7,76 M**
- 📊 **Outputs:** CSV + 2 gráficos Plotly (perfil diário + distribuição bootstrap)

**Quando usar:** Proposta comercial rápida, apresentação visual intuitiva para clientes.

---

### Modelo B — Iteração Dia a Dia (15 min)

**Arquivo:** `modelamento_anual.py`

Simulação granular de **357 dias individuais** (96 slots × 15 min) com delta-correction sazonal (9 meses ajustados).

**Resultados:**
- ✅ Cobertura BESS: **94,0%**
- 💰 Economia anual: **R$ 4,11 milhões**
- 📈 Payback: **4,2 anos** | TIR: **23,9%** | VPL: **R$ 20,19 M**
- 📊 **Outputs:** 2 CSVs (357 dias + 12 meses)

**Quando usar:** Análise detalhada, due diligence, dimensionamento técnico.

---

## 📦 Pacote `fatura/`

Cálculo heurístico de faturas AZUL e VERDE com split tributário brasileiro (ICMS, PIS, COFINS).

- ✅ **75 testes unitários** (pytest) — 100% pass
- 📘 Docstrings detalhadas explicando tributos "por dentro" (gross-up)
- ⚙️ Suporta desconto de fonte incentivada (50%) e desconto VERDE HP

**Módulos principais:**
- `premissas.py` — Constantes tarifárias e tributárias
- `calculo_azul.py` — Fatura AZUL (demanda HP/FP separada)
- `calculo_verde.py` — Fatura VERDE (TUSD HP cara, demanda única)

---

## 📚 Documentação Técnica

**`DOCUMENTACAO_MODELAMENTO.md`** — ~550 linhas cobrindo:

1. **Premissas Comuns:** Equipamentos, contrato, CAPEX, tarifas
2. **Algoritmo Bootstrap:** Por que mediana? Por que K=1000?
3. **Delta-Correction:** Ajuste sazonal P90 com dual delta (mediana + P95)
4. **Simulação BESS:** Margem anti-injeção de 5%, janelas carga/descarga
5. **Faturamento AZUL vs VERDE:** Quando cada modalidade é vantajosa
6. **Comparativo de Resultados:** MC 6,2yr vs Dia-a-Dia 4,2yr — diferença de R$ 1,37M/ano explicada
7. **Glossário:** Termos técnicos do setor elétrico brasileiro

---

## 🚀 Como Executar

```bash
# 1. Clonar repositório
git clone https://github.com/RodrigoAbrao/kira-bess-modelamento.git
cd kira-bess-modelamento

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Rodar Modelo A (Monte Carlo)
python montecarlo_dia_tipico.py
# → Outputs: data/dia_tipico_mediano.csv + 2 HTMLs em output/

# 4. Rodar Modelo B (Dia a Dia)
python modelamento_anual.py
# → Outputs: 2 CSVs em data/

# 5. Rodar testes
pytest fatura/tests/ -v
# → 75 passed
```

---

## 📂 Estrutura do Repositório

```
kira-bess-modelamento/
├── modelamento_anual.py          # Modelo B — Dia a Dia (15 min)
├── montecarlo_dia_tipico.py      # Modelo A — Monte Carlo
├── DOCUMENTACAO_MODELAMENTO.md   # Documentação técnica completa
├── requirements.txt              # pandas, numpy, plotly
│
├── fatura/                       # Pacote de cálculo de fatura
│   ├── premissas.py              # Constantes tarifárias
│   ├── calculo_azul.py           # Heurística AZUL
│   ├── calculo_verde.py          # Heurística VERDE
│   └── tests/                    # 75 testes unitários
│
├── data/                         # Dados de entrada + saídas
│   ├── iplenix_*.csv             # 15 CSVs de medição (15 min)
│   ├── Shopping Rio Poty_*.CSV   # PVsyst (8.760 h)
│   ├── bess_simulacao_diaria.csv # Saída Modelo B
│   └── dia_tipico_mediano.csv    # Saída Modelo A
│
└── output/                       # Gráficos gerados
    ├── dia_tipico_perfil.html    # Perfil do dia típico + SOC BESS
    └── bootstrap_distribuicao.html # Histograma Bootstrap (1000 amostras)
```

---

## 🔍 Principais Features

- ✅ **Bootstrap robusto:** Mediana de 1.000 reamostragens (breakdown point 50%)
- ✅ **Delta-correction sazonal:** P90 threshold com dual delta (mediana + P95)
- ✅ **Margem anti-injeção:** 5% da demanda permanece no grid (proteção relé)
- ✅ **Split tributário automático:** Demanda usada (tributada) vs não usada (isenta ICMS)
- ✅ **Desconto fonte incentivada:** 50% sobre demanda e diferencial HP VERDE
- ✅ **Análise de outliers:** 18 dias críticos onde BESS esgota (SOC → 0)
- ✅ **Testes unitários:** 75 testes cobrindo todos os componentes de fatura

---

## 📊 Comparativo de Resultados

| Métrica | Modelo A (MC) | Modelo B (Dia-a-Dia) | Δ |
|---|---|---|---|
| **Payback** | **6,2 anos** | **4,2 anos** | +2,0 anos |
| TIR | 15,6% | 23,9% | −8,3 pp |
| VPL | R$ 7,76 M | R$ 20,19 M | +R$ 12,43 M |
| Cobertura BESS | 74,1% | 94,0% | −19,9 pp |
| Economia/ano | R$ 2,74 M | R$ 4,11 M | −R$ 1,37 M |

**Por que o MC é mais conservador?**

O dia mediano tem HP = 8.099 kWh, acima da capacidade do BESS (6.200 kWh). Na realidade, 75% dos dias têm HP < 6.200 kWh e são cobertos integralmente — a mediana captura um "dia médio-alto" onde o BESS sempre é insuficiente, enquanto o dia-a-dia captura toda a variabilidade real.

---

## 🧑‍💻 Autor

**Rodrigo Abrão** — Kira Engenharia  
Engenheiro Eletricista + Cientista de Dados

---

## 📄 Licença

Este repositório contém código proprietário da Kira Engenharia para modelamento avançado de sistemas BESS.

---

## 🏷️ Tags

`#BESS` `#EnergyStorage` `#SolarEnergy` `#BoostrapMonteCarlo` `#FinancialModeling` `#Python` `#Pandas` `#Plotly` `#MercadoLivreEnergia` `#TarifaBranca` `#PeakShaving`
