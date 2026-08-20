# Motor de Prospecção — Rodrigues Contabilidade

Projeto para rodar no **Claude Code desktop**. Você conversa, o Claude executa.

---

## Instalação (uma vez, ~15 minutos)

### 1. Python

Baixe em [python.org/downloads](https://www.python.org/downloads/).
**No Windows, marque "Add Python to PATH" na primeira tela do instalador.**
Sem isso, nada funciona.

### 2. Coloque a pasta em um lugar definitivo

Exemplo: `C:\Users\SeuNome\Documentos\rodrigues-prospeccao`
Não deixe em Downloads — você vai voltar aqui todo dia.

### 3. Abra no Claude Code

No app do Claude, vá na aba **Code** e abra esta pasta como projeto.

### 4. Primeira mensagem

Digite exatamente isto:

```
Instale as dependências do requirements.txt e confirme que os 4 scripts
da pasta scripts/ rodam sem erro de import.
```

Aprove os comandos que ele pedir. Se algo falhar, cole o erro no chat.

### 5. Ajuste seu nome

```
Troque SEU_NOME no script 03 pelo meu primeiro nome: [seu nome]
```

---

## Uso

### Todo dia útil, de manhã

```
/roteiro
```

Claude gera e apresenta, em ordem de prioridade: quem respondeu (responda
primeiro), follow-ups atrasados, follow-ups do dia e 10 novos primeiros
contatos — cada um com a mensagem pronta e o link do WhatsApp.

Você copia, cola, envia. Depois:

```
Marca como enviado quem eu disparei hoje
```

### Uma vez por mês

```
/base-mensal
```

Baixa ~7 GB da Receita Federal, cruza tudo e devolve os leads de Fortaleza
já filtrados por Simples Nacional, ME/EPP, ativos e no CNAE certo.
Demora até 90 minutos rodando sozinho. Depois:

```
/importar-leads
```

### Toda sexta-feira

```
/painel
```

Claude lê o funil, calcula as taxas e aponta **um** gargalo com a ação da
semana. Não é relatório: é diagnóstico.

### Quando um prospect mandar os PGDAS

```
/diagnostico Auto Peças Silva
```

Claude analisa e monta o relatório de 1 página em `saidas/`.
**Confira o cálculo antes de enviar ao cliente — a responsabilidade
técnica é sua.**

---

## Conversa livre

Os comandos são atalhos, não limites. Vale pedir direto:

- "Reescreve o D0 — ninguém está respondendo. Aqui está o que recebi: ..."
- "Quantos leads de autopeças ainda não foram contatados?"
- "Monta a proposta comercial pra esse prospect, faixa C"
- "O prospect disse que o contador dele falou que não se aplica. E agora?"
- "Adiciona clínicas odontológicas nos CNAEs e roda de novo"

O arquivo `CLAUDE.md` carrega todo o contexto do escritório em cada sessão:
precificação, cunhas, base legal, regras de objeção e as restrições
(nada de vídeo, exposição pessoal, evento ou anúncio pago).

---

## Estrutura

```
CLAUDE.md                  contexto do negócio — leia antes de editar
requirements.txt           dependências Python
.claude/skills/            os 5 comandos
scripts/                   os 4 scripts de automação
crm/                       o CRM em Excel (trabalho) + CRM_MODELO.xlsx
                           (modelo em branco, versionado)
dados_rfb/                 base bruta da Receita (fica local, ~25 GB)
saidas/                    leads, roteiros e diagnósticos gerados
```

---

## Cuidados

- **O CRM tem fórmula.** Não edite as colunas I, N, O, P, Q, R, S à mão.
  O Claude foi instruído a não tocar nelas.
- **`dados_rfb/` ocupa ~25 GB.** Não apague no fim do mês: é reaproveitada.
- **O `.gitignore` bloqueia o CRM de trabalho e os CSVs** de propósito: são
  CNPJ e telefone de terceiros. Só o `crm/CRM_MODELO.xlsx` (em branco) vai
  para o repositório. Em uma máquina nova, recrie o arquivo de trabalho com:

  ```
  copy crm\CRM_MODELO.xlsx crm\CRM_Prospeccao_Rodrigues.xlsx
  ```

  (no Mac/Linux, `cp` no lugar de `copy`). Ou peça ao Claude: "prepara o CRM
  de trabalho a partir do modelo".
- **Nenhum cálculo tributário vai para o cliente sem sua conferência.**
