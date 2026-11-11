// lib/nfse.js — leitura do XML da NFS-e Nacional e classificação de cada nota
// segundo as regras combinadas para a escrituração de tomados em Itaitinga.
//
// Esta é a parte que decide o que digitar no portal. A automação do formulário
// só executa o que sai daqui.

export const MUNICIPIO_ITAITINGA = '2306256';

// Item da lista de serviços -> código CNAE da tabela do portal.
// Levantado nota a nota; para item novo, busca-se no diálogo do portal.
export const CNAE_POR_ITEM = {
  '17.02': { cnae: '821999901', desc: 'apoio administrativo' },
  '17.01': { cnae: '702040000', desc: 'consultoria em gestão' },
  '08.02': { cnae: '859960400', desc: 'treinamento profissional/gerencial' },
  '01.07': { cnae: '620910000', desc: 'suporte técnico TI' },
  '01.06': { cnae: '620910001', desc: 'consultoria em informática' },
  '04.22': { cnae: '655020000', desc: 'planos de saúde' },
  '17.19': { cnae: '692060100', desc: 'contabilidade' },
  '14.01': { cnae: '331470200', desc: 'manutenção bombas de combustível' },
  '11.04': { cnae: '521170200', desc: 'guarda/custódia' },
  '10.05': { cnae: '829979904', desc: 'administração de convênio' },
  '17.12': { cnae: '829979916', desc: 'administração em geral' },
  '07.02': { cnae: '439919900', desc: 'serviços especializados construção' },
  '99.01': { cnae: '773310001', desc: 'locação máquinas de escritório' },
};

const NS = 'http://www.sped.fazenda.gov.br/nfse';

function texto(no, tag) {
  if (!no) return '';
  const achados = no.getElementsByTagNameNS(NS, tag);
  const el = achados.length ? achados[0] : no.getElementsByTagName(tag)[0];
  return el && el.textContent ? el.textContent.trim() : '';
}

function primeiro(doc, tag) {
  const achados = doc.getElementsByTagNameNS(NS, tag);
  return achados.length ? achados[0] : doc.getElementsByTagName(tag)[0] || null;
}

function numero(s) {
  const v = parseFloat((s || '').replace(',', '.'));
  return Number.isFinite(v) ? v : 0;
}

/** "170201" -> "17.02" (o item são os dois primeiros pares). */
export function itemDoTribNac(cTribNac) {
  const d = (cTribNac || '').replace(/\D/g, '');
  return d.length >= 4 ? `${d.slice(0, 2)}.${d.slice(2, 4)}` : '';
}

/**
 * Decide regime, flag do Simples e alíquota a digitar.
 * Regras combinadas — ver SKILL.md, seção 2.
 */
export function classificar({ opSimpNac, regEspTrib, pAliqAplic, item }) {
  if (regEspTrib === '2') {
    return {
      regime: 'Cooperativa',
      simples: false,
      aliquota: null,            // o portal calcula
      lancarDesconto: true,
      observacao: 'Cooperativa: lançar desconto incondicional e aceitar o cálculo do portal.',
    };
  }
  if (opSimpNac === '2') {
    return {
      regime: 'Microempresario Individual (MEI)',
      simples: true,
      aliquota: 0,
      lancarDesconto: false,
      observacao: 'MEI: alíquota 0, ISS deve ficar 0.',
    };
  }
  if (opSimpNac === '3') {
    return {
      regime: 'Microempresa (ME EPP)',
      simples: true,
      aliquota: numero(pAliqAplic),
      lancarDesconto: false,
      observacao: 'Simples: marcar Optante (libera a alíquota) e digitar a da nota.',
    };
  }
  return {
    regime: 'Demais',
    simples: false,
    aliquota: null,              // o portal calcula e costuma divergir da nota
    lancarDesconto: false,
    observacao: 'Não optante: aceitar alíquota/natureza calculada pelo portal.',
  };
}

/** Avisos que exigem atenção humana antes de gravar. */
function avisos(n, competenciaZip) {
  const lista = [];
  if (n.vServ <= 0.01) lista.push('Nota zerada ou de valor simbólico — lançar mesmo assim.');
  if (n.tribISSQN === '4' || n.item === '99.01') {
    lista.push('NÃO INCIDÊNCIA: o portal trava a alíquota mas calcula 3% na validação. Não gravar sem confirmar.');
  }
  if (n.opSimpNac === '2') lista.push('Prestador MEI.');
  if (n.regEspTrib === '2') lista.push('Prestador cooperativa.');
  if (n.cLocPrestacao === MUNICIPIO_ITAITINGA) {
    lista.push('Prestador do próprio município — confirmar se cabe nesta tela.');
  }
  if (competenciaZip && n.dCompet && !n.dCompet.startsWith(competenciaZip.ano)) {
    lista.push('Competência do XML diferente da do período.');
  }
  if (n.dhEmi && n.dCompet && n.dhEmi.slice(0, 7) !== n.dCompet.slice(0, 7)) {
    lista.push('Emissão fora do mês da competência — usar a competência do período.');
  }
  if (!CNAE_POR_ITEM[n.item]) {
    lista.push(`Item ${n.item || '?'} sem CNAE mapeado — buscar no diálogo do portal.`);
  }
  return lista;
}

/** Lê um XML de NFS-e Nacional e devolve a nota já classificada. */
export function lerNota(xmlTexto, competenciaZip) {
  const doc = new DOMParser().parseFromString(xmlTexto, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('XML inválido');

  const raiz = doc.documentElement;
  if (raiz.localName !== 'NFSe') return null;   // eventos de cancelamento etc.

  const emit = primeiro(doc, 'emit');
  const ender = primeiro(doc, 'enderNac') || primeiro(doc, 'enderExt');
  const cServ = primeiro(doc, 'cServ');
  const regTrib = primeiro(doc, 'regTrib');
  const tribMun = primeiro(doc, 'tribMun');
  const infDPS = primeiro(doc, 'infDPS');
  const valoresNfse = primeiro(doc, 'valores');

  const cTribNac = texto(cServ, 'cTribNac');
  const n = {
    arquivo: '',
    nNFSe: texto(doc, 'nNFSe'),
    dhEmi: texto(infDPS, 'dhEmi').slice(0, 10),
    dCompet: texto(infDPS, 'dCompet'),
    prestadorCnpj: texto(emit, 'CNPJ') || texto(emit, 'CPF'),
    prestadorNome: texto(emit, 'xNome'),
    prestadorIM: texto(emit, 'IM'),
    prestadorEmail: texto(emit, 'email'),
    endereco: {
      logradouro: texto(ender, 'xLgr'),
      numero: texto(ender, 'nro'),
      complemento: texto(ender, 'xCpl'),
      bairro: texto(ender, 'xBairro'),
      cMun: texto(ender, 'cMun'),
      uf: texto(ender, 'UF'),
      cep: texto(ender, 'CEP'),
    },
    cLocPrestacao: texto(primeiro(doc, 'locPrest'), 'cLocPrestacao'),
    xLocPrestacao: texto(doc, 'xLocPrestacao'),
    xLocIncid: texto(doc, 'xLocIncid'),
    cTribNac,
    item: itemDoTribNac(cTribNac),
    descServico: texto(cServ, 'xDescServ'),
    vServ: numero(texto(primeiro(doc, 'vServPrest'), 'vServ')),
    vDescIncond: numero(texto(doc, 'vDescIncond')),
    vBC: numero(texto(valoresNfse, 'vBC')),
    pAliqAplic: texto(valoresNfse, 'pAliqAplic'),
    vISSQN: numero(texto(valoresNfse, 'vISSQN')),
    tpRetISSQN: texto(tribMun, 'tpRetISSQN'),
    tribISSQN: texto(tribMun, 'tribISSQN'),
    opSimpNac: texto(regTrib, 'opSimpNac'),
    regEspTrib: texto(regTrib, 'regEspTrib'),
  };

  n.decisao = classificar(n);
  n.cnae = CNAE_POR_ITEM[n.item] || null;
  n.avisos = avisos(n, competenciaZip);
  n.retido = n.tpRetISSQN && n.tpRetISSQN !== '1';
  return n;
}

/** Lê vários XMLs e devolve notas + resumo por prestador. */
export function lerLote(arquivos, competenciaZip) {
  const notas = [];
  const erros = [];
  for (const { nome, texto: xml } of arquivos) {
    try {
      const n = lerNota(xml, competenciaZip);
      if (n) {
        n.arquivo = nome;
        notas.push(n);
      }
    } catch (e) {
      erros.push(`${nome}: ${e.message}`);
    }
  }
  notas.sort((a, b) => (a.dhEmi || '').localeCompare(b.dhEmi || ''));

  const porPrestador = new Map();
  for (const n of notas) {
    const k = n.prestadorCnpj;
    const atual = porPrestador.get(k) || { nome: n.prestadorNome, qtd: 0, total: 0, iss: 0 };
    atual.qtd += 1;
    atual.total += n.vServ;
    atual.iss += n.vISSQN;
    porPrestador.set(k, atual);
  }

  return {
    notas,
    erros,
    resumo: {
      qtd: notas.length,
      total: notas.reduce((s, n) => s + n.vServ, 0),
      iss: notas.reduce((s, n) => s + n.vISSQN, 0),
      retidos: notas.filter((n) => n.retido).length,
      comAviso: notas.filter((n) => n.avisos.length).length,
      porPrestador: [...porPrestador.entries()].map(([cnpj, v]) => ({ cnpj, ...v })),
    },
  };
}
