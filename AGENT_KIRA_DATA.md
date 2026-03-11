# Documentação de Outputs — kira-bess-modelamento

> Referência completa de todos os arquivos de saída gerados por este repositório.
> O frontend `kira-data` consome estes dados.

---

## Contexto

O repositório `kira-bess-modelamento` simula um sistema BESS (Battery Energy Storage System) acoplado a uma usina solar para o **Shopping Rio Poty** (Equatorial Piauí, tarifa VERDE/AZUL). A simulação roda **dia-a-dia** sobre 12 meses de dados reais de 15 min (357 dias × 96 slots = ~34 mil registros de demand/consumo).

### Parâmetros do sistema

| Parâmetro | Valor |
|---|---|
| Capacidade BESS | 6.200 kWh |
| Potência descarga | 3.100 kW |
| Potência carga | 1.000 kW |
| Janela de carga | 07:30–15:00 |
| Janela de ponta | 17:30–20:29 (só dias úteis) |
| Cap demanda FDS | 2.800 kW |
| Margem anti-injeção | 5% |
| Demanda contratada HP | 2.980 kW |
| Demanda contratada FP | 3.280 kW |
| CAPEX total | R$ 17.096.491 |

### Metodologia

Simulação dia-a-dia real (não Monte Carlo). SOC carrega entre dias (carry-over). Dados brutos vindos do iPlenix (medidor de 15 min) + PVSyst (geração solar horária).

**Comportamento por tipo de dia:**
- **Dias úteis com ponta**: BESS carrega 07:30–15:00, descarrega na ponta (17:30–20:29) cobrindo até 95% da demanda HP.
- **Fins de semana (sáb/dom)**: Não existe HP — tudo é FP. BESS carrega 07:30–15:00 e faz peak-shaving FP, garantindo que a demanda líquida nunca ultrapasse **2.800 kW**. *(Heurística ajustável — constante `BESS_WEEKEND_DEM_CAP` em `modelamento_anual.py`.)*
- **Feriados em dia útil**: BESS permanece idle, SOC carrega para o próximo dia.

---

## Arquivos de Saída

Todos os arquivos ficam na pasta `data/` deste repositório.

| # | Arquivo | Gerado por | Linhas | Descrição |
|---|---------|------------|--------|-----------|
| 1 | `audit_data.json` | `exportar_audit_data.py` | ~1 | JSON completo para o frontend (premissas, perfis, faturas, financeiro, glossário) |
| 2 | `bess_simulacao_diaria.csv` | `modelamento_anual.py` | 357 | Uma linha por dia simulado — consumos, demandas, BESS, solar |
| 3 | `modelamento_anual_resultado.csv` | `modelamento_anual.py` | 12 | Agregação mensal — custos C1/C2/C3, demandas, contadores |
| 4 | `bess_timeline_15min.csv` | `modelamento_anual.py` | ~34.000 | Timeline slot-a-slot — SOC, BESS kW, demanda, solar (~1.9 MB) |

O frontend `kira-data` atualmente consome apenas o `audit_data.json` (copiado para `kira-data/src/data/audit_data.json`). Os CSVs são referência para validação e para futuros gráficos interativos.

---

## 1. `bess_simulacao_diaria.csv` — Simulação diária (357 dias)

Uma linha por dia. 15 colunas.

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `dia` | date | — | Data do dia (ex: `2025-02-01`) |
| `mes` | string | — | Mês abreviado (`Nov`, `Dez`, `Jan`, ..., `Out`) |
| `tipo` | string | — | `Real` (dados brutos) ou `Ajustado` (projeção via delta-correction) |
| `dow` | string | — | Dia da semana em inglês (`Monday`, ..., `Sunday`) |
| `has_ponta` | bool | — | `True` se o dia teve consumo no horário de ponta |
| `cons_hp_total` | float | kWh | Consumo total no horário de ponta |
| `cons_hp_residual` | float | kWh | Consumo de ponta NÃO coberto pelo BESS (resíduo) |
| `cons_fp_total` | float | kWh | Consumo total fora de ponta |
| `cons_fp_net` | float | kWh | Consumo FP líquido (FP − solar + carga BESS) |
| `dem_hp_max` | float | kW | Demanda máxima instantânea na ponta |
| `dem_fp_max` | float | kW | Demanda máxima fora de ponta (sem solar) |
| `dem_hp_resid` | float | kW | Demanda máxima residual de ponta pós-BESS |
| `solar_saving` | float | kWh | Energia economizada pelo solar (abatida do FP) |
| `bess_charge_kwh` | float | kWh | Energia carregada no BESS naquele dia |
| `bess_dead` | bool | — | `True` se SOC chegou a ≤1 kWh durante a ponta |

**Exemplo:**
```csv
dia,mes,tipo,dow,has_ponta,cons_hp_total,cons_hp_residual,cons_fp_total,cons_fp_net,dem_hp_max,dem_fp_max,dem_hp_resid,solar_saving,bess_charge_kwh,bess_dead
2025-02-01,Fev,Ajustado,Saturday,True,6321.83,307.29,36710.24,34362.19,2311.39,2403.43,113.26,8548.05,6200.00,False
```

---

## 2. `modelamento_anual_resultado.csv` — Resultado mensal (12 meses)

Uma linha por mês. 16 colunas.

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `mes` | string | — | Mês abreviado |
| `c1` | float | R$ | **Cenário 1**: fatura AZUL sem solar nem BESS |
| `c2` | float | R$ | **Cenário 2**: fatura AZUL com solar, sem BESS |
| `c3` | float | R$ | **Cenário 3**: fatura VERDE com solar + BESS |
| `cons_hp` | float | kWh | Consumo total de ponta no mês |
| `cons_fp` | float | kWh | Consumo total fora de ponta no mês |
| `cons_hp_resid` | float | kWh | Consumo de ponta residual (não coberto pelo BESS) |
| `cons_fp_net` | float | kWh | Consumo FP líquido mensal |
| `solar_gen` | float | kWh | Geração solar no mês |
| `dem_hp` | float | kW | Demanda máxima de ponta no mês |
| `dem_fp` | float | kW | Demanda máxima fora de ponta no mês |
| `dem_verde` | float | kW | Demanda única VERDE = max(dem_fp_bess, dem_hp_resid) |
| `dem_hp_resid` | float | kW | Demanda máxima residual de ponta no mês |
| `n_ponta` | int | dias | Dias com consumo de ponta |
| `n_overflow` | int | dias | Dias onde BESS não cobriu 100% do pico |
| `n_bess_dead` | int | dias | Dias onde SOC chegou a ≤1 kWh na ponta |

**Exemplo:**
```csv
mes,c1,c2,c3,cons_hp,cons_fp,cons_hp_resid,cons_fp_net,solar_gen,dem_hp,dem_fp,dem_verde,dem_hp_resid,n_ponta,n_overflow,n_bess_dead
Nov,1107097.99,948784.61,741807.96,192262.42,1172892.98,11750.81,1076021.02,264699.57,2902.07,2829.11,2503.21,2482.56,31,31,5
```

---

## 3. `bess_timeline_15min.csv` — Timeline 15 minutos (NOVO)

Um registro por slot de medição, para todos os 357 dias (67.926 linhas, ~3.8 MB). Os timestamps refletem os intervalos reais do medidor iPlenix (~5 a 15 min). Ideal para gráficos interativos com zoom/scroll.

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `timestamp` | datetime | — | Timestamp do slot (ex: `2025-02-01 00:00:00`) |
| `dem_hp_kw` | float | kW | Demanda de ponta naquele slot (0 fora da ponta) |
| `dem_fp_kw` | float | kW | Demanda fora de ponta naquele slot |
| `solar_kw` | float | kW | Geração solar naquele slot |
| `soc_kwh` | float | kWh | Estado de carga da bateria (0 a 6.200) |
| `bess_kw` | float | kW | Potência BESS: **positivo** = carregando, **negativo** = descarregando |
| `cons_hp_kwh` | float | kWh | Consumo de ponta no slot (dem × 0.25h) |
| `cons_fp_kwh` | float | kWh | Consumo fora de ponta no slot (dem × 0.25h) |
| `demanda_bruta_kw` | float | kW | Demanda total medida = `dem_hp_kw + dem_fp_kw` |
| `demanda_solar_kw` | float | kW | Demanda pós-solar = `max(0, bruta − solar_kw)` |
| `demanda_liquida_kw` | float | kW | Demanda na rede (C3) = `max(0, bruta − solar + bess_kw)` |

**Convenção de sinais do `bess_kw`:**
- `+1000` → BESS carregando a 1.000 kW (consome da rede)
- `−3100` → BESS descarregando a 3.100 kW (injeta no consumo)
- `0` → BESS inativo

**Uso no frontend:** O CSV contém todas as séries temporais necessárias para plotar a demanda em qualquer cenário:
- `demanda_bruta_kw` — demanda medida (sem solar, sem BESS)
- `demanda_solar_kw` — demanda com solar (sem BESS)
- `demanda_liquida_kw` — demanda na rede C3 (solar + BESS)
- `solar_kw`, `bess_kw`, `soc_kwh` — componentes individuais

Gráfico de área empilhada com rangeslider para navegar entre dias/semanas. Recharts ou similar com virtualização para ~68k pontos.

---

## 4. `audit_data.json` — Dados completos para o frontend

Gerado por `exportar_audit_data.py`. Contém TUDO que o frontend precisa: premissas, perfis horários, faturas, financeiro, glossário e metodologia.

### Top-level keys

```
audit_data.json
├── _meta                      # Metadados da simulação
├── premissas                  # Tarifas, impostos, parâmetros regulatórios (17 campos)
├── perfil                     # Perfis horários 96-slot + métricas de geração
├── bess                       # Configuração e performance do BESS
├── demandas                   # Demandas faturadas por cenário (C1/C2/C3)
├── consumos                   # Consumos por cenário (C1/C2/C3)
├── fatura_azul_c1_detalhe     # Fatura detalhada AZUL (20+ campos, mês exemplo)
├── faturas                    # Custos mensais médios por cenário
├── financeiro                 # Payback, TIR, VPL, ROI, economia
├── resumo_mensal              # Array de 12 objetos (mês a mês)
├── outliers                   # Dias onde BESS não cobriu 100%
├── glossario                  # Definição de cada campo (pt-BR)
└── metodologia_calculo        # Passo a passo das fórmulas (9 etapas)
```

### `_meta`

```json
{
  "gerado_por": "exportar_audit_data.py",
  "metodologia": "dia-a-dia (365 dias × 96 slots)",
  "nota": "Todos os números financeiros vêm da simulação dia-a-dia...",
  "dias_simulados": 357,
  "dias_com_ponta": 244,
  "dias_bess_dead": 18,
  "cobertura_bess_pct": 94.0
}
```

### `premissas` (17 campos)

Tarifas e impostos regulatórios. Exemplos:
- `AZUL_DEMANDA_HP`, `AZUL_DEMANDA_FP`, `VERDE_DEMANDA_UNICA`
- `TUSD_ENCARGOS_HP`, `TUSD_ENCARGOS_FP`, `TE_HP`, `TE_FP`
- `ICMS`, `PIS_COFINS`, `DESCONTO_FONTE`

### `perfil` (arrays 96-slot)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `horas` | float[96] | Horas do dia (0.0, 0.25, 0.50, ..., 23.75) |
| `is_ponta` | bool[96] | `true` nos slots 17:30–20:14 |
| `perfil_horario_demanda` | float[96] | Demanda mediana por slot (kW) |
| `perfil_horario_solar` | float[96] | Geração solar mediana por slot (kW) |
| `perfil_horario_grid_c3` | float[96] | Demanda líquida pós-solar+BESS por slot (kW) |
| `perfil_horario_soc` | float[96] | SOC mediano da bateria por slot (kWh, 0–6200) |
| `n_dias_simulados` | int | 357 |
| `metodologia_perfil` | string | "mediana_dias_reais (visual only)" |
| `geracao_anual_mwh` | float | Geração solar anual total |
| `geracao_pico_kw` | float | Pico de geração solar |

### `bess`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `capacidade_kwh` | float | 6200 |
| `potencia_saida_kw` | float | 3100 |
| `potencia_carga_kw` | float | 1000 |
| `carga_janela` | string | "07:30–15:00" |
| `descarga_janela` | string | "17:30–20:29 (ponta)" |
| `energia_carga_kwh_dia` | float | Energia típica carregada por dia |
| `energia_descarga_kwh_dia` | float | Energia típica descarregada por dia |
| `grid_margin_pct` | float | 5.0 |
| `cobertura_bess_pct` | float | 94.0 |
| `dias_bess_dead` | int | 18 |

### `demandas` e `consumos`

Três cenários: `c1` (AZUL sem nada), `c2` (AZUL + solar), `c3` (VERDE + solar + BESS).
Cada um tem subcampos como `dem_hp`, `dem_fp`, `cons_hp`, `cons_fp`, etc.

### `fatura_azul_c1_detalhe` (20+ campos)

Fatura detalhada de um mês AZUL, com decomposição completa:
- Demanda: `dem_hp_faturada`, `dem_hp_tributada`, `dem_hp_isenta`, `dem_hp_ultrapassagem`
- Bases R$: `base_dem_hp_trib`, `base_dem_hp_isenta`, `base_dem_hp_ultra`
- Energia: `base_en_hp_trib`, `base_en_fp_trib`
- TUSD/TE: `base_tusd_hp`, `base_te_hp`
- Benefício I-5: `desconto_fonte_total`, `ben_liquido`
- **Ultrapassagem**: multiplicador é **2×** (200% da tarifa cheia)

### `faturas`

```json
{
  "c1": { "custo_total": 1020639 },
  "c2": { "custo_total": 866456 },
  "c3": { "custo_total": 678334 }
}
```

### `financeiro`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `eco_solar_mes` | float | Economia mensal do solar alone |
| `eco_bess_mes` | float | Economia mensal do BESS alone |
| `eco_total_mes` | float | Economia mensal total (solar + BESS + troca tarifária) |
| `eco_anual` | float | Economia anual total |
| `capex_solar` | float | R$ 5.700.000 |
| `capex_bess` | float | R$ 8.396.491 |
| `capex_implementacao` | float | R$ 3.000.000 |
| `capex_total` | float | R$ 17.096.491 |
| `payback_simples` | float | anos |
| `payback_descontado` | float | anos (ajustado pela taxa de desconto) |
| `vpl` | float | Valor Presente Líquido |
| `tir` | float | Taxa Interna de Retorno (%) |
| `roi` | float | Retorno sobre Investimento (%) |
| `taxa_desconto` | float | 10% |
| `vida_util` | int | 25 anos |
| `solar_payback` | float | Payback do solar-only |
| `solar_vpl` | float | VPL do solar-only |
| `solar_tir` | float | TIR do solar-only |
| `solar_roi` | float | ROI do solar-only |

### `resumo_mensal` (array de 12 objetos)

```json
[
  {
    "mes": "Nov",
    "c1": 1107803,
    "c2": 952694,
    "c3": 748985,
    "cons_hp_kwh": 128837,
    "cons_fp_kwh": 1236319,
    "cons_hp_resid_kwh": 10102,
    "solar_gen_kwh": 264700,
    "n_dias_ponta": 21,
    "n_bess_dead": 3
  }
]
```

### `outliers`

```json
{
  "total": 18,
  "hp_residual_anual_kwh": 18620,
  "dias": [
    {
      "dia": "2025-11-03",
      "dow": "Monday",
      "mes": "Nov",
      "hp_total_kwh": 9280,
      "hp_residual_kwh": 3080,
      "dem_hp_kw": 3093,
      "cobertura_pct": 66.8
    }
  ]
}
```

### `glossario`

Dicionário com definição em português de cada campo das faturas:
- `fatura_azul` — 20+ campos
- `fatura_verde` — 15+ campos
- `fatores_grossup` — fator_tributado, fator_isento_icms, fator_comercializadora
- `beneficio_tarifario` — desconto I-5, benefício bruto/líquido

### `metodologia_calculo`

9 passos com fórmulas detalhadas:
1. Split de demanda (tributada, isenta, ultrapassagem)
2. Bases de demanda (R$ antes de impostos)
3. Bases de energia (TUSD)
4. Cálculo TE
5. Gross-up tributário
6. Benefício I-5
7. Fatura total
8. Cenários C2 e C3
9. Análise financeira (payback, VPL, TIR)
}
---

## Números oficiais (última execução)

| Métrica | Valor |
|---|---|
| C1 AZUL mensal | R$ 1.024.834 |
| C2 Solar mensal | R$ 871.268 |
| C3 VERDE+BESS mensal | R$ 668.356 |
| Economia mensal | R$ 356.478 |
| Economia anual | R$ 4.277.737 |
| Payback simples | 4,0 anos |
| Payback descontado | 5,4 anos |
| TIR | 24,9% |
| VPL (10%) | R$ 21.732.700 |
| ROI (25 anos) | 526% |
| Cobertura BESS | 94,2% |

---

## Como re-gerar os outputs

```bash
# 1. Rodar a simulação anual (gera os 3 CSVs)
python modelamento_anual.py

# 2. Exportar o JSON para o frontend
python exportar_audit_data.py

# 3. Copiar o JSON para o kira-data (se necessário)
copy data\audit_data.json ..\kira-data\src\data\audit_data.json
```

---

## Tarefas para o agente kira-data

### 1. Atualizar `audit_data.json` (OBRIGATÓRIO)
Copiar o `data/audit_data.json` mais recente para `kira-data/src/data/audit_data.json`.

### 2. Criar tipos TypeScript (RECOMENDADO)
Criar `src/types/audit.ts` com interfaces tipadas para o JSON:

```ts
export interface AuditData {
  _meta: AuditMeta;
  premissas: Premissas;
  perfil: Perfil;
  bess: BessConfig;
  demandas: Demandas;
  consumos: Consumos;
  fatura_azul_c1_detalhe: FaturaAzulDetalhe;
  faturas: Faturas;
  financeiro: Financeiro;
  resumo_mensal: ResumoMensal[];
  outliers: Outliers;
}
```

### 3. Gráfico interativo de timeline 15-min (RECOMENDADO)
Usar `bess_timeline_15min.csv` para criar um gráfico scrollável/zoomável:
- **Eixo X**: timestamp (dias/horas)
- **Linha**: `soc_kwh` (estado de carga, eixo Y direito, 0–6200 kWh)
- **Barras/área**: `bess_kw` (positivo=carga, negativo=descarga)
- **Áreas**: `dem_hp_kw` (vermelho), `dem_fp_kw` (azul), `solar_kw` (dourado)
- **Rangeslider**: permite navegar entre dias e semanas
- Recharts ou similar com virtualização para ~68k pontos

### 4. Melhorias sugeridas nas páginas (OPCIONAL)

#### `/data-room` (Dashboard)
- Adicionar card com **Cobertura BESS**: `_meta.cobertura_bess_pct` (94%)
- Adicionar card com **Payback Descontado**: `financeiro.payback_descontado`
- Adicionar separação solar vs BESS na economia: `financeiro.eco_solar_mes` + `financeiro.eco_bess_mes`

#### `/data-room/energia`
- Usar `resumo_mensal` para gráfico de barras mensal (c1/c2/c3 por mês) — muito melhor que o chart fixo atual
- Adicionar curva SOC: `perfil.perfil_horario_soc` no gráfico horário
- Mostrar `_meta.dias_bess_dead` e `_meta.dias_com_ponta`

#### `/data-room/simulacao-fatura`
- Sem mudanças necessárias — os campos que essa página usa são todos compatíveis

#### `/data-room/relatorios`
- Usar `resumo_mensal` para tabela detalhada mês a mês
- Adicionar seção de outliers com `outliers.dias`
- Mostrar comparativo Solar-only (payback / TIR / VPL do solar-only sem BESS)

### 5. Novo componente sugerido: Gráfico Mensal (OPCIONAL)
O `resumo_mensal` permite um gráfico de barras empilhadas com 12 meses mostrando:
- C1 vs C2 vs C3 por mês (economia visual mês a mês)
- Consumo HP vs FP vs Solar por mês
- Dias BESS dead por mês (barras vermelhas)

### 6. Novo componente sugerido: Tabela de Outliers (OPCIONAL)
Com `outliers.dias`, pode-se mostrar uma tabela dos 18 dias onde o BESS não deu conta, com:
- Data e dia da semana
- Consumo HP total vs residual
- % de cobertura naquele dia
- Ajuda o investidor a entender o risco

## Compatibilidade retroativa

O JSON mantém TODOS os campos que as 4 páginas atuais usam. **Nenhuma página vai quebrar.** As mudanças são aditivas (campos novos, nenhum removido que estivesse em uso).
