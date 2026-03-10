"""
Premissas tarifárias para cálculo heurístico de fatura de energia.
==================================================================

Este módulo centraliza **todas** as constantes tarifárias e tributárias
utilizadas nos cálculos de fatura AZUL e VERDE.

Estrutura Tributária
--------------------
A fatura de energia no mercado regulado brasileiro (ACR/ACL) possui uma
estrutura de impostos em cascata:

- **PIS** (Programa de Integração Social): 0,7216%
- **COFINS** (Contribuição para Financiamento da Seguridade Social): 3,332%
- **ICMS** (Imposto sobre Circulação de Mercadorias): 22,50%

Os impostos são aplicados como **gross-up** (por dentro): o valor final
já inclui o imposto, que é calculado sobre a base líquida dividindo
pelo fator complementar::

    Valor_tributado = Base / [(1 − ICMS) × (1 − PIS − COFINS)]
    Valor_isento_ICMS = Base / (1 − PIS − COFINS)
    Valor_comercializadora = Base / (1 − ICMS)    (só ICMS, sem PIS/COFINS)

Modalidades Tarifárias
----------------------
**AZUL** (consumidores com separação HP/FP na demanda):
  - 2 demandas contratadas (HP e FP) em R$/kW.
  - TUSD energia HP e FP em R$/MWh.

**VERDE** (demanda única, mas energia HP diferenciada):
  - 1 demanda contratada (FP) em R$/kW.
  - TUSD FP em R$/MWh + TUSD HP muito mais caro (R$2.296,63/MWh).
  - Benefício: desconto de 50% no diferencial HP-FP para fontes incentivadas.

Desconto de Fonte Incentivada
------------------------------
Usinas solares, eólicas, biomassa e PCHs ≤ 30 MW recebem desconto de 50%
na TUSD de demanda (classificação I-5, conforme Resolução ANEEL nº 1.059/2023).

Comercializadora (TE)
---------------------
A Tarifa de Energia (TE) remunera a geração. No mercado livre, o contrato
com a comercializadora cobra TE = R$ 0,308/kWh (base, sem impostos).
Na comercializadora incide **apenas ICMS** (sem PIS/COFINS), diferente
da distribuidora onde incidem os 3 tributos.

Premissas importantes
---------------------
- Na parte da comercializadora (TE), incide apenas ICMS (sem PIS/COFINS).
- Valores de TUSD estão em R$/MWh.
- Valores de demanda estão em R$/kW.
- Alíquotas de PIS, COFINS e ICMS são as vigentes informadas pelo usuário.
"""

# ─── Impostos ───────────────────────────────────────────────────────────────────
PIS: float = 0.007216          # 0,7216 %
COFINS: float = 0.033320       # 3,3320 %
ICMS: float = 0.2250           # 22,50 %

PIS_COFINS: float = PIS + COFINS                        # ≈ 4,0536 %
FATOR_TRIBUTADO: float = (1 - ICMS) * (1 - PIS_COFINS)  # ≈ 0,7436
FATOR_ISENTO_ICMS: float = 1 - PIS_COFINS               # ≈ 0,9595
FATOR_COMERCIALIZADORA: float = 1 - ICMS                 # ≈ 0,775  (TE: só ICMS, sem PIS/COFINS)

# ─── Tarifa AZUL ────────────────────────────────────────────────────────────────
AZUL_DEMANDA_HP: float = 88.82        # R$ / kW   (Ponta) — cheia, sem desconto
# R$ / kW   (Fora Ponta) — cheia, sem desconto
AZUL_DEMANDA_FP: float = 32.50
AZUL_TUSD_HP: float = 140.21          # R$ / MWh  (Ponta)
AZUL_TUSD_FP: float = 140.21          # R$ / MWh  (Fora Ponta)

# ─── Tarifa VERDE ───────────────────────────────────────────────────────────────
# R$ / kW   (somente Fora Ponta) — cheia, sem desconto
VERDE_DEMANDA_UNICA: float = 32.50
VERDE_TUSD_HP: float = 2296.63        # R$ / MWh  (Ponta)
VERDE_TUSD_FP: float = 140.21         # R$ / MWh  (Fora Ponta)

# ─── Desconto de Fonte Incentivada ──────────────────────────────────────────────
# 50 % (I-5: eólica, solar, biomassa, PCH ≤ 30 MW)
DESCONTO_FONTE_INCENTIVADA: float = 0.50

# ─── Comercializadora (TE) ──────────────────────────────────────────────────────
# R$ / kWh  (base sem imposto; gross-up tributado é aplicado)
TE_COMERCIALIZADORA: float = 0.308
