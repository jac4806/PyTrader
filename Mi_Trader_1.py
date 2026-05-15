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
TXT_FILE = "Magnificas.txt"

# =========================================================
# CARGAR TICKERS DESDE TXT
# =========================================================

with open(TXT_FILE, "r", encoding="utf-8") as file:

    content = file.read()

raw_tickers = content.split(",")

TICKERS = sorted(list(set(

    ticker
    .replace("NASDAQ:", "")
    .replace("NYSE:", "")
    .replace("AMEX:", "")
    .strip()

    for ticker in raw_tickers

    if ticker.strip()

)))

print("\n")
print("=" * 80)
print("TICKERS CARGADOS")
print("=" * 80)
print(TICKERS)
print("=" * 80)

# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================


def calculate_indicators(dataframe):
    """
    Calcula indicadores Smart Money,
    CFI, Flow, Tendencia y señales.
    """

    data = dataframe.copy()

    # =====================================================
    # CFI DIARIO
    # =====================================================

    data["cfi"] = (
        data["Volume"] *
        (data["Close"] - data["Open"])
    ).ewm(span=20, adjust=False).mean()

    data["cfi_ma"] = (
        data["cfi"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    data["cfi_up"] = (
        data["cfi"] > data["cfi_ma"]
    )

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

    weekly["cfi_w"] = (
        weekly["Volume"] *
        (weekly["Close"] - weekly["Open"])
    ).ewm(span=20, adjust=False).mean()

    weekly["cfi_w_ma"] = (
        weekly["cfi_w"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    weekly["cfi_w_up"] = (
        weekly["cfi_w"] >
        weekly["cfi_w_ma"]
    )

    data["cfi_w_up"] = (
        weekly["cfi_w_up"]
        .reindex(data.index, method="ffill")
    )

    # =====================================================
    # VOLUMEN
    # =====================================================

    data["vol_ma"] = (
        data["Volume"]
        .rolling(50)
        .mean()
    )

    data["vol_strong"] = (
        data["Volume"] >
        data["vol_ma"]
    )

    # =====================================================
    # FLOW / SMART MONEY
    # =====================================================

    spread = np.maximum(
        data["High"] - data["Low"],
        0.0001
    )

    data["close_pos"] = (
        (data["Close"] - data["Low"]) /
        spread
    )

    data["strength"] = (
        2 * data["close_pos"] - 1
    )

    data["flow"] = np.where(
        data["vol_strong"],
        data["strength"] * data["Volume"],
        0
    )

    data["flow_smooth"] = (
        data["flow"]
        .ewm(span=5, adjust=False)
        .mean()
    )

    # =====================================================
    # ACUMULACIÓN / DISTRIBUCIÓN
    # =====================================================

    data["accumulation"] = (
        (data["vol_strong"]) &
        (data["close_pos"] > 0.6) &
        (data["Close"] >= data["Open"])
    )

    data["distribution"] = (
        (data["vol_strong"]) &
        (data["close_pos"] < 0.4) &
        (data["Close"] <= data["Open"])
    )

    # =====================================================
    # TENDENCIA
    # =====================================================

    data["ema21"] = (
        data["Close"]
        .ewm(span=21, adjust=False)
        .mean()
    )

    data["sma50"] = (
        data["Close"]
        .rolling(50)
        .mean()
    )

    data["sma200"] = (
        data["Close"]
        .rolling(200)
        .mean()
    )

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
        (
            data["flow_smooth"].shift(5) >
            data["flow_smooth"].shift(10)
        )
    )

    data["bear_div"] = (
        (data["High"].shift(5) > data["High"].shift(10)) &
        (
            data["flow_smooth"].shift(5) <
            data["flow_smooth"].shift(10)
        )
    )

    # =====================================================
    # SEÑALES
    # =====================================================

    data["buy_pro"] = (
        data["trend_up"] &
        data["cfi_up"] &
        (
            (data["flow_smooth"] > 0) |
            (data["accumulation"])
        )
    )

    data["buy_early"] = (
        data["bull_div"] &
        (data["flow_smooth"] > 0)
    )

    data["sell"] = (
        data["distribution"] |
        data["bear_div"] |
        (data["flow_smooth"] < 0)
    )

    # =====================================================
    # LIMPIAR NaN BOOLEANOS
    # =====================================================

    bool_cols = [
        "cfi_up",
        "cfi_w_up",
        "vol_strong",
        "accumulation",
        "distribution",
        "trend_up",
        "bull_div",
        "bear_div",
        "buy_pro",
        "buy_early",
        "sell"
    ]

    for col in bool_cols:

        data[col] = data[col].fillna(False)

    # =====================================================
    # SCORE
    # =====================================================

    data["score"] = 0

    trend_mask = data["trend_up"]
    cfi_mask = data["cfi_up"]
    cfiw_mask = data["cfi_w_up"]
    acc_mask = data["accumulation"]
    flow_mask = (data["flow_smooth"] > 0).fillna(False)

    data.loc[trend_mask, "score"] += 25
    data.loc[cfi_mask, "score"] += 25
    data.loc[cfiw_mask, "score"] += 20
    data.loc[acc_mask, "score"] += 15
    data.loc[flow_mask, "score"] += 15

    # =====================================================
    # TEXTO SEÑAL
    # =====================================================

    conditions = [
        data["buy_pro"],
        data["buy_early"],
        data["sell"]
    ]

    choices = [
        "COMPRA FUERTE",
        "COMPRA TEMPRANA",
        "VENTA"
    ]

    data["signal"] = np.select(
        conditions,
        choices,
        default="ESPERA"
    )

    return data


# =========================================================
# ANALIZAR EMPRESAS
# =========================================================

results = []

for ticker in TICKERS:

    try:

        print(f"\nAnalizando {ticker}...")

        # =================================================
        # DESCARGAR DATOS
        # =================================================

        stock_data = yf.download(
            ticker,
            period=PERIOD,
            interval=INTERVAL,
            auto_adjust=True,
            progress=False,
            group_by="column"
        )

        # =================================================
        # CORREGIR MULTIINDEX
        # =================================================

        if isinstance(stock_data.columns, pd.MultiIndex):

            stock_data.columns = (
                stock_data.columns.get_level_values(0)
            )

        # =================================================
        # LIMPIAR DATOS
        # =================================================

        stock_data.dropna(inplace=True)

        if stock_data.empty:

            print(f"Sin datos para {ticker}")
            continue

        # =================================================
        # CALCULAR INDICADORES
        # =================================================

        stock_data = calculate_indicators(stock_data)

        # =================================================
        # ÚLTIMO REGISTRO
        # =================================================

        last = stock_data.iloc[-1]

        # =================================================
        # GUARDAR RESULTADOS
        # =================================================

        results.append({

            "Ticker": ticker,

            "Precio": round(
                float(last["Close"]),
                2
            ),

            "Signal": str(last["signal"]),

            "Score": int(last["score"]),

            "Trend": (
                "SI"
                if bool(last["trend_up"])
                else "NO"
            ),

            "CFI Diario": (
                "FUERTE"
                if bool(last["cfi_up"])
                else "DEBIL"
            ),

            "CFI Semanal": (
                "FUERTE"
                if bool(last["cfi_w_up"])
                else "DEBIL"
            ),

            "Flow": (
                "COMPRANDO"
                if float(last["flow_smooth"]) > 0
                else "VENDIENDO"
            ),

            "Smart Money": (

                "ACUMULANDO"

                if bool(last["accumulation"])

                else

                "DISTRIBUYENDO"

                if bool(last["distribution"])

                else

                "NEUTRO"
            ),

            "Vol Relativo": round(

                float(last["Volume"]) /
                float(last["vol_ma"]),

                2

            ) if float(last["vol_ma"]) > 0 else 0,

            "Fecha": datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )
        })

        print(f"{ticker} OK")

        # =================================================
        # RETRASO ENTRE CONSULTAS
        # =================================================

        time.sleep(DELAY_BETWEEN_REQUESTS)

    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError
    ) as error:

        print(f"\nERROR EN {ticker}")
        print(error)

# =========================================================
# CREAR DATAFRAME
# =========================================================

results_df = pd.DataFrame(results)

# =========================================================
# VERIFICAR RESULTADOS
# =========================================================

if not results_df.empty and "Score" in results_df.columns:

    # =====================================================
    # ORDENAR
    # =====================================================

    results_df = results_df.sort_values(
        by="Score",
        ascending=False
    )

    # =====================================================
    # MOSTRAR RESULTADOS
    # =====================================================

    print("\n")
    print("=" * 100)
    print(results_df)
    print("=" * 100)

    # =====================================================
    # EXPORTAR EXCEL
    # =====================================================

    if EXPORT_EXCEL:

        with pd.ExcelWriter(
            EXCEL_NAME,
            engine="openpyxl"
        ) as writer:

            results_df.to_excel(
                writer,
                sheet_name="SmartMoney",
                index=False
            )

            worksheet = writer.sheets["SmartMoney"]

            # =================================================
            # AJUSTAR ANCHO COLUMNAS
            # =================================================

            for column in worksheet.columns:

                max_length = 0

                column_letter = (
                    column[0].column_letter
                )

                for cell in column:

                    try:

                        if len(str(cell.value)) > max_length:

                            max_length = len(
                                str(cell.value)
                            )

                    except (
                        ValueError,
                        TypeError
                    ):
                        pass

                adjusted_width = max_length + 3

                worksheet.column_dimensions[
                    column_letter
                ].width = adjusted_width

        print("\n")
        print("=" * 80)
        print(f"Excel exportado: {EXCEL_NAME}")
        print("=" * 80)

else:

    print("\n")
    print("=" * 80)
    print("NO SE GENERARON RESULTADOS")
    print("Revisa conexión, tickers o Yahoo Finance")
    print("=" * 80)
    