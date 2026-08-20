---
name: roteiro
description: Gera o roteiro de mensagens de prospecção do dia a partir do CRM, já personalizado e na ordem de prioridade.
allowed-tools: Bash, Read
---

Gere o roteiro de prospecção de hoje.

1. Rode `python scripts/03_gerar_roteiro_diario.py`.
   Se `$ARGUMENTS` trouxer um número, passe como `--novos N`.
2. Leia `saidas/roteiro_do_dia.txt`.
3. Me apresente no chat, nesta ordem exata:
   - **Quem respondeu** — nome, status atual e o que fazer. Prioridade máxima.
   - **Atrasados** — quantos e quais. Precisam ser zerados hoje.
   - **Follow-ups de hoje** — com a mensagem já pronta para copiar.
   - **Novos D0** — com a mensagem já pronta e o link wa.me.
4. Feche com uma linha só: quantas mensagens no total e o tempo estimado
   (conte ~4 minutos por contato).

Não reescreva as mensagens por conta própria. Elas foram calibradas. Se
achar que alguma não serve para o caso, diga qual e por quê, e proponha a
alteração — mas não altere sozinho.

Se a fila de novos contatos estiver vazia, avise para rodar `/base-mensal`.
