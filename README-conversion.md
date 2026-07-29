# PyTrader JS core (conversión parcial)

Este repositorio contiene una conversión parcial de la lógica de `F_Trader_4.py` a un módulo Node.js.

Archivos añadidos:

- `src/F_Trader_4.js`: implementación de funciones core (normalización de tickers, símbolo TradingView, cálculo de indicadores).
- `package.json`: dependencias mínimas (`technicalindicators`).

Instalación:

```bash
cd /home/jac4806/Documentos/PyTrader
npm install
```

Uso:

Importa `calculateIndicators` y pásale un array de objetos OHLCV:

```js
const { calculateIndicators } = require('./src/F_Trader_4');

const sample = [
  { date: '2026-01-01', open: 10, high: 11, low: 9.5, close: 10.5, volume: 1000 },
  // ... más filas
];

const augmented = calculateIndicators(sample);
console.log(augmented[augmented.length-1]);
```

Notas:
- La conversión cubre la lógica de indicadores (RSI, MACD, VWAP, ADX simple, score y señales).
- No incluye por ahora la descarga automática de datos desde Yahoo Finance ni la integración de UI (PyQt).
- Si quieres que añada descarga automática (`yahoo-finance2`) y un CLI o app Electron, indícalo y lo implemento en el siguiente paso.
