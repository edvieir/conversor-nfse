// automacao.js — função injetada no "main world" da aba do portal.
//
// Precisa ser autocontida: chrome.scripting.executeScript serializa a função,
// então ela não pode fechar sobre nada deste módulo.
//
// Ela PREENCHE e, se pedido, VALIDA. Nunca clica em Salvar: gravar é ato do
// usuário, depois de conferir o diálogo.

export function preencherNota(nota, opcoes) {
  return (async () => {
    const log = [];
    const diz = (m) => { log.push(m); return m; };

    const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

    async function ajaxParado(limite = 15000) {
      const ate = Date.now() + limite;
      while (Date.now() < ate) {
        if (window.PrimeFaces?.ajax?.Queue?.isEmpty?.()) return true;
        await esperar(120);
      }
      return false;
    }

    // Os ids do PrimeFaces vêm prefixados pelo formulário; casamos pelo sufixo.
    const W = (sufixo) => Object.values(window.PrimeFaces?.widgets || {})
      .find((w) => w && w.id && w.id.endsWith(sufixo));

    const campo = (id) => document.getElementById(id + '_input') || document.getElementById(id);

    function dispara(el, tipos) {
      for (const t of tipos) el.dispatchEvent(new Event(t, { bubbles: true }));
    }

    async function escrever(el, valor, extras = ['input', 'change']) {
      el.focus();
      el.value = valor;
      dispara(el, extras);
      el.blur();
      dispara(el, ['blur']);
      await ajaxParado();
    }

    // selectValue não persiste no servidor (regime some, CNAE dá erro de
    // processo). Abrir o painel e clicar no <li> é o que funciona.
    async function escolher(sufixo, rotulo) {
      const w = W(sufixo);
      if (!w) return diz(`select ${sufixo}: widget não encontrado`);
      w.show();
      await esperar(180);
      const itens = [...(w.panel ? w.panel[0].querySelectorAll('li') : [])];
      const alvo = itens.find((li) => (li.dataset.label || li.textContent || '').trim() === rotulo)
        || itens.find((li) => (li.dataset.label || li.textContent || '').trim()
          .toLowerCase().includes(String(rotulo).toLowerCase()));
      if (!alvo) {
        w.hide?.();
        return diz(`select ${sufixo}: opção "${rotulo}" não existe`);
      }
      window.jQuery(alvo).trigger('click');
      await ajaxParado();
      return diz(`${sufixo}: ${rotulo}`);
    }

    async function dinheiro(sufixo, valor) {
      const w = W(sufixo);
      const el = w ? campo(w.id) : document.querySelector(`[id$="${sufixo}"]`);
      if (!el) return diz(`campo ${sufixo} não encontrado`);
      const txt = Number(valor).toFixed(2).replace('.', ',');
      el.focus();
      el.value = txt;
      dispara(el, ['keyup', 'input', 'change']);
      el.blur();
      dispara(el, ['blur']);
      await ajaxParado();
      return diz(`${sufixo}: ${txt}`);
    }

    try {
      if (!window.PrimeFaces) {
        return { ok: false, log, erro: 'Esta aba não parece ser o portal (PrimeFaces ausente).' };
      }

      // 1. Documento do prestador — dispara a busca do cadastro
      const doc = document.querySelector('input[placeholder="Somente números."]');
      if (!doc) return { ok: false, log, erro: 'Campo do documento não encontrado. Abra Incluir antes.' };
      await escrever(doc, nota.prestadorCnpj);
      await esperar(1500);
      await ajaxParado();
      diz(`documento: ${nota.prestadorCnpj}`);

      const dialogoPrestador = [...document.querySelectorAll('.ui-dialog')]
        .find((d) => d.offsetParent && /Adicionar Prestador/i.test(d.textContent));
      if (dialogoPrestador) {
        return {
          ok: false, precisaCadastro: true, log,
          erro: `Prestador ${nota.prestadorCnpj} não cadastrado. O portal abriu `
            + `"Adicionar Prestador" — preencha com os dados abaixo e repita.`,
          dadosCadastro: {
            uf: nota.endereco.uf, municipio: nota.xLocPrestacao, nome: nota.prestadorNome,
            im: nota.prestadorIM, cep: nota.endereco.cep, bairro: nota.endereco.bairro,
            logradouro: nota.endereco.logradouro, numero: nota.endereco.numero,
            complemento: nota.endereco.complemento, email: nota.prestadorEmail,
          },
        };
      }

      // 2. Número da nota
      const num = document.querySelector('[id$="inp-num-nota"]') || document.querySelector('[id$="inp-numero"]');
      if (num) await escrever(num, nota.nNFSe);

      // 3. Emissão (datepicker somente leitura: só pela API do widget)
      const wData = W('inp-data') || W(':data');
      if (wData && nota.dhEmi) {
        const [a, m, d] = nota.dhEmi.split('-').map(Number);
        wData.setDate(new Date(a, m - 1, d));
        wData.cfg?.behaviors?.dateSelect?.call(wData, {});
        await ajaxParado();
        diz(`emissão: ${d}/${m}/${a}`);
      }

      // 4. Competência (mês/ano do período, não o da nota)
      const comp = document.querySelector('[id$="inp-data-competencia:inp-compe"]')
        || document.querySelector('[id$="inp-compe"]');
      if (comp && opcoes?.competencia) await escrever(comp, opcoes.competencia);

      // 5. Regime e flag do Simples
      await escolher('inp-regime:input', nota.decisao.regime);
      const flag = W('card-servico:j_idt233');
      if (flag && typeof flag.toggle === 'function') {
        const marcado = !!flag.input?.[0]?.checked;
        if (marcado !== !!nota.decisao.simples) {
          flag.toggle();
          await ajaxParado();
        }
        diz(`optante Simples: ${nota.decisao.simples ? 'sim' : 'não'}`);
      }

      // 6. Valores. A alíquota só é digitada quando a regra manda; nos demais
      // regimes quem calcula é o portal.
      await dinheiro('inp-vl-nota', nota.vServ);
      if (nota.decisao.lancarDesconto && nota.vDescIncond) {
        await dinheiro('inp-vl-desc-inco', nota.vDescIncond);
      }
      if (nota.decisao.aliquota !== null && nota.decisao.aliquota !== undefined) {
        await dinheiro('inp-ali', nota.decisao.aliquota);
      }

      if (!opcoes?.validar) {
        return { ok: true, log, aviso: 'Preenchido. Confira o CNAE e clique em Validar.' };
      }

      // 7. Validar e ler o diálogo — sem gravar
      const btn = [...document.querySelectorAll('button, a')]
        .find((b) => /validar/i.test(b.textContent || ''));
      if (!btn) return { ok: true, log, aviso: 'Preenchido, mas o botão Validar não foi achado.' };
      btn.click();
      await esperar(900);
      await ajaxParado();

      const dlg = [...document.querySelectorAll('.ui-dialog')].find((d) => d.offsetParent);
      const textoDlg = dlg ? dlg.innerText.replace(/\s+/g, ' ') : '';
      const esperado = nota.vServ.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
      const bateValor = textoDlg.includes(esperado);
      const bateIss = nota.decisao.aliquota === null
        || textoDlg.includes(nota.vISSQN.toLocaleString('pt-BR', { minimumFractionDigits: 2 }));

      return {
        ok: true, log, validado: true, bateValor, bateIss,
        dialogo: textoDlg.slice(0, 600),
        aviso: bateValor && bateIss
          ? 'Confere com o XML. Clique em Salvar no portal se estiver de acordo.'
          : 'DIVERGÊNCIA entre o diálogo e o XML — confira antes de salvar.',
      };
    } catch (e) {
      return { ok: false, log, erro: `${e.name}: ${e.message}` };
    }
  })();
}
