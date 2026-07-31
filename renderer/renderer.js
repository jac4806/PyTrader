const btn = document.getElementById('btnAnalyze');
const status = document.getElementById('status');
const resultsTbody = document.querySelector('#results tbody');
const filterText = document.getElementById('filterText');
const filterScore = document.getElementById('filterScore');
const btnSendEmail = document.getElementById('btnSendEmail');
const btnAutoEmail = document.getElementById('btnAutoEmail');
const periodInput = document.getElementById('period');
const intervalInput = document.getElementById('interval');
const tickersInput = document.getElementById('tickers');

let lastResults = [];
let sortState = { col: 'Score', dir: -1 };

// cargar configuración guardada al inicio
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const cfg = await window.pytrader.getConfig();
    if (cfg) {
      if (cfg.smtp) {
        document.getElementById('smtpHost').value = cfg.smtp.host || '';
        document.getElementById('smtpUser').value = cfg.smtp.user || '';
        document.getElementById('smtpPass').value = cfg.smtp.pass || '';
        document.getElementById('emailTo').value = cfg.smtp.to || '';
      }
      if (cfg.ui) {
        tickersInput.value = cfg.ui.tickers || tickersInput.value;
        periodInput.value = cfg.ui.period || periodInput.value;
        intervalInput.value = cfg.ui.interval || intervalInput.value;
        filterText.value = cfg.ui.filterText || filterText.value;
        filterScore.value = cfg.ui.filterScore || filterScore.value;
      }
    }
  } catch (e) {
    console.warn('No se pudo cargar configuración:', e);
  }
});

function renderTable(results) {
  resultsTbody.innerHTML = '';
  // apply filter
  const text = (filterText.value || '').toLowerCase();
  const minScore = parseInt(filterScore.value || '0', 10) || 0;
  let filtered = results.filter(r => {
    const s = (r.ticker || r.Ticker || '').toString().toLowerCase();
    const sig = (r.result ? (r.result.signal || '') : (r.Signal || '')).toString().toLowerCase();
    const score = parseInt(r.result ? (r.result.score || 0) : (r.Score || 0), 10) || 0;
    if (text) {
      if (!s.includes(text) && !sig.includes(text)) return false;
    }
    if (score < minScore) return false;
    return true;
  });

  // sort
  filtered.sort((a,b) => {
    const A = a.result ? (a.result[sortState.col.toLowerCase()] || a.result[sortState.col] ) : (a[sortState.col] || a[sortState.col.toLowerCase()]);
    const B = b.result ? (b.result[sortState.col.toLowerCase()] || b.result[sortState.col] ) : (b[sortState.col] || b[sortState.col.toLowerCase()]);
    const na = A == null ? -Infinity : A;
    const nb = B == null ? -Infinity : B;
    if (na < nb) return -1 * sortState.dir;
    if (na > nb) return 1 * sortState.dir;
    return 0;
  });

  for (const r of filtered) {
    const tr = document.createElement('tr');
    if (r.error) {
      tr.innerHTML = `<td>${r.ticker}</td><td colspan="5">Error: ${r.error}</td>`;
    } else if (r.result) {
      const last = r.result;
      const score = last.score || last.Score || '';
      tr.innerHTML = `<td>${r.ticker}</td><td>${last.signal||''}</td><td>${score}</td><td>${last.close||last.Close||''}</td><td>${last.rsi||''}</td><td>${last.macd||''}</td>`;
    } else {
      tr.innerHTML = `<td>${r.ticker}</td><td colspan="5">Sin resultado</td>`;
    }
    resultsTbody.appendChild(tr);
  }
}

btn.addEventListener('click', async () => {
  const raw = tickersInput.value || '';
  const tickers = raw.split(/[,\n;]+/).map(s => s.trim()).filter(Boolean);
  if (tickers.length === 0) return alert('Introduce tickers');
  status.textContent = 'Analizando...';
  resultsTbody.innerHTML = '';
  try {
    const options = {
      period: periodInput.value.trim() || '1y',
      interval: intervalInput.value.trim() || '1d',
      indicators: {}
    };
    const res = await window.pytrader.analyze(tickers, options);
    lastResults = res.map(r => ({ ticker: r.ticker, result: r.result, error: r.error }));
    renderTable(lastResults);
    status.textContent = 'Análisis finalizado.';
    await window.pytrader.setConfig('ui', {
      tickers: tickersInput.value,
      period: options.period,
      interval: options.interval,
      filterText: filterText.value,
      filterScore: filterScore.value
    });
  } catch (err) {
    status.textContent = 'Error: ' + String(err);
  }
});

// Sorting by clicking headers
document.querySelectorAll('#results thead th').forEach(th => {
  th.style.cursor = 'pointer';
  th.addEventListener('click', () => {
    const col = th.dataset.col || th.textContent;
    if (sortState.col === col) sortState.dir = -sortState.dir; else { sortState.col = col; sortState.dir = -1; }
    renderTable(lastResults);
  });
});

filterText.addEventListener('input', () => renderTable(lastResults));
filterScore.addEventListener('input', () => renderTable(lastResults));

async function sendEmailAction(auto=false) {
  const to = document.getElementById('emailTo').value.trim();
  if (!to) return alert('Introduce dirección de destino.');
  const smtp = { host: document.getElementById('smtpHost').value.trim(), user: document.getElementById('smtpUser').value.trim(), pass: document.getElementById('smtpPass').value };
  smtp.to = to;
  smtp.from = smtp.user;
  smtp.port = 587;
  smtp.tls = true;

  const minScore = parseInt(filterScore.value||'0',10) || 0;
  const highs = [];
  for (const r of lastResults) {
    const score = r.result ? (r.result.score || r.result.Score || 0) : (r.Score || 0);
    if (score >= minScore && !r.error && r.result) {
      highs.push({ Ticker: r.ticker, Score: score, Signal: r.result.signal, Precio: r.result.close });
    }
  }
  if (highs.length === 0) {
    if (!auto) alert('No hay resultados con score >= mínimo');
    return;
  }

  status.textContent = 'Enviando email...';
  try {
    const resp = await window.pytrader.sendEmail({ smtp, results: highs, subject: `PyTrader: ${highs.length} resultados`, text: 'Resultados con score alto:' });
    status.textContent = resp.message || JSON.stringify(resp);
    if (!resp.success) alert('Error al enviar: ' + resp.message);
    else {
      // guardar credenciales SMTP (sincronamente en store)
      try {
        await window.pytrader.setConfig('smtp', smtp);
      } catch (e) {
        console.warn('No se pudo guardar config:', e);
      }
    }
  } catch (err) {
    status.textContent = 'Error: ' + String(err);
  }
}

btnSendEmail.addEventListener('click', () => sendEmailAction(false));
btnAutoEmail.addEventListener('click', () => sendEmailAction(true));
