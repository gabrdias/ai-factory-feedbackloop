// Coletor de medições pela interface do app (usado nas medições do dev, 19/10/2026).
//
// Como usar: abra o app (dev ou local), configure na barra lateral "Avançado: medir otimizações"
// (chamadas em paralelo e cache), cole este arquivo no console do navegador e rode:
//
//     await window.__medir(6, 'A: 1 em paralelo, sem cache');
//     JSON.stringify(window.__med.runs)
//
// A 1ª execução de cada configuração é de AQUECIMENTO (a primeira análise após cada reinício do
// serviço, ou com uma configuração nova, não entra nos percentis do dashboard); descarte-a ao
// calcular as estatísticas. Para a medição reproduzível sem navegador, use scripts/benchmark.py.
//
// Lê, na tela de resultado: Duração (do pipeline, medida pelo app), Chamadas ao LLM, Tokens e
// Custo estimado, e o bloco "Distribuição de sentimento + Principais temas" (para comparar se as
// configurações produzem o mesmo resultado agregado). `parede_s` é o tempo de relógio entre o
// clique e o resultado na tela, que inclui a renderização.
//
// Versão 2: o Streamlit atualiza a tela de cima para baixo. A versão 1 lia os campos assim que
// aparecia o resultado e, numa execução, leu chamadas/tokens do resultado ANTERIOR. Agora a leitura
// só é aceita depois de ficar idêntica em 4 consultas seguidas (1 s), e o clique só acontece depois
// de a tela anterior ter parado de mudar.

window.__med = window.__med || { runs: [], done: false, inicio: new Date().toISOString() };

window.__medir = async (n, rotulo, limparCache = false) => {
  window.__med.done = false;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const botao = (texto) => [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === texto);
  const rodando = () => /Classificando as respostas e montando o resumo/.test(document.body.innerText);
  const ler = () => {
    const t = document.body.innerText;
    const m = t.match(/Duração\s+([\d.,]+)\s*s\s+Chamadas ao LLM\s+(\d+)\s+Tokens \(entrada\/saída\)\s+(\d+)\/(\d+)\s+Custo estimado\s+(US\$\s*[\d.,]+|n\/d)/);
    if (!m) return null;
    const bloco = ((t.match(/Distribuição de sentimento([\s\S]*?)Leitura e ações recomendadas/) || [, ''])[1]).replace(/\s+/g, ' ').trim();
    return { duracao: parseFloat(m[1].replace(',', '.')), chamadas: +m[2], tin: +m[3], tout: +m[4], custo: m[5], bloco };
  };
  const estavel = async () => {
    let ultima = null;
    let iguais = 0;
    for (let k = 0; k < 40; k++) {
      await sleep(250);
      const atual = ler();
      const chave = atual ? JSON.stringify(atual) : null;
      iguais = chave && chave === ultima ? iguais + 1 : 0;
      ultima = chave;
      if (iguais >= 3) return atual;
    }
    return ler();
  };
  for (let i = 0; i < n; i++) {
    if (limparCache) {
      const b = botao('Excluir cache agora');
      if (b) { b.click(); await sleep(1500); }
    }
    botao('Analisar respostas').click();
    const t0 = Date.now();
    let rodou = false;
    while (true) {
      await sleep(250);
      if (rodando()) rodou = true;
      if (rodou && !rodando() && ler()) {
        const fim = Date.now();
        const lido = await estavel();
        window.__med.runs.push({ rotulo, i: i + 1, ...lido, parede_s: +((fim - t0) / 1000).toFixed(1), hora: new Date().toISOString() });
        break;
      }
      if (Date.now() - t0 > 300000) {
        window.__med.runs.push({ rotulo, i: i + 1, timeout: true });
        break;
      }
    }
    await sleep(1000);
  }
  window.__med.done = true;
};
