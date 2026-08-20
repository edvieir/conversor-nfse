---
name: importar-leads
description: Move os leads extraídos da Receita Federal para o CRM, sem duplicar e sem quebrar as fórmulas.
allowed-tools: Bash, Read, Write
---

Importe os leads novos para o CRM.

1. Faça backup: copie `crm/CRM_Prospeccao_Rodrigues.xlsx` para
   `saidas/backup_crm_AAAA-MM-DD.xlsx`.
2. Leia `saidas/leads_fortaleza.xlsx` (ou o arquivo indicado em `$ARGUMENTS`).
3. Leia a aba `Pipeline` do CRM e colete os CNPJs já presentes.
4. Escreva as linhas novas com openpyxl, a partir da primeira linha vazia,
   **apenas nestas colunas**:
   - C Razao_Social · D Nome_Fantasia · E CNPJ · F Segmento
   - G Bairro · H Telefone · J Porte
   - A ID (sequencial) · B Data_Entrada (hoje) · K Cunha · L "Nao iniciado"
5. **Nunca escreva nas colunas I, N, O, P, Q, R, S** — são fórmulas.
   Se precisar estender as fórmulas para linhas novas, copie a fórmula da
   linha imediatamente acima, ajustando o número da linha.
6. Priorize quem tem celular: importe primeiro as linhas com WhatsApp.
7. Não importe duplicados. Reporte quantos foram ignorados por já existirem.
8. Ao final, reporte: importados, ignorados, total no pipeline.
