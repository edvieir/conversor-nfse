---
name: painel
description: Lê o funil do CRM, calcula as taxas de conversão e aponta onde está o gargalo real da semana.
allowed-tools: Bash, Read
---

Faça a leitura semanal do funil.

1. Leia a aba `Pipeline` do CRM e calcule em Python (não confie em valor
   em cache do Excel):
   - Leads na base, não iniciados, contatados, responderam
   - Diagnósticos aceitos, relatórios entregues, fechados, perdidos
   - Taxa de resposta, contato→diagnóstico, diagnóstico→fechamento, total
   - Economia mensal e retroativo identificados, honorário fechado
2. Compare com as referências e **aponte um único gargalo prioritário**:

| Sintoma | Diagnóstico |
|---|---|
| Resposta < 20% | Script ou lista errados |
| Contato→diagnóstico < 7% | A cunha não é relevante para esse público |
| Diagnóstico alto, fechamento < 30% | Preço ou objeção mal tratada |
| Contatados < 200/mês | Disciplina, não estratégia |
| Atrasados > 10 | A cadência está furando |

3. Não liste todos os problemas. Nomeie **o** gargalo e diga a ação
   concreta da semana para atacá-lo.
4. Se houver linhas com Alerta ATRASADO, diga quantas e que isso vem antes
   de qualquer prospecção nova.
