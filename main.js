const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const nodemailer = require('nodemailer');
const Store = require('electron-store');
const store = new Store({ name: 'pytrader' });

function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, 'src', 'electron-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Analysis handler: main process will perform downloads and indicator calculation
ipcMain.handle('analyze', async (event, tickers, options) => {
  const yf = require('yahoo-finance2').default;
  const { calculateIndicators } = require('./src/F_Trader_4');
  const results = [];
  for (const ticker of tickers) {
    try {
      const params = { period: options.period || '1y', interval: options.interval || '1d' };
      const hist = await yf.historical(ticker, params);
      if (!hist || hist.length === 0) {
        results.push({ ticker, error: 'Sin datos' });
        continue;
      }
      // Convert to ohlcv array with oldest->newest
      const ohlcv = hist.map(h => ({
        date: h.date,
        open: h.open,
        high: h.high,
        low: h.low,
        close: h.close,
        volume: h.volume
      })).reverse();

      const augmented = calculateIndicators(ohlcv, options.indicators || {});
      const last = augmented[augmented.length - 1] || null;
      results.push({ ticker, result: last });
    } catch (err) {
      results.push({ ticker, error: String(err) });
    }
  }
  return results;
});

ipcMain.handle('send-email', async (event, payload) => {
  try {
    const { smtp, results, subject, text } = payload;
    if (!smtp || !smtp.host || !smtp.user || !smtp.pass) {
      return { success: false, message: 'Faltan datos SMTP (host/user/pass).' };
    }

    const transporter = nodemailer.createTransport({
      host: smtp.host,
      port: smtp.port || 587,
      secure: smtp.secure || false,
      auth: {
        user: smtp.user,
        pass: smtp.pass,
      },
      tls: smtp.tls ? { rejectUnauthorized: false } : undefined,
    });

    const bodyLines = [];
    bodyLines.push(text || 'Resultados:');
    bodyLines.push('');
    for (const r of results) {
      bodyLines.push(`Ticker: ${r.Ticker || r.ticker || ''} | Score: ${r.Score || r.score || ''} | Signal: ${r.Signal || r.signal || ''} | Precio: ${r.Precio || r.close || ''}`);
    }

    const message = {
      from: smtp.from || smtp.user,
      to: smtp.to,
      subject: subject || `Resultados PyTrader (${results.length})`,
      text: bodyLines.join('\n'),
    };

    await transporter.sendMail(message);
    return { success: true, message: `Correo enviado a ${smtp.to}` };
  } catch (err) {
    return { success: false, message: String(err) };
  }
});

ipcMain.handle('get-config', async (event, key) => {
  try {
    if (!key) return store.store;
    return store.get(key);
  } catch (err) {
    return null;
  }
});

ipcMain.handle('set-config', async (event, key, value) => {
  try {
    if (!key) return { success: false, message: 'Key required' };
    store.set(key, value);
    return { success: true };
  } catch (err) {
    return { success: false, message: String(err) };
  }
});
