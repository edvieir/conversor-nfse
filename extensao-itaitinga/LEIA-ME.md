# Escrituração ISS Itaitinga — extensão do Chrome

Lê o ZIP das NFS-e tomadas, classifica cada nota pelo regime do prestador e
preenche a tela **Escrituração Tomador > NFSe de Outros Municípios > Incluir**
do portal de Itaitinga (SS Informática).

Existe porque isso não roda no Fiscal Hub: o portal exige a sessão já
autenticada no navegador, e o Hub roda no servidor, sem acesso a ela.

## Instalar

1. Chrome → `chrome://extensions`
2. Ligar **Modo do desenvolvedor** (canto superior direito)
3. **Carregar sem compactação** → escolher esta pasta
4. Fixar o ícone na barra

## Usar

1. Abrir o portal e **fazer login normalmente** (a extensão nunca pede nem
   digita senha).
2. Navegar até `Escrituração Tomador > NFSe de Outros Municípios > Incluir`.
3. Clicar no ícone da extensão — abre o painel lateral, que fica aberto
   enquanto se trabalha na página.
4. Selecionar o ZIP da competência (ou os XMLs soltos) e conferir o mês.
5. Conferir o resumo e os avisos.
6. Nota a nota: **Preencher no portal** → revisar a tela → **Salvar no
   próprio portal**.

## O que ela faz e o que não faz

Ela preenche os campos, escolhe o regime, marca o Simples quando cabe, lança
valor e desconto, e opcionalmente clica em **Validar** e compara o diálogo com
o XML.

**Ela nunca clica em Salvar.** Gravar é ato de quem opera, depois de conferir —
é o fluxo que a própria skill define. Também nunca clica em **Encerrar**.

## Regras aplicadas

| Situação no XML | Regime no portal | Simples | Alíquota |
|---|---|---|---|
| `opSimpNac=3` (ME/EPP) | Microempresa (ME EPP) | marcado | a da nota |
| `opSimpNac=2` (MEI) | Microempresario Individual (MEI) | marcado | 0 |
| `opSimpNac=1` (não optante) | Demais | — | calculada pelo portal |
| `regEspTrib=2` (cooperativa) | Cooperativa | — | portal + desconto incondicional |

Avisos que aparecem no painel: nota zerada, não incidência (item 99.01),
prestador MEI ou cooperativa, prestador do próprio município (IBGE 2306256),
emissão fora do mês da competência e item sem CNAE mapeado.

**Não incidência não é preenchida às cegas**: o portal trava a alíquota mas
calcula 3% na validação, então a nota entra marcada para decisão humana.

## Estrutura

- `lib/nfse.js` — leitura do XML e as regras de classificação. É o miolo; foi
  verificado contra XMLs reais (21 checagens).
- `lib/zip.js` — leitor de ZIP com `DecompressionStream`, sem biblioteca externa.
- `automacao.js` — função injetada na aba do portal (PrimeFaces).
- `painel.html` / `painel.js` / `estilo.css` — painel lateral.

## Limites conhecidos

A automação depende de ids internos do PrimeFaces (`inp-regime:input`,
`card-servico:j_idt233`, `inp-vl-nota`…). **Uma atualização do portal pode
quebrá-la** — nesse caso o painel mostra "widget não encontrado" e o
preenchimento manual continua possível.

O CNAE ainda não é selecionado automaticamente: o painel mostra o código certo
para o item e a busca no diálogo fica por conta de quem opera. Os 13 itens
mapeados estão em `CNAE_POR_ITEM`, em `lib/nfse.js`.

Cadastro de prestador novo também não é automático: quando o portal abre
"Adicionar Prestador", o painel exibe os dados da nota prontos para copiar.
