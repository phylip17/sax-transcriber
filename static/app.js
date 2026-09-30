const formulario = document.getElementById("formulario");
const campoOrigem = document.getElementById("origem");
const botaoEnviar = document.getElementById("botaoEnviar");

const formularioArquivo = document.getElementById("formularioArquivo");
const campoArquivo = document.getElementById("arquivoAudio");
const botaoEnviarArquivo = document.getElementById("botaoEnviarArquivo");
const dicaArquivo = document.getElementById("dicaArquivo");

const abaLink = document.getElementById("abaLink");
const abaArquivo = document.getElementById("abaArquivo");

const console_ = document.getElementById("console");
const linhasConsole = document.getElementById("linhasConsole");

const secaoResultado = document.getElementById("resultado");
const pauta = document.getElementById("pauta");
const botaoCopiar = document.getElementById("botaoCopiar");
const botaoBaixar = document.getElementById("botaoBaixar");
const botaoPdf = document.getElementById("botaoPdf");

const secaoLetra = document.getElementById("secaoLetra");
const campoLetra = document.getElementById("campoLetra");
const linhasLetra = document.getElementById("linhasLetra");
const botaoPdfLetra = document.getElementById("botaoPdfLetra");

const nomeParaSalvar = document.getElementById("nomeParaSalvar");
const botaoSalvarBiblioteca = document.getElementById("botaoSalvarBiblioteca");
const buscaBiblioteca = document.getElementById("buscaBiblioteca");
const listaBiblioteca = document.getElementById("listaBiblioteca");

const tonalidadeEstimada = document.getElementById("tonalidadeEstimada");
const pautaVisual = document.getElementById("pautaVisual");
const painelDedilhado = document.getElementById("painelDedilhado");
const dedilhadoNotaNome = document.getElementById("dedilhadoNotaNome");
const botaoTocarNota = document.getElementById("botaoTocarNota");

const botaoPraticar = document.getElementById("botaoPraticar");
const velocidadePratica = document.getElementById("velocidadePratica");
const botaoMetronomo = document.getElementById("botaoMetronomo");
const bpmMetronomo = document.getElementById("bpmMetronomo");

const caixaErro = document.getElementById("erro");

let notasAtuais = [];
let frasesAtuais = [];
let contagensLetra = [];
let praticadasLetra = [];
let confiancasAtuais = [];
let foraDoAlcanceAtuais = [];
let notaSelecionada = null;

const CHAVE_BIBLIOTECA = "saxAltoBiblioteca";
const LIMIAR_CONFIANCA_BAIXA = 0.65;

// ---- Audio: sintetizar e tocar uma nota ----
let contextoAudio = null;

function obterContextoAudio() {
  if (!contextoAudio) {
    const AudioContextClasse = window.AudioContext || window.webkitAudioContext;
    contextoAudio = new AudioContextClasse();
  }
  if (contextoAudio.state === "suspended") {
    contextoAudio.resume();
  }
  return contextoAudio;
}

function notaParaMidi(nome) {
  const m = nome.match(/^([A-Ga-g])(#?)(-?\d+)$/);
  if (!m) return null;
  const semitons = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const base = semitons[m[1].toUpperCase()];
  const acidente = m[2] === "#" ? 1 : 0;
  const oitava = parseInt(m[3], 10);
  return (oitava + 1) * 12 + base + acidente;
}

function midiParaFrequencia(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function tocarNota(nome, duracaoS = 0.6) {
  const midi = notaParaMidi(nome);
  if (midi === null) return;
  const freq = midiParaFrequencia(midi);
  const ctx = obterContextoAudio();

  const osc = ctx.createOscillator();
  const ganho = ctx.createGain();
  osc.type = "triangle";
  osc.frequency.value = freq;

  const agora = ctx.currentTime;
  ganho.gain.setValueAtTime(0, agora);
  ganho.gain.linearRampToValueAtTime(0.25, agora + 0.02);
  ganho.gain.exponentialRampToValueAtTime(0.001, agora + duracaoS);

  osc.connect(ganho);
  ganho.connect(ctx.destination);
  osc.start(agora);
  osc.stop(agora + duracaoS + 0.05);
}

function tocarClickMetronomo() {
  const ctx = obterContextoAudio();
  const osc = ctx.createOscillator();
  const ganho = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = 1000;

  const agora = ctx.currentTime;
  ganho.gain.setValueAtTime(0.15, agora);
  ganho.gain.exponentialRampToValueAtTime(0.001, agora + 0.05);

  osc.connect(ganho);
  ganho.connect(ctx.destination);
  osc.start(agora);
  osc.stop(agora + 0.06);
}

abaLink.addEventListener("click", () => {
  abaLink.classList.add("aba--ativa");
  abaArquivo.classList.remove("aba--ativa");
  abaLink.setAttribute("aria-selected", "true");
  abaArquivo.setAttribute("aria-selected", "false");
  formulario.hidden = false;
  formularioArquivo.hidden = true;
  dicaArquivo.hidden = true;
});

abaArquivo.addEventListener("click", () => {
  abaArquivo.classList.add("aba--ativa");
  abaLink.classList.remove("aba--ativa");
  abaArquivo.setAttribute("aria-selected", "true");
  abaLink.setAttribute("aria-selected", "false");
  formularioArquivo.hidden = false;
  formulario.hidden = true;
  dicaArquivo.hidden = false;
});

function adicionarLinhaConsole(texto) {
  const linha = document.createElement("div");
  linha.className = "console__linha";
  linha.textContent = texto;
  linhasConsole.appendChild(linha);
  console_.scrollTop = console_.scrollHeight;
}

function limparEstado() {
  linhasConsole.innerHTML = "";
  pauta.innerHTML = "";
  notasAtuais = [];
  frasesAtuais = [];
  contagensLetra = [];
  linhasLetra.innerHTML = "";
  caixaErro.hidden = true;
  secaoResultado.hidden = true;
  secaoLetra.hidden = true;
  console_.hidden = false;
}

function mostrarErro(mensagem) {
  caixaErro.textContent = mensagem;
  caixaErro.hidden = false;
}

function mostrarResultado(notas, frases, confiancas, foraDoAlcance, tonalidade) {
  notasAtuais = notas;
  frasesAtuais = frases || [];
  confiancasAtuais = confiancas || [];
  foraDoAlcanceAtuais = foraDoAlcance || [];
  painelDedilhado.hidden = true;
  notaSelecionada = null;

  pauta.innerHTML = "";
  notas.forEach((nota, i) => {
    pauta.appendChild(criarChipNota(nota, confiancasAtuais[i], foraDoAlcanceAtuais[i]));
  });

  if (tonalidade) {
    tonalidadeEstimada.textContent = `Tonalidade estimada (na música original): ${tonalidade}`;
    tonalidadeEstimada.hidden = false;
  } else {
    tonalidadeEstimada.hidden = true;
  }

  renderizarPautaVisual(notas);

  secaoResultado.hidden = false;
  secaoLetra.hidden = false;
  contagensLetra = [];
  praticadasLetra = [];
  renderizarLetra();
}

function renderizarPautaVisual(notas) {
  pautaVisual.innerHTML = "";
  if (!notas.length || typeof Vex === "undefined") return;

  try {
    const NOTAS_POR_LINHA = 8;
    const LARGURA_POR_NOTA = 70;
    const ALTURA_POR_LINHA = 110;
    const linhas = [];
    for (let i = 0; i < notas.length; i += NOTAS_POR_LINHA) {
      linhas.push(notas.slice(i, i + NOTAS_POR_LINHA));
    }

    const largura = Math.max(300, NOTAS_POR_LINHA * LARGURA_POR_NOTA + 40);
    const altura = linhas.length * ALTURA_POR_LINHA + 20;

    const vf = new Vex.Flow.Factory({
      renderer: { elementId: "pautaVisual", width: largura, height: altura },
    });
    const score = vf.EasyScore();

    linhas.forEach((grupo) => {
      const notacao = grupo
        .map((nome) => {
          const m = nome.match(/^([A-Ga-g])(#?)(-?\d+)$/);
          if (!m) return null;
          return `${m[1].toLowerCase()}${m[2]}${m[3]}/q`;
        })
        .filter(Boolean)
        .join(", ");
      if (!notacao) return;

      const system = vf.System({ width: largura - 20 });
      system
        .addStave({ voices: [score.voice(score.notes(notacao))] })
        .addClef("treble");
    });

    vf.draw();
  } catch (err) {
    pautaVisual.innerHTML = "";
    const aviso = document.createElement("p");
    aviso.style.cssText = "font-size:12px;color:#948d80;padding:8px 12px";
    aviso.textContent = "Não foi possível desenhar a pauta visual agora — as notas continuam disponíveis acima.";
    pautaVisual.appendChild(aviso);
  }
}

function criarChipNota(nome, confianca, foraAlcance) {
  const chip = document.createElement("span");
  chip.className = "nota";
  chip.textContent = nome;
  if (typeof confianca === "number" && confianca < LIMIAR_CONFIANCA_BAIXA) {
    chip.classList.add("nota--baixa-confianca");
  }
  if (foraAlcance) {
    chip.classList.add("nota--fora-alcance");
  }
  chip.addEventListener("click", () => {
    tocarNota(nome);
    notaSelecionada = nome;
    dedilhadoNotaNome.textContent = nome;
    painelDedilhado.hidden = false;
  });
  return chip;
}

botaoTocarNota.addEventListener("click", () => {
  if (notaSelecionada) tocarNota(notaSelecionada);
});

function distribuirIgual(nLinhas, total) {
  const base = Math.floor(total / nLinhas);
  const resto = total % nLinhas;
  return Array.from({ length: nLinhas }, (_, i) => base + (i < resto ? 1 : 0));
}

function renderizarLetra() {
  const linhas = campoLetra.value.split("\n").filter((l) => l.trim() !== "");
  linhasLetra.innerHTML = "";

  if (!linhas.length || !notasAtuais.length) return;

  if (contagensLetra.length !== linhas.length) {
    if (frasesAtuais.length === linhas.length) {
      // As frases detectadas pelas pausas do audio batem com o numero de
      // linhas da letra - usamos isso como divisao inicial, mais precisa
      // que so dividir as notas igualmente.
      contagensLetra = frasesAtuais.map((f) => f.length);
    } else {
      contagensLetra = distribuirIgual(linhas.length, notasAtuais.length);
    }
  }

  const soma = contagensLetra.reduce((a, b) => a + b, 0);
  if (soma !== notasAtuais.length && linhas.length) {
    contagensLetra[contagensLetra.length - 1] += notasAtuais.length - soma;
  }

  let cursor = 0;
  linhas.forEach((linhaTexto, i) => {
    const qtd = Math.max(0, contagensLetra[i] || 0);
    const grupoNotas = notasAtuais.slice(cursor, cursor + qtd);
    const grupoConfiancas = confiancasAtuais.slice(cursor, cursor + qtd);
    const grupoForaAlcance = foraDoAlcanceAtuais.slice(cursor, cursor + qtd);
    cursor += qtd;

    const bloco = document.createElement("div");
    bloco.className = "letra-linha";

    const notasDiv = document.createElement("div");
    notasDiv.className = "letra-linha__notas";
    if (grupoNotas.length) {
      grupoNotas.forEach((nota, j) => {
        notasDiv.appendChild(criarChipNota(nota, grupoConfiancas[j], grupoForaAlcance[j]));
      });
    } else {
      const vazio = document.createElement("span");
      vazio.style.fontSize = "12px";
      vazio.style.color = "var(--texto-muted)";
      vazio.textContent = "sem notas nesta linha";
      notasDiv.appendChild(vazio);
    }

    const textoDiv = document.createElement("div");
    textoDiv.className = "letra-linha__texto";
    textoDiv.textContent = linhaTexto;

    const controleDiv = document.createElement("div");
    controleDiv.className = "letra-linha__controle";
    const label = document.createElement("label");
    label.textContent = "Notas nesta linha:";
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.value = qtd;
    input.addEventListener("change", (evento) => {
      contagensLetra[i] = parseInt(evento.target.value, 10) || 0;
      renderizarLetra();
    });
    controleDiv.appendChild(label);
    controleDiv.appendChild(input);

    const praticadaDiv = document.createElement("div");
    praticadaDiv.className = "letra-linha__praticada";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `praticada-${i}`;
    checkbox.checked = !!praticadasLetra[i];
    checkbox.addEventListener("change", (evento) => {
      praticadasLetra[i] = evento.target.checked;
    });
    const checkboxLabel = document.createElement("label");
    checkboxLabel.htmlFor = `praticada-${i}`;
    checkboxLabel.textContent = "Já pratiquei esta linha";
    praticadaDiv.appendChild(checkbox);
    praticadaDiv.appendChild(checkboxLabel);

    bloco.appendChild(notasDiv);
    bloco.appendChild(textoDiv);
    bloco.appendChild(controleDiv);
    bloco.appendChild(praticadaDiv);
    linhasLetra.appendChild(bloco);
  });
}

campoLetra.addEventListener("input", () => {
  contagensLetra = [];
  renderizarLetra();
});

function obterBiblioteca() {
  try {
    const bruto = localStorage.getItem(CHAVE_BIBLIOTECA);
    return bruto ? JSON.parse(bruto) : [];
  } catch (err) {
    return [];
  }
}

function salvarListaBiblioteca(lista) {
  try {
    localStorage.setItem(CHAVE_BIBLIOTECA, JSON.stringify(lista));
    return true;
  } catch (err) {
    return false;
  }
}

function formatarData(isoString) {
  const data = new Date(isoString);
  return data.toLocaleDateString("pt-BR") + " " + data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function renderizarBiblioteca() {
  const filtro = buscaBiblioteca.value.trim().toLowerCase();
  const lista = obterBiblioteca()
    .filter((item) => item.nome.toLowerCase().includes(filtro))
    .sort((a, b) => new Date(b.criadoEm) - new Date(a.criadoEm));

  listaBiblioteca.innerHTML = "";

  if (!lista.length) {
    const vazio = document.createElement("p");
    vazio.className = "biblioteca-vazia";
    vazio.textContent = filtro ? "Nada encontrado com esse nome." : "Nenhuma música salva ainda.";
    listaBiblioteca.appendChild(vazio);
    return;
  }

  lista.forEach((item) => {
    const linha = document.createElement("div");
    linha.className = "biblioteca-item";

    const info = document.createElement("div");
    info.className = "biblioteca-item__info";
    const nome = document.createElement("span");
    nome.className = "biblioteca-item__nome";
    nome.textContent = item.nome;
    const meta = document.createElement("span");
    meta.className = "biblioteca-item__meta";
    meta.textContent = `${item.notas.length} notas · ${formatarData(item.criadoEm)}`;
    info.appendChild(nome);
    info.appendChild(meta);

    const acoes = document.createElement("div");
    acoes.className = "biblioteca-item__acoes";

    const botaoAbrir = document.createElement("button");
    botaoAbrir.type = "button";
    botaoAbrir.className = "botao-secundario";
    botaoAbrir.textContent = "Abrir";
    botaoAbrir.addEventListener("click", () => abrirItemBiblioteca(item.id));

    const botaoRemover = document.createElement("button");
    botaoRemover.type = "button";
    botaoRemover.className = "botao-secundario";
    botaoRemover.textContent = "Remover";
    botaoRemover.addEventListener("click", () => removerItemBiblioteca(item.id));

    acoes.appendChild(botaoAbrir);
    acoes.appendChild(botaoRemover);

    linha.appendChild(info);
    linha.appendChild(acoes);
    listaBiblioteca.appendChild(linha);
  });
}

function abrirItemBiblioteca(id) {
  const item = obterBiblioteca().find((i) => i.id === id);
  if (!item) return;

  caixaErro.hidden = true;
  console_.hidden = true;

  mostrarResultado(item.notas, item.frases, item.confiancas, item.foraDoAlcance, item.tonalidade ? item.tonalidade.replace(/^Tonalidade estimada \(na música original\): /, "") : null);
  campoLetra.value = item.letra || "";
  contagensLetra = item.contagensLetra || [];
  praticadasLetra = item.praticadasLetra || [];
  renderizarLetra();
}

function removerItemBiblioteca(id) {
  const lista = obterBiblioteca().filter((i) => i.id !== id);
  salvarListaBiblioteca(lista);
  renderizarBiblioteca();
}

botaoSalvarBiblioteca.addEventListener("click", () => {
  const nome = nomeParaSalvar.value.trim();
  if (!nome) {
    mostrarErro("Digite um nome antes de salvar na biblioteca.");
    return;
  }
  if (!notasAtuais.length) return;

  const item = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    nome,
    notas: notasAtuais,
    frases: frasesAtuais,
    confiancas: confiancasAtuais,
    foraDoAlcance: foraDoAlcanceAtuais,
    tonalidade: tonalidadeEstimada.hidden ? null : tonalidadeEstimada.textContent,
    letra: campoLetra.value,
    contagensLetra,
    praticadasLetra,
    criadoEm: new Date().toISOString(),
  };

  const lista = obterBiblioteca();
  lista.push(item);
  const salvou = salvarListaBiblioteca(lista);

  if (salvou) {
    nomeParaSalvar.value = "";
    const textoOriginal = botaoSalvarBiblioteca.textContent;
    botaoSalvarBiblioteca.textContent = "Salvo!";
    setTimeout(() => (botaoSalvarBiblioteca.textContent = textoOriginal), 1500);
    renderizarBiblioteca();
  } else {
    mostrarErro("Não foi possível salvar - o armazenamento do navegador pode estar cheio.");
  }
});

buscaBiblioteca.addEventListener("input", renderizarBiblioteca);

renderizarBiblioteca();

botaoPdfLetra.addEventListener("click", async () => {
  const linhas = campoLetra.value.split("\n").filter((l) => l.trim() !== "");
  if (!linhas.length || !notasAtuais.length) {
    mostrarErro("Cole a letra e gere as notas antes de baixar o PDF com letra.");
    return;
  }

  const textoOriginal = botaoPdfLetra.textContent;
  botaoPdfLetra.textContent = "Gerando...";
  botaoPdfLetra.disabled = true;

  try {
    let cursor = 0;
    const grupos = linhas.map((linhaTexto, i) => {
      const qtd = Math.max(0, contagensLetra[i] || 0);
      const grupoNotas = notasAtuais.slice(cursor, cursor + qtd);
      cursor += qtd;
      return { linha: linhaTexto, notas: grupoNotas };
    });

    const resposta = await fetch("/api/pdf-letra", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grupos, origem: campoOrigem.value.trim() }),
    });

    if (!resposta.ok) {
      throw new Error("Falha ao gerar o PDF com letra");
    }

    const blob = await resposta.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "notas_com_letra.pdf";
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    mostrarErro("Não foi possível gerar o PDF com letra agora.");
  } finally {
    botaoPdfLetra.textContent = textoOriginal;
    botaoPdfLetra.disabled = false;
  }
});

async function processarResposta(resposta) {
  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder("utf-8");
  let restante = "";

  while (true) {
    const { done, value } = await leitor.read();
    if (done) break;

    restante += decodificador.decode(value, { stream: true });
    const linhas = restante.split("\n");
    restante = linhas.pop(); // guarda pedaço incompleto para a próxima leitura

    for (const linha of linhas) {
      if (!linha.trim()) continue;
      const evento_ = JSON.parse(linha);

      if (evento_.tipo === "log") {
        adicionarLinhaConsole(evento_.mensagem);
      } else if (evento_.tipo === "erro") {
        mostrarErro(evento_.mensagem);
      } else if (evento_.tipo === "resultado") {
        mostrarResultado(evento_.notas, evento_.frases, evento_.confiancas, evento_.fora_do_alcance, evento_.tonalidade);
      }
    }
  }
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const origem = campoOrigem.value.trim();
  if (!origem) return;

  limparEstado();
  botaoEnviar.disabled = true;
  botaoEnviar.textContent = "Processando...";

  try {
    const resposta = await fetch("/api/transcrever", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origem }),
    });
    await processarResposta(resposta);
  } catch (err) {
    mostrarErro("Não foi possível conectar ao servidor. Tenta de novo em alguns segundos.");
  } finally {
    botaoEnviar.disabled = false;
    botaoEnviar.textContent = "Extrair notas";
  }
});

formularioArquivo.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const arquivo = campoArquivo.files[0];
  if (!arquivo) return;

  limparEstado();
  botaoEnviarArquivo.disabled = true;
  botaoEnviarArquivo.textContent = "Processando...";

  try {
    const dadosFormulario = new FormData();
    dadosFormulario.append("arquivo", arquivo);

    const resposta = await fetch("/api/transcrever-arquivo", {
      method: "POST",
      body: dadosFormulario,
    });
    await processarResposta(resposta);
  } catch (err) {
    mostrarErro("Não foi possível conectar ao servidor. Tenta de novo em alguns segundos.");
  } finally {
    botaoEnviarArquivo.disabled = false;
    botaoEnviarArquivo.textContent = "Extrair notas";
  }
});

botaoCopiar.addEventListener("click", async () => {
  if (!notasAtuais.length) return;
  await navigator.clipboard.writeText(notasAtuais.join(" "));
  const textoOriginal = botaoCopiar.textContent;
  botaoCopiar.textContent = "Copiado!";
  setTimeout(() => (botaoCopiar.textContent = textoOriginal), 1500);
});

botaoBaixar.addEventListener("click", () => {
  if (!notasAtuais.length) return;
  const blob = new Blob([notasAtuais.join(" ")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "notas_sax.txt";
  link.click();
  URL.revokeObjectURL(url);
});

botaoPdf.addEventListener("click", async () => {
  if (!notasAtuais.length) return;
  const textoOriginal = botaoPdf.textContent;
  botaoPdf.textContent = "Gerando...";
  botaoPdf.disabled = true;

  try {
    const resposta = await fetch("/api/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notas: notasAtuais, origem: campoOrigem.value.trim() }),
    });

    if (!resposta.ok) {
      throw new Error("Falha ao gerar o PDF");
    }

    const blob = await resposta.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "notas_sax.pdf";
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    mostrarErro("Não foi possível gerar o PDF agora.");
  } finally {
    botaoPdf.textContent = textoOriginal;
    botaoPdf.disabled = false;
  }
});

// ---- Modo pratica: toca a sequencia de notas devagar, destacando cada uma ----
let praticaEmAndamento = false;
let praticaTimeoutId = null;

function pararPratica() {
  praticaEmAndamento = false;
  if (praticaTimeoutId) clearTimeout(praticaTimeoutId);
  pauta.querySelectorAll(".nota--destaque-pratica").forEach((el) => el.classList.remove("nota--destaque-pratica"));
  botaoPraticar.textContent = "▶ Tocar sequência";
}

function tocarProximaNotaPratica(indice, intervaloMs) {
  if (!praticaEmAndamento) return;
  const chips = pauta.querySelectorAll(".nota");
  chips.forEach((el) => el.classList.remove("nota--destaque-pratica"));

  if (indice >= notasAtuais.length) {
    pararPratica();
    return;
  }

  chips[indice].classList.add("nota--destaque-pratica");
  chips[indice].scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  tocarNota(notasAtuais[indice], Math.min(0.9, intervaloMs / 1000));

  praticaTimeoutId = setTimeout(() => tocarProximaNotaPratica(indice + 1, intervaloMs), intervaloMs);
}

botaoPraticar.addEventListener("click", () => {
  if (praticaEmAndamento) {
    pararPratica();
    return;
  }
  if (!notasAtuais.length) return;

  praticaEmAndamento = true;
  botaoPraticar.textContent = "■ Parar";
  const intervaloMs = parseInt(velocidadePratica.value, 10) || 550;
  tocarProximaNotaPratica(0, intervaloMs);
});

// ---- Metronomo simples ----
let metronomoEmAndamento = false;
let metronomoIntervalId = null;

botaoMetronomo.addEventListener("click", () => {
  if (metronomoEmAndamento) {
    metronomoEmAndamento = false;
    clearInterval(metronomoIntervalId);
    botaoMetronomo.textContent = "▶ Iniciar";
    return;
  }

  const bpm = Math.max(30, Math.min(240, parseInt(bpmMetronomo.value, 10) || 80));
  const intervaloMs = 60000 / bpm;

  metronomoEmAndamento = true;
  botaoMetronomo.textContent = "■ Parar";
  tocarClickMetronomo();
  metronomoIntervalId = setInterval(tocarClickMetronomo, intervaloMs);
});
