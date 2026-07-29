const ti = require('technicalindicators');

function normalizeTicker(ticker) {
  if (!ticker) return '';
  ticker = String(ticker).toUpperCase().trim();
  if (ticker.includes(':')) {
    const [exchange, symbol] = ticker.split(':', 2);
    const sym = symbol.replace(/\s+/g, '').replace('/', '-');
    if (!sym) return '';
    const map = {
      BME: '.MC', BM: '.MC', MC: '.MC', EPA: '.PA', PAR: '.PA', LON: '.L',
      LSE: '.L', XETR: '.DE', ETR: '.DE', FRA: '.F', MIL: '.MI', BIT: '.MI',
      AMS: '.AS', HEL: '.HE', STO: '.ST', SWX: '.SW', SIX: '.SW', OSL: '.OL',
      CPH: '.CO', BRU: '.BR', LIS: '.LS', VIE: '.VI'
    };
    if (map[exchange] && !sym.includes('.')) return sym + map[exchange];
    const exchangeWithout = new Set(['NASDAQ', 'NYSE', 'AMEX', 'ARCA', 'CBOE']);
    if (exchangeWithout.has(exchange)) return sym;
    return sym;
  }
  return ticker.replace(/\s+/g, '').replace('/', '-');
}

const TV_SUFFIX_EXCHANGE_MAP = {
  '.MC': 'BME', '.PA': 'EURONEXT', '.L': 'LSE', '.DE': 'XETR', '.F': 'FWB',
  '.MI': 'MIL', '.AS': 'EURONEXT', '.HE': 'EURONEXT', '.ST': 'OMXSTO',
  '.SW': 'SIX', '.OL': 'OSE', '.CO': 'OMXCOP', '.BR': 'EURONEXT', '.LS': 'EURONEXT', '.VI': 'VIE'
};

function buildTradingViewSymbol(ticker) {
  if (!ticker) return '';
  ticker = String(ticker).trim().toUpperCase();
  if (ticker.includes(':')) return ticker;
  for (const suf of Object.keys(TV_SUFFIX_EXCHANGE_MAP)) {
    if (ticker.endsWith(suf.replace('.', ''))) {
      const base = ticker.slice(0, -suf.length + 1);
      return `${TV_SUFFIX_EXCHANGE_MAP[suf]}:${base}`;
    }
  }
  return `NASDAQ:${ticker}`;
}

function ewma(values, span) {
  const alpha = 2 / (span + 1);
  const out = [];
  let prev = null;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null || Number.isNaN(v)) {
      out.push(null);
      continue;
    }
    if (prev === null) prev = v;
    else prev = alpha * v + (1 - alpha) * prev;
    out.push(prev);
  }
  return out;
}

function cumulative(values) {
  const out = [];
  let s = 0;
  for (const v of values) {
    s += (v || 0);
    out.push(s);
  }
  return out;
}

function padArray(arr, length) {
  const out = Array(length - arr.length).fill(null).concat(arr);
  return out;
}

function calculateIndicators(ohlcv, options = {}) {
  // ohlcv: array of {open, high, low, close, volume, date}
  const defaults = {
    rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
    macdFast: 12, macdSlow: 26, macdSignal: 9,
    per: null, perMax: 25, adxPeriod: 14
  };
  const cfg = Object.assign({}, defaults, options);
  const n = ohlcv.length;
  if (n === 0) return [];

  const close = ohlcv.map(r => r.close);
  const high = ohlcv.map(r => r.high);
  const low = ohlcv.map(r => r.low);
  const open = ohlcv.map(r => r.open);
  const volume = ohlcv.map(r => r.volume);

  // CFI
  const cfiRaw = volume.map((v, i) => (v || 0) * ((close[i] || 0) - (open[i] || 0)));
  const cfi = ewma(cfiRaw, 20);
  const cfiMa = ewma(cfi.map(x => x == null ? 0 : x), 20);
  const cfiUp = cfi.map((v, i) => v != null && cfiMa[i] != null ? v > cfiMa[i] : false);

  // Vol MA (SMA 50)
  const volMa = ti.SMA.calculate({ period: 50, values: volume });
  const volMaP = padArray(volMa, n);
  const volStrong = volume.map((v, i) => (v || 0) > (volMaP[i] || 0));

  const spread = ohlcv.map(r => Math.max((r.high - r.low), 0.0001));
  const closePos = close.map((c, i) => ((c - low[i]) / spread[i]));
  const strength = closePos.map(cp => 2 * cp - 1);
  const flow = volume.map((v, i) => volStrong[i] ? strength[i] * (v || 0) : 0);
  const flowSmooth = ewma(flow, 5);

  // RSI
  const rsi = ti.RSI.calculate({ period: cfg.rsiPeriod, values: close });
  const rsiP = padArray(rsi, n).map(v => v == null ? 50 : v);
  const rsiBullish = rsiP.map((v, i) => i>0 ? v > 50 && v > rsiP[i-1] : false);

  // MACD
  const macdOut = ti.MACD.calculate({
    values: close,
    fastPeriod: cfg.macdFast,
    slowPeriod: cfg.macdSlow,
    signalPeriod: cfg.macdSignal,
    SimpleMAOscillator: false,
    SimpleMASignal: false
  });
  const macd = padArray(macdOut.map(x=>x.MACD), n);
  const macdSignal = padArray(macdOut.map(x=>x.signal), n);
  const macdBullish = macd.map((m, i) => (m != null && macdSignal[i] != null) ? (m > macdSignal[i] && m > (macd[i-1]||-Infinity)) : false);

  // VWAP
  const typical = ohlcv.map(r => (r.high + r.low + r.close) / 3);
  const tpVol = typical.map((t, i) => (t || 0) * (volume[i] || 0));
  const cumTpVol = cumulative(tpVol);
  const cumVol = cumulative(volume);
  const vwap = cumTpVol.map((v, i) => (cumVol[i] ? v / cumVol[i] : null));
  const vwapBullish = close.map((c,i) => (c != null && vwap[i] != null) ? c > vwap[i] : false);

  // ADX
  const adxOut = ti.ADX.calculate({ period: cfg.adxPeriod, high, low, close });
  const adx = padArray(adxOut, n).map(x => (x && x.adx) ? x.adx : null);
  const adxStrong = adx.map(v => v != null ? v >= 20 : false);

  // Moving averages for trend
  const ema21 = padArray(ti.EMA.calculate({ period: 21, values: close }), n);
  const sma50 = padArray(ti.SMA.calculate({ period: 50, values: close }), n);
  const sma200 = padArray(ti.SMA.calculate({ period: 200, values: close }), n);
  const trendUp = close.map((c,i) => (c != null && ema21[i]!=null && sma50[i]!=null && sma200[i]!=null) ? (c > ema21[i] && ema21[i] > sma50[i] && sma50[i] > sma200[i]) : false);

  // Divergences (simple heuristic)
  const bullDiv = ohlcv.map((r,i) => i>=10 ? (low[i-5] < low[i-10] && (flowSmooth[i-5] || 0) > (flowSmooth[i-10] || 0)) : false);
  const bearDiv = ohlcv.map((r,i) => i>=10 ? (high[i-5] > high[i-10] && (flowSmooth[i-5] || 0) < (flowSmooth[i-10] || 0)) : false);

  const accumulation = ohlcv.map((r,i) => volStrong[i] && closePos[i] > 0.6 && r.close >= r.open);
  const distribution = ohlcv.map((r,i) => volStrong[i] && closePos[i] < 0.4 && r.close <= r.open);

  const buyPro = ohlcv.map((r,i) => trendUp[i] && cfiUp[i] && ((flowSmooth[i]||0) > 0 || accumulation[i]));
  const buyEarly = bullDiv.map((v,i) => v && (flowSmooth[i]||0) > 0);
  const sell = ohlcv.map((r,i) => distribution[i] || bearDiv[i] || ((flowSmooth[i]||0) < 0));

  // PER support
  const per = cfg.per != null ? cfg.per : null;
  const perSupportBool = per != null ? (per > 0 && per <= cfg.perMax) : false;

  // Score
  const results = [];
  for (let i=0;i<n;i++) {
    const score = Math.max(0, Math.min(100,
      (trendUp[i] ? 25 : 0) +
      (cfiUp[i] ? 25 : 0) +
      (false ? 20 : 0) +
      (accumulation[i] ? 15 : 0) +
      ((flowSmooth[i]||0) > 0 ? 15 : 0) +
      (rsiBullish[i] ? 5 : 0) +
      (macdBullish[i] ? 5 : 0) +
      (perSupportBool ? 5 : 0) +
      (adxStrong[i] ? 5 : 0) +
      (vwapBullish[i] ? 5 : 0)
    ));

    const signal = buyPro[i] || ((rsiBullish[i] && macdBullish[i]) && trendUp[i]) ? 'COMPRA FUERTE' : (buyEarly[i] ? 'COMPRA TEMPRANA' : (sell[i] ? 'VENTA' : 'ESPERA'));

    results.push(Object.assign({}, ohlcv[i], {
      cfi: cfi[i],
      cfiUp: cfiUp[i],
      volMa: volMaP[i],
      volStrong: volStrong[i],
      closePos: closePos[i],
      strength: strength[i],
      flow: flow[i],
      flowSmooth: flowSmooth[i],
      rsi: rsiP[i],
      rsiBullish: rsiBullish[i],
      macd: macd[i],
      macdSignal: macdSignal[i],
      macdBullish: macdBullish[i],
      vwap: vwap[i],
      vwapBullish: vwapBullish[i],
      adx: adx[i],
      adxStrong: adxStrong[i],
      ema21: ema21[i],
      sma50: sma50[i],
      sma200: sma200[i],
      trendUp: trendUp[i],
      bullDiv: bullDiv[i],
      bearDiv: bearDiv[i],
      accumulation: accumulation[i],
      distribution: distribution[i],
      buyPro: buyPro[i],
      buyEarly: buyEarly[i],
      sell: sell[i],
      per: per,
      perSupport: perSupportBool,
      score,
      signal
    }));
  }

  return results;
}

module.exports = {
  normalizeTicker,
  buildTradingViewSymbol,
  calculateIndicators,
  ewma
};
