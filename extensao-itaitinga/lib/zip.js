// lib/zip.js — leitor de ZIP sem dependência externa.
//
// Usa DecompressionStream('deflate-raw'), nativo do Chrome, em vez de embutir
// uma biblioteca. O ZIP das NFS-e só traz arquivos armazenados (método 0) ou
// deflate (método 8), que é o que tratamos aqui.

const ASSINATURA_FIM_CENTRAL = 0x06054b50;
const ASSINATURA_CENTRAL = 0x02014b50;

function acharFimDoDiretorio(visao) {
  // O registro final tem tamanho variável por causa do comentário; procura de trás pra frente.
  const limite = Math.max(0, visao.byteLength - 0xffff - 22);
  for (let i = visao.byteLength - 22; i >= limite; i--) {
    if (visao.getUint32(i, true) === ASSINATURA_FIM_CENTRAL) return i;
  }
  throw new Error('Arquivo não parece ser um ZIP válido.');
}

async function inflar(bytes) {
  const fluxo = new Blob([bytes]).stream()
    .pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(fluxo).arrayBuffer());
}

/**
 * Lê um ZIP e devolve [{nome, texto}] apenas dos arquivos que casam com `filtro`.
 * @param {ArrayBuffer} buffer
 * @param {RegExp} filtro
 */
export async function lerZip(buffer, filtro = /\.xml$/i) {
  const visao = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  const fim = acharFimDoDiretorio(visao);
  const qtd = visao.getUint16(fim + 10, true);
  let p = visao.getUint32(fim + 16, true);

  const saida = [];
  const decodificador = new TextDecoder('utf-8');

  for (let i = 0; i < qtd; i++) {
    if (visao.getUint32(p, true) !== ASSINATURA_CENTRAL) break;
    const metodo = visao.getUint16(p + 10, true);
    const tamComprimido = visao.getUint32(p + 20, true);
    const tamNome = visao.getUint16(p + 28, true);
    const tamExtra = visao.getUint16(p + 30, true);
    const tamComentario = visao.getUint16(p + 32, true);
    const deslocamento = visao.getUint32(p + 42, true);
    const nome = decodificador.decode(bytes.subarray(p + 46, p + 46 + tamNome));
    p += 46 + tamNome + tamExtra + tamComentario;

    if (!filtro.test(nome)) continue;

    // Cabeçalho local: os campos de nome/extra podem ter tamanhos diferentes
    // dos do diretório central, então releem-se aqui.
    const nomeLocal = visao.getUint16(deslocamento + 26, true);
    const extraLocal = visao.getUint16(deslocamento + 28, true);
    const inicio = deslocamento + 30 + nomeLocal + extraLocal;
    const bruto = bytes.subarray(inicio, inicio + tamComprimido);

    let conteudo;
    if (metodo === 0) conteudo = bruto;
    else if (metodo === 8) conteudo = await inflar(bruto);
    else continue;   // método não suportado: ignora em silêncio

    saida.push({ nome, texto: decodificador.decode(conteudo) });
  }
  return saida;
}
