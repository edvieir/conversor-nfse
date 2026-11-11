// painel.js — lê os arquivos, mostra as notas classificadas e dispara o
// preenchimento no portal, uma nota por vez.

import { lerZip } from './lib/zip.js';
import { lerLote } from './lib/nfse.js';
import { preencherNota } from './automacao.js';

const $ = (id) => document.getElementById(id);
let notas = [];

const dinheiro = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

function registrar(msg) {
  const agora = new Date().toLocaleTimeString('pt-BR');
  $('log').textContent = `[${agora}] ${msg}\n` + $('log').textContent;
}

$('competencia').value = new Date().toISOString().slice(0, 7);

$('arquivo').addEventListener('change', async (ev) => {
  const arquivos = [...ev.target.files];
  if (!arquivos.length) return;
  try {
    let entradas = [];
    for (const f of arquivos) {
      if (/\.zip$/i.test(f.name)) {
        entradas.push(...await lerZip(await f.arrayBuffer()));
      } else {
        entradas.push({ nome: f.name, texto: await f.text() });
      }
    }
    const comp = $('competencia').value;             // "2026-10"
    const resultado = lerLote(entradas, { ano: comp.slice(0, 4) });
    notas = resultado.notas;
    desenharResumo(resultado);
    desenharNotas();
    registrar(`${notas.length} nota(s) lida(s) de ${entradas.length} arquivo(s).`);
    for (const e of resultado.erros) registrar(`erro: ${e}`);
  } catch (e) {
    registrar(`Falha ao ler: ${e.message}`);
  }
});

function desenharResumo({ resumo }) {
  $('blocoResumo').hidden = false;
  const linhas = resumo.porPrestador
    .sort((a, b) => b.total - a.total)
    .map((p) => `<tr><td>${p.nome}</td><td class="n">${p.qtd}</td>`
      + `<td class="n">${dinheiro(p.total)}</td></tr>`).join('');
  $('resumo').innerHTML = `
    <div class="numeros">
      <span><b>${resumo.qtd}</b> notas</span>
      <span><b>${dinheiro(resumo.total)}</b></span>
      <span>ISS ${dinheiro(resumo.iss)}</span>
      ${resumo.retidos ? `<span class="alerta">${resumo.retidos} retido(s)</span>` : ''}
      ${resumo.comAviso ? `<span class="alerta">${resumo.comAviso} com aviso</span>` : ''}
    </div>
    <table class="prestadores"><tbody>${linhas}</tbody></table>`;
}

function desenharNotas() {
  $('blocoNotas').hidden = false;
  $('notas').innerHTML = notas.map((n, i) => `
    <article class="nota${n.avisos.length ? ' com-aviso' : ''}" data-i="${i}">
      <div class="cab">
        <b>#${n.nNFSe}</b> · ${n.prestadorNome}
        <span class="valor">${dinheiro(n.vServ)}</span>
      </div>
      <div class="meta">
        item ${n.item || '—'} · ${n.decisao.regime}
        ${n.decisao.aliquota !== null ? ` · alíq ${n.decisao.aliquota}%` : ' · alíq do portal'}
        ${n.cnae ? ` · CNAE ${n.cnae.cnae}` : ' · <b class="alerta">CNAE a buscar</b>'}
      </div>
      ${n.avisos.map((a) => `<div class="aviso-item">${a}</div>`).join('')}
      <button class="preencher" data-i="${i}">Preencher no portal</button>
      <div class="status" id="st${i}"></div>
    </article>`).join('');

  for (const b of document.querySelectorAll('button.preencher')) {
    b.addEventListener('click', () => executar(Number(b.dataset.i)));
  }
}

async function executar(i) {
  const nota = notas[i];
  const alvo = $('st' + i);
  alvo.textContent = 'preenchendo…';
  const [aba] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!aba) { alvo.textContent = 'nenhuma aba ativa'; return; }

  const comp = $('competencia').value;
  const competencia = comp ? `${comp.slice(5, 7)}/${comp.slice(0, 4)}` : '';

  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: aba.id },
      world: 'MAIN',
      func: preencherNota,
      args: [nota, { competencia, validar: $('validar').checked }],
    });
    const r = res.result || {};
    (r.log || []).forEach(registrar);

    if (r.precisaCadastro) {
      alvo.className = 'status erro';
      alvo.textContent = r.erro + ' Dados: ' + JSON.stringify(r.dadosCadastro);
    } else if (!r.ok) {
      alvo.className = 'status erro';
      alvo.textContent = r.erro || 'falhou';
    } else {
      alvo.className = 'status ' + (r.bateValor === false || r.bateIss === false ? 'erro' : 'ok');
      alvo.textContent = r.aviso || 'preenchido';
    }
    registrar(`#${nota.nNFSe}: ${alvo.textContent}`);
  } catch (e) {
    alvo.className = 'status erro';
    alvo.textContent = e.message;
    registrar(`#${nota.nNFSe}: ${e.message}`);
  }
}
