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

const caixaErro = document.getElementById("erro");

let notasAtuais = [];
let frasesAtuais = [];
let contagensLetra = [];

const CHAVE_BIBLIOTECA = "saxAltoBiblioteca";

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

function mostrarResultado(notas, frases) {
  notasAtuais = notas;
  frasesAtuais = frases || [];
  pauta.innerHTML = "";
  notas.forEach((nota) => {
    const chip = document.createElement("span");
    chip.className = "nota";
    chip.textContent = nota;
    pauta.appendChild(chip);
  });
  secaoResultado.hidden = false;
  secaoLetra.hidden = false;
  contagensLetra = [];
  renderizarLetra();
}

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
    cursor += qtd;

    const bloco = document.createElement("div");
    bloco.className = "letra-linha";

    const notasDiv = document.createElement("div");
    notasDiv.className = "letra-linha__notas";
    if (grupoNotas.length) {
      grupoNotas.forEach((nota) => {
        const chip = document.createElement("span");
        chip.className = "nota";
        chip.textContent = nota;
        notasDiv.appendChild(chip);
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

    bloco.appendChild(notasDiv);
    bloco.appendChild(textoDiv);
    bloco.appendChild(controleDiv);
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

  mostrarResultado(item.notas, item.frases);
  campoLetra.value = item.letra || "";
  contagensLetra = item.contagensLetra || [];
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
    letra: campoLetra.value,
    contagensLetra,
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
        mostrarResultado(evento_.notas, evento_.frases);
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
