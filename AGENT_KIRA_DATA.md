# Script para o Agente do kira-data

> Cole este prompt inteiro no agente que gerencia o repositório `kira-data`.

---

## Contexto

O repositório `kira-bess-modelamento` acabou de atualizar o arquivo `src/data/audit_data.json` com dados da simulação dia-a-dia (365 dias × 96 slots de 15 min). O JSON já foi escrito diretamente em `kira-data/src/data/audit_data.json`.

A metodologia agora é **dia-a-dia real** (não mais Monte Carlo). Todos os números financeiros são oficiais.

## O que mudou no schema do `audit_data.json`

### Campos removidos (era do Monte Carlo — não existem mais)
- `perfil.n_dias_mc` → substituído por `perfil.n_dias_simulados`
- `bess.iteracoes_convergencia` → removido (não há mais convergência iterativa)
- `bess.soc_regime_kwh` → removido

### Campos que continuam iguais (não mexer)
- `premissas` — mesmo schema, mesmos 17 campos
- `demandas` — mesmo schema (c1/c2/c3)
- `consumos` — mesmo schema (c1/c2/c3)
- `fatura_azul_c1_detalhe` — mesmo schema (20 campos)
- `faturas` — mesmo schema (c1/c2/c3 com custo_total etc)
- `financeiro` — campos antigos mantidos (eco_solar_mes, eco_total_mes, eco_anual, capex_*, payback_simples, vpl, tir, roi, taxa_desconto, vida_util)
- `perfil` — arrays 96-slot mantidos (perfil_horario_demanda, perfil_horario_solar, perfil_horario_grid_c3, horas, is_ponta)
- `bess` — campos mantidos (capacidade_kwh, potencia_saida_kw, potencia_carga_kw, carga_janela, descarga_janela, energia_carga_kwh_dia, energia_descarga_kwh_dia)

### Campos novos disponíveis

#### `_meta` (novo top-level)
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

#### `perfil` (campos novos)
- `perfil.n_dias_simulados` — substitui n_dias_mc (357 dias reais)
- `perfil.metodologia_perfil` — "mediana_dias_reais (visual only)"
- `perfil.perfil_horario_soc` — array 96 floats, SOC da bateria por slot (kWh)
- `perfil.geracao_anual_mwh` — mantido
- `perfil.geracao_pico_kw` — mantido

#### `bess` (campos novos)
- `bess.grid_margin_pct` — 5.0 (margem anti-injeção)
- `bess.cobertura_bess_pct` — 94.0 (% do consumo HP coberto pelo BESS)
- `bess.dias_bess_dead` — 18 (dias onde BESS não cobriu 100%)

#### `financeiro` (campos novos)
- `financeiro.eco_bess_mes` — economia mensal só do BESS
- `financeiro.payback_descontado` — payback ajustado pela taxa de desconto
- `financeiro.solar_payback` — payback do solar-only
- `financeiro.solar_vpl` — VPL do solar-only
- `financeiro.solar_tir` — TIR do solar-only
- `financeiro.solar_roi` — ROI do solar-only

#### `resumo_mensal` (novo top-level — array de 12 objetos)
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
  },
  ...
]
```

#### `outliers` (novo top-level)
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
    },
    ...
  ]
}
```

## Números oficiais (para referência)

| Métrica | Valor |
|---|---|
| C1 AZUL mensal | R$ 1.020.639 |
| C2 Solar mensal | R$ 866.456 |
| C3 VERDE+BESS mensal | R$ 678.334 |
| Economia mensal | R$ 342.305 |
| Economia anual | R$ 4.107.657 |
| Payback simples | 4,2 anos |
| TIR | 23,9% |
| VPL | R$ 20.188.878 |
| ROI | 501% |
| Cobertura BESS | 94,0% |

## Tarefas para o agente kira-data

### 1. Corrigir referências quebradas (OBRIGATÓRIO)
Nenhuma página usa `n_dias_mc`, `iteracoes_convergencia` ou `soc_regime_kwh` diretamente, então nada deve quebrar. Mas verifique se alguma referência foi adicionada depois.

### 2. Criar tipos TypeScript (RECOMENDADO)
Criar `src/types/audit.ts` com interfaces tipadas para o JSON. Atualmente tudo é `as Record<string, unknown>`, o que é frágil. Sugestão:

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

### 3. Melhorias sugeridas nas páginas (OPCIONAL)

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

### 4. Novo componente sugerido: Gráfico Mensal (OPCIONAL)
O `resumo_mensal` permite um gráfico de barras empilhadas com 12 meses mostrando:
- C1 vs C2 vs C3 por mês (economia visual mês a mês)
- Consumo HP vs FP vs Solar por mês
- Dias BESS dead por mês (barras vermelhas)

### 5. Novo componente sugerido: Tabela de Outliers (OPCIONAL)
Com `outliers.dias`, pode-se mostrar uma tabela dos 18 dias onde o BESS não deu conta, com:
- Data e dia da semana
- Consumo HP total vs residual
- % de cobertura naquele dia
- Ajuda o investidor a entender o risco

## Compatibilidade retroativa

O JSON mantém TODOS os campos que as 4 páginas atuais usam. As únicas diferenças:
- `perfil.n_dias_mc` foi renomeado para `perfil.n_dias_simulados` (nenhuma página usa esse campo)
- `bess.iteracoes_convergencia` e `bess.soc_regime_kwh` foram removidos (nenhuma página usa)

**Nenhuma página vai quebrar** com o novo JSON. As mudanças são aditivas.
