---
name: base-mensal
description: Baixa a base pública de CNPJ da Receita Federal e extrai os leads qualificados de Fortaleza. Rodar uma vez por mês.
allowed-tools: Bash, Read, Edit, Write
---

Atualize a base de leads. Execute na ordem, sem pedir confirmação entre etapas:

1. Verifique se há ao menos 30 GB livres em disco. Se não houver, pare e avise.
2. Rode `python scripts/00_baixar_base.py`.
   - Demora de 30 a 90 minutos. Não interrompa por lentidão.
   - Se terminar com pendências, rode de novo até zerar (máximo 3 tentativas).
3. Rode `python scripts/01_extrator_receita_federal.py`.
4. Leia `saidas/leads_fortaleza.xlsx` e me reporte:
   - Total de leads e quantos têm celular (WhatsApp)
   - Quebra por segmento
   - Os 10 bairros com maior concentração
5. Se o total vier abaixo de 200, avise: a lista de CNAEs em
   `scripts/01_extrator_receita_federal.py` precisa ser ampliada. Sugira
   quais CNAEs acrescentar com base no que já veio.
6. Se o argumento `$ARGUMENTS` mencionar uma cunha ("fator r", "recém-abertas"),
   ajuste `CNAES_ALVO` ou `IDADE_MAX_MESES` no script antes de rodar a etapa 3.

Não apague a pasta `dados_rfb/` no fim — ela é reaproveitada no mês seguinte.
