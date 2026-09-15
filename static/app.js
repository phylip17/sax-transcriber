const formulario = document.getElementById("formulario");
const campoOrigem = document.getElementById("origem");
const botaoEnviar = document.getElementById("botaoEnviar");

const console_ = document.getElementById("console");
const linhasConsole = document.getElementById("linhasConsole");

const secaoResultado = document.getElementById("resultado");
const pauta = document.getElementById("pauta");
const botaoCopiar = document.getElementById("botaoCopiar");
const botaoBaixar = document.getElementById("botaoBaixar");
const botaoPdf = document.getElementById("botaoPdf");

const caixaErro = document.getElementById("erro");

let notasAtuais = [];

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
  caixaErro.hidden = true;
  secaoResultado.hidden = true;
  console_.hidden = false;
}

function mostrarErro(mensagem) {
  caixaErro.textContent = mensagem;
  caixaErro.hidden = false;
}

function mostrarResultado(notas) {
  notasAtuais = notas;
  pauta.innerHTML = "";
  notas.forEach((nota) => {
    const chip = document.createElement("span");
    chip.className = "nota";
    chip.textContent = nota;
    pauta.appendChild(chip);
  });
  secaoResultado.hidden = false;
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
          mostrarResultado(evento_.notas);
        }
      }
    }
  } catch (err) {
    mostrarErro("Não foi possível conectar ao servidor local. Confira se o app.py está rodando.");
  } finally {
    botaoEnviar.disabled = false;
    botaoEnviar.textContent = "Extrair notas";
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
