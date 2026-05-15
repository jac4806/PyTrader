# =========================================================
#   Mi Trader_2.py | V03 | 08/05/2026
# =========================================================
# SMART MONEY / CFI SCREENER
#
# Analiza empresas usando:
# - CFI Diario y Semanal
# - Smart Money Flow
# - Acumulación / Distribución
# - Tendencia
# - Divergencias
#
# Exporta resultados a Excel.
# =========================================================
# INSTALAR LIBRERÍAS
# =========================================================
#
# pip install yfinance pandas numpy openpyxl
#
# =========================================================

import time
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

# =========================================================
# CONFIGURACIÓN
# =========================================================

PERIOD = "1y"
INTERVAL = "1d"

EXPORT_EXCEL = True
EXCEL_NAME = "SmartMoney_Screener.xlsx"

# Tiempo entre peticiones a Yahoo
DELAY_BETWEEN_REQUESTS = 1

# Archivo TXT con tickers
TXT_FILE = "Mi_Lista.txt"

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def download_data_safe(ticker, period="1y", interval="1d", max_retries=3):
    """
    Descarga datos de yfinance con manejo de errores para tickers internacionales.
    """
    for attempt in range(max_retries):
        try:
            stock_data = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                group_by="column"
            )
            
            # Corregir MultiIndex si existe
            if isinstance(stock_data.columns, pd.MultiIndex):
                stock_data.columns = stock_data.columns.get_level_values(0)
            
            # Limpiar NaN
            stock_data.dropna(inplace=True)
            
            if stock_data.empty:
                return None, f"Sin datos disponibles para {ticker}"
            
            return stock_data, None
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)  # Esperar antes de reintentar
            else:
                return None, f"Error después de {max_retries} intentos: {str(e)}"

# =========================================================
# CARGAR TICKERS DESDE TXT
# =========================================================

def load_tickers(filename):
    """Carga y limpia tickers desde archivo TXT, soportando sufijos internacionales."""
    try:
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        print(f"ERROR: Archivo '{filename}' no encontrado")
        return []
    
    # Prefijos antiguos a remover (para compatibilidad)
    prefixes = ["NASDAQ:", "NYSE:", "AMEX:"]
    tickers = set()
    
    for item in content.split(","):
        item = item.strip()
        if item:
            # Remover prefijos antiguos
            for prefix in prefixes:
                item = item.replace(prefix, "")
            # Normalizar a mayúsculas y aceptar sufijos (ej. BBVA.MC)
            item = item.upper().replace(":", ".")  # Convertir : a . si hay
            tickers.add(item)
    
    return sorted(list(tickers))

TICKERS = load_tickers(TXT_FILE)

if TICKERS:
    print("\n" + "=" * 80)
    print(f"TICKERS CARGADOS ({len(TICKERS)}): {', '.join(TICKERS)}")
    print("=" * 80)
else:
    print("\n" + "=" * 80)
    print("✗ NO SE CARGARON TICKERS")
    print("=" * 80)
    exit()

# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================


def calculate_indicators(dataframe):
    """
    Calcula indicadores Smart Money, CFI, Flow, Tendencia y señales.
    """
    data = dataframe.copy()

    # =====================================================
    # CFI DIARIO
    # =====================================================
    cfi_raw = data["Volume"] * (data["Close"] - data["Open"])
    data["cfi"] = cfi_raw.ewm(span=20, adjust=False).mean()
    data["cfi_ma"] = data["cfi"].ewm(span=20, adjust=False).mean()
    data["cfi_up"] = data["cfi"] > data["cfi_ma"]

    # =====================================================
    # CFI SEMANAL
    # =====================================================
    weekly = data.resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    })

    weekly_cfi_raw = weekly["Volume"] * (weekly["Close"] - weekly["Open"])
    weekly["cfi_w"] = weekly_cfi_raw.ewm(span=20, adjust=False).mean()
    weekly["cfi_w_ma"] = weekly["cfi_w"].ewm(span=20, adjust=False).mean()
    weekly["cfi_w_up"] = weekly["cfi_w"] > weekly["cfi_w_ma"]

    # Alinear datos semanales con diarios (usar ffill en lugar de deprecated reindex)
    data["cfi_w_up"] = weekly["cfi_w_up"].reindex(data.index, fill_value=False).ffill()

    # =====================================================
    # VOLUMEN
    # =====================================================
    data["vol_ma"] = data["Volume"].rolling(50).mean()
    data["vol_strong"] = data["Volume"] > data["vol_ma"]

    # =====================================================
    # FLOW / SMART MONEY
    # =====================================================
    spread = np.maximum(data["High"] - data["Low"], 0.0001)
    data["close_pos"] = (data["Close"] - data["Low"]) / spread
    data["strength"] = 2 * data["close_pos"] - 1
    data["flow"] = np.where(data["vol_strong"], data["strength"] * data["Volume"], 0)
    data["flow_smooth"] = data["flow"].ewm(span=5, adjust=False).mean()

    # =====================================================
    # ACUMULACIÓN / DISTRIBUCIÓN
    # =====================================================
    data["accumulation"] = (
        data["vol_strong"] &
        (data["close_pos"] > 0.6) &
        (data["Close"] >= data["Open"])
    )
    data["distribution"] = (
        data["vol_strong"] &
        (data["close_pos"] < 0.4) &
        (data["Close"] <= data["Open"])
    )

    # =====================================================
    # TENDENCIA
    # =====================================================
    data["ema21"] = data["Close"].ewm(span=21, adjust=False).mean()
    data["sma50"] = data["Close"].rolling(50).mean()
    data["sma200"] = data["Close"].rolling(200).mean()
    data["trend_up"] = (
        (data["Close"] > data["ema21"]) &
        (data["ema21"] > data["sma50"]) &
        (data["sma50"] > data["sma200"])
    )

    # =====================================================
    # DIVERGENCIAS
    # =====================================================
    data["bull_div"] = (
        (data["Low"].shift(5) < data["Low"].shift(10)) &
        (data["flow_smooth"].shift(5) > data["flow_smooth"].shift(10))
    )
    data["bear_div"] = (
        (data["High"].shift(5) > data["High"].shift(10)) &
        (data["flow_smooth"].shift(5) < data["flow_smooth"].shift(10))
    )

    # =====================================================
    # SEÑALES
    # =====================================================
    data["buy_pro"] = (
        data["trend_up"] &
        data["cfi_up"] &
        ((data["flow_smooth"] > 0) | data["accumulation"])
    )
    data["buy_early"] = data["bull_div"] & (data["flow_smooth"] > 0)
    data["sell"] = data["distribution"] | data["bear_div"] | (data["flow_smooth"] < 0)

    # =====================================================
    # LIMPIAR NaN BOOLEANOS
    # =====================================================
    bool_cols = [
        "cfi_up", "cfi_w_up", "vol_strong", "accumulation",
        "distribution", "trend_up", "bull_div", "bear_div",
        "buy_pro", "buy_early", "sell"
    ]
    data[bool_cols] = data[bool_cols].fillna(False)

    # =====================================================
    # SCORE
    # =====================================================
    data["score"] = (
        (data["trend_up"].astype(int) * 25) +
        (data["cfi_up"].astype(int) * 25) +
        (data["cfi_w_up"].astype(int) * 20) +
        (data["accumulation"].astype(int) * 15) +
        ((data["flow_smooth"] > 0).astype(int) * 15)
    )

    # =====================================================
    # TEXTO SEÑAL
    # =====================================================
    conditions = [data["buy_pro"], data["buy_early"], data["sell"]]
    choices = ["COMPRA FUERTE", "COMPRA TEMPRANA", "VENTA"]
    data["signal"] = np.select(conditions, choices, default="ESPERA")

    return data


# =========================================================
# ANALIZAR EMPRESAS
# =========================================================

results = []

for ticker in TICKERS:
    print(f"\nAnalizando {ticker}...")
    
    # Descargar datos con manejo de errores
    stock_data, error_msg = download_data_safe(ticker, period=PERIOD, interval=INTERVAL)
    
    if stock_data is None:
        print(f"⚠️  {ticker}: {error_msg}")
        continue
    
    try:
        # Calcular indicadores
        stock_data = calculate_indicators(stock_data)
        last = stock_data.iloc[-1]

        # Guardar resultados
        results.append({
            "Ticker": ticker,
            "Precio": round(float(last["Close"]), 2),
            "Signal": str(last["signal"]),
            "Score": int(last["score"]),
            "Trend": "SI" if last["trend_up"] else "NO",
            "CFI Diario": "FUERTE" if last["cfi_up"] else "DEBIL",
            "CFI Semanal": "FUERTE" if last["cfi_w_up"] else "DEBIL",
            "Flow": "COMPRANDO" if last["flow_smooth"] > 0 else "VENDIENDO",
            "Smart Money": (
                "ACUMULANDO" if last["accumulation"]
                else "DISTRIBUYENDO" if last["distribution"]
                else "NEUTRO"
            ),
            "Vol Relativo": (
                round(float(last["Volume"]) / float(last["vol_ma"]), 2)
                if float(last["vol_ma"]) > 0 else 0
            ),
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        print(f"✓ {ticker} OK")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print(f"✗ ERROR procesando {ticker}: {type(error).__name__}: {str(error)[:60]}")

# =========================================================
# CREAR DATAFRAME
# =========================================================

results_df = pd.DataFrame(results)

# =========================================================
# VERIFICAR RESULTADOS
# =========================================================

if not results_df.empty and "Score" in results_df.columns:
    
    # Ordenar por Score
    results_df = results_df.sort_values(by="Score", ascending=False)
    
    # Mostrar resultados
    print("\n" + "=" * 100)
    print(results_df)
    print("=" * 100)
    
    # Exportar Excel si está habilitado
    if EXPORT_EXCEL:
        with pd.ExcelWriter(EXCEL_NAME, engine="openpyxl") as writer:
            results_df.to_excel(
                writer,
                sheet_name="SmartMoney",
                index=False
            )
            
            # Auto-ajustar ancho de columnas
            worksheet = writer.sheets["SmartMoney"]
            for idx, col in enumerate(results_df.columns, 1):
                max_length = max(
                    len(str(val)) for val in results_df[col].astype(str)
                ) + 2
                worksheet.column_dimensions[
                    chr(64 + idx)
                ].width = min(max_length, 50)
        
        print("\n" + "=" * 80)
        print(f"✓ Excel exportado: {EXCEL_NAME}")
        print("=" * 80)

else:
    print("\n" + "=" * 80)
    print("✗ NO SE GENERARON RESULTADOS")
    print("Revisa: conexión, archivo de tickers o disponibilidad en Yahoo Finance")
    print("=" * 80)