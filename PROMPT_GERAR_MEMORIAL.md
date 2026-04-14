# Prompt — Gerar Memorial de Cálculo para o kira-data

> Cole este prompt no agente do `kira-bess-modelamento` para gerar o arquivo de saída.

---

## Objetivo

Gerar o arquivo `data/memorial_de_calculo.md` — um memorial de cálculo técnico completo, extraído **diretamente do código-fonte** deste repositório (`kira-bess-modelamento`). Este arquivo será consumido pelo frontend `kira-data` e exibido na seção Engenharia do Data Room.

## Por quê

Hoje o `kira-data` mantém uma cópia manual do memorial (`src/data/memorial.ts`) que ficou desatualizada: parâmetros como janela de carga, capacidade do BESS e TE da comercializadora divergem do código real. Para garantir **single source of truth**, o memorial deve ser gerado automaticamente a partir dos arquivos-fonte deste repositório.

## Fontes de dados (leia todos antes de gerar)

1. **`fatura/premissas.py`** — todas as constantes tarifárias, tributárias e de equipamento
2. **`modelamento_anual.py`** — lógica completa do Modelo B (dia-a-dia), parâmetros BESS, janelas horárias, peak-shaving FDS
3. **`montecarlo_dia_tipico.py`** — lógica do Modelo A (bootstrap Monte Carlo)
4. **`fatura/calculo_azul.py`** + **`fatura/calculo_verde.py`** — fórmulas de faturamento
5. **`exportar_audit_data.py`** — lógica de exportação e resultados financeiros
6. **`DOCUMENTACAO_MODELAMENTO.md`** — documentação existente (use como referência de estrutura, mas **extraia valores do código, não da doc**)
7. **`data/modelamento_anual_resultado.csv`** — resultados mensais reais (12 linhas)
8. **`data/bess_simulacao_diaria.csv`** — resultados diários (357 dias)
9. **`data/audit_data.json`** — JSON exportado com todos os resultados consolidados

## Estrutura obrigatória do memorial

O arquivo gerado deve conter **exatamente** estas seções, nesta ordem:

### Cabeçalho
```
# Memorial de Cálculo — Simulação BESS + Solar
**Gerado automaticamente** a partir do código-fonte de `kira-bess-modelamento`
**Commit:** [hash do HEAD atual]
**Data de geração:** [data atual]
**Unidade Consumidora:** Shopping Rio Poty — Teresina/PI
```

### Seções

1. **Sistema Proposto** — Tabela com TODOS os parâmetros do BESS e solar, extraídos do código:
   - Capacidade BESS (kWh), potência carga (kW), potência descarga (kW)
   - Janela de carga (início–fim, número de slots)
   - Janela de ponta (início–fim, número de slots)  
   - Margem anti-injeção (%)
   - Comportamento em fins de semana (cap de demanda FP, constante `BESS_WEEKEND_DEM_CAP`)
   - Solar FV (kWp)
   - Fonte do perfil solar (PVsyst)

2. **Contrato de Demanda** — Demanda HP e FP contratadas (do código, não hardcoded)

3. **CAPEX** — Tabela itemizada (Solar, BESS, Engenharia, Total)

4. **Premissas Tarifárias** — Extrair TUDO de `premissas.py`:
   - Impostos (PIS, COFINS, ICMS) com valores e fatores derivados
   - Tarifa AZUL (demanda HP/FP, TUSD HP/FP)
   - Tarifa VERDE (demanda única, TUSD HP/FP)
   - Desconto fonte incentivada
   - TE Comercializadora
   - Fórmulas de gross-up

5. **Modelo A — Dia Típico (Monte Carlo)** — Resumo do algoritmo bootstrap:
   - Pool de amostragem, número de iterações, critério de convergência
   - Simulação BESS no dia típico
   - Extrapolação para 12 meses

6. **Modelo B — Dia a Dia (15 min)** — Descrição completa:
   - Carga de dados (meses reais vs ajustados)
   - Delta-correction (motivação, algoritmo, aplicação)
   - Classificação de dias (útil/FDS/feriado)
   - Ciclo BESS dia útil (carga, descarga, standby)
   - **Comportamento BESS em fins de semana** (peak-shaving FP, cap 2.800 kW)
   - Faturamento C1/C2/C3

7. **Cálculo de Fatura** — Resumo das fórmulas:
   - AZUL: componentes (demanda usada, não usada, TUSD, ultrapassagem, TE)
   - VERDE: componentes (demanda única, TUSD HP ponta, desconto incentivada, TE)
   - Split tributário (tributada vs isenta ICMS)

8. **Resultados Financeiros** — Extrair do `audit_data.json` ou dos CSVs:
   - Tabela comparativa C1 vs C2 vs C3 (custo mensal, economia, %)
   - VPL, payback, ROI para Solar+BESS e Somente Solar
   - Decomposição da economia

9. **Resultados Mensais** — Tabela 12 meses do `modelamento_anual_resultado.csv`:
   - Colunas: mês, custo C1, custo C2, custo C3, economia, demanda HP medida, demanda FP medida, dias BESS

10. **Cobertura e Confiabilidade do BESS**:
    - Dias com esgotamento
    - % de cobertura HP
    - Outlier total (kWh)

11. **Glossário** — Termos técnicos usados no memorial

## Regras de extração

- **NUNCA** hardcode valores. Extraia do código Python real (`premissas.py`, `modelamento_anual.py`, etc.)
- Se um valor aparece em `premissas.py` E no `DOCUMENTACAO_MODELAMENTO.md` e eles divergem, **use o de `premissas.py`** (código é a verdade)
- Formate valores monetários como `R$ X.XXX,XX` (formato brasileiro)
- Use tabelas Markdown para dados tabulares
- Use fórmulas LaTeX ($...$) para equações
- Inclua o hash do commit no cabeçalho para rastreabilidade

## Formato de saída

- Arquivo: `data/memorial_de_calculo.md`
- Encoding: UTF-8
- Tamanho esperado: ~15–25 KB
- Linguagem: Português técnico

## Validação

Depois de gerar, confirme que:
1. A capacidade do BESS bate com o código (`modelamento_anual.py`)
2. A janela de carga bate com o código
3. A TE da comercializadora bate com `premissas.py`
4. Os custos mensais batem com `modelamento_anual_resultado.csv`
5. O comportamento de FDS bate com o código (peak-shaving FP, cap de demanda)
