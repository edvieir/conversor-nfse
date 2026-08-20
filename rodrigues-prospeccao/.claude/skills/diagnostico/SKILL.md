---
name: diagnostico
description: Analisa os PGDAS-D de um prospect e monta o Relatório de Diagnóstico Fiscal de 1 página.
allowed-tools: Bash, Read, Write
---

Monte o diagnóstico fiscal para: $ARGUMENTS

1. Peça (ou localize) os PGDAS-D dos últimos 3 meses e o relatório de
   vendas por produto ou os XMLs de venda.
2. Extraia por competência: receita bruta declarada, anexo, alíquota
   efetiva, parcelas de PIS e COFINS.
3. Classifique o mix por NCM e identifique os grupos monofásicos:
   - Lei 10.147/2000 — medicamentos, perfumaria, toucador, higiene pessoal
   - Lei 10.485/2002 — autopeças (Anexos I e II), pneus e câmaras de ar
   - Lei 13.097/2015 — bebidas frias
   - Lei 9.718/1998 — combustíveis
4. Calcule: recolhimento indevido mensal, projeção anual e retroativo
   recuperável (limite de 60 meses, CTN art. 168).
5. Gere `saidas/diagnostico_[EMPRESA].md` com a estrutura fixa de 1 página:
   situação atual → inconsistência com base legal → impacto financeiro em
   tabela → providências com prazo → observações.
6. Termine sempre com: *"Este diagnóstico é de propriedade da empresa
   analisada e pode ser utilizado por qualquer profissional de sua escolha,
   sem qualquer vínculo ou obrigação com a Rodrigues Contabilidade."*

**Regras que não se quebram:**
- Nenhum número sai de estimativa sua. Só de documento. Se faltar dado
  para um cálculo, diga qual falta e pare — não preencha com premissa.
- Se o mix não tiver produto monofásico, diga isso com todas as letras e
  sugira testar o Fator R. Diagnóstico honesto que dá zero também gera
  indicação; diagnóstico inflado destrói o escritório.
- Antes de enviar ao prospect, o cálculo precisa de conferência humana
  com CRC. Lembre disso uma vez, no final.
