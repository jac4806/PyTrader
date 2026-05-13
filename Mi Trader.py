# =========================================================
#   SMART MONEY / CFI SCREENER
#   Versión corregida y optimizada
# =========================================================

# =========================================================
# INSTALAR LIBRERÍAS
# =========================================================
#
# pip install yfinance pandas numpy openpyxl
#
# =========================================================

import yfinance as yf
import pandas as pd
import numpy as np

from datetime import datetime

# =========================================================
# CONFIGURACIÓN
# =========================================================

# =========================================================
# LEER TICKERS DESDE TXT
# =========================================================

with open("Magnificas.txt", "r") as file:

    content = file.read()

# Separar por comas
raw_tickers = content.split(",")

# Limpiar prefijos NASDAQ: / NYSE:
TICKERS = []

for ticker in raw_tickers:

    clean_ticker = (
        ticker
        .replace("NASDAQ:", "")
        .replace("NYSE:", "")
        .strip()
    )

    TICKERS.append(clean_ticker)

print("\nTICKERS CARGADOS:")
print(TICKERS)

PERIOD = "1y"
INTERVAL = "1d"

EXPORT_EXCEL = True
EXCEL_NAME = "SmartMoney_Screener.xlsx"

# =========================================================
# FUNCIÓN PRINCIPAL INDICADORES
# =========================================================

def calculate_indicators(dataframe):

    df = dataframe.copy()

    # =====================================================
    # CFI DIARIO
    # =====================================================

    df["cfi"] = (
        df["Volume"] *
        (df["Close"] - df["Open"])
    ).ewm(span=20, adjust=False).mean()

    df["cfi_ma"] = (
        df["cfi"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    df["cfi_up"] = (
        df["cfi"] > df["cfi_ma"]
    )

    # =====================================================
    # CFI SEMANAL
    # =====================================================

    weekly = df.resample("W").agg({
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

    # Reindexar semanal al diario
    df["cfi_w_up"] = (
        weekly["cfi_w_up"]
        .reindex(df.index, method="ffill")
    )

    # =====================================================
    # VOLUMEN
    # =====================================================

    df["vol_ma"] = (
        df["Volume"]
        .rolling(50)
        .mean()
    )

    df["vol_strong"] = (
        df["Volume"] >
        df["vol_ma"]
    )

    # =====================================================
    # FLOW / SMART MONEY
    # =====================================================

    spread = np.maximum(
        df["High"] - df["Low"],
        0.0001
    )

    df["close_pos"] = (
        (df["Close"] - df["Low"]) /
        spread
    )

    df["strength"] = (
        2 * df["close_pos"] - 1
    )

    df["flow"] = np.where(
        df["vol_strong"],
        df["strength"] * df["Volume"],
        0
    )

    df["flow_smooth"] = (
        df["flow"]
        .ewm(span=5, adjust=False)
        .mean()
    )

    # =====================================================
    # ACUMULACIÓN / DISTRIBUCIÓN
    # =====================================================

    df["accumulation"] = (
        (df["vol_strong"]) &
        (df["close_pos"] > 0.6) &
        (df["Close"] >= df["Open"])
    )

    df["distribution"] = (
        (df["vol_strong"]) &
        (df["close_pos"] < 0.4) &
        (df["Close"] <= df["Open"])
    )

    # =====================================================
    # TENDENCIA
    # =====================================================

    df["ema21"] = (
        df["Close"]
        .ewm(span=21, adjust=False)
        .mean()
    )

    df["sma50"] = (
        df["Close"]
        .rolling(50)
        .mean()
    )

    df["sma200"] = (
        df["Close"]
        .rolling(200)
        .mean()
    )

    df["trend_up"] = (
        (df["Close"] > df["ema21"]) &
        (df["ema21"] > df["sma50"]) &
        (df["sma50"] > df["sma200"])
    )

    # =====================================================
    # DIVERGENCIAS
    # =====================================================

    df["bull_div"] = (
        (df["Low"].shift(5) < df["Low"].shift(10)) &
        (
            df["flow_smooth"].shift(5) >
            df["flow_smooth"].shift(10)
        )
    )

    df["bear_div"] = (
        (df["High"].shift(5) > df["High"].shift(10)) &
        (
            df["flow_smooth"].shift(5) <
            df["flow_smooth"].shift(10)
        )
    )

    # =====================================================
    # SEÑALES
    # =====================================================

    df["buy_pro"] = (
        df["trend_up"] &
        df["cfi_up"] &
        (
            (df["flow_smooth"] > 0) |
            (df["accumulation"])
        )
    )

    df["buy_early"] = (
        df["bull_div"] &
        (df["flow_smooth"] > 0)
    )

    df["sell"] = (
        df["distribution"] |
        df["bear_div"] |
        (df["flow_smooth"] < 0)
    )

    # =====================================================
    # SCORE
    # =====================================================

    df["score"] = 0

    trend_mask = df["trend_up"].fillna(False)
    cfi_mask = df["cfi_up"].fillna(False)
    cfiw_mask = df["cfi_w_up"].fillna(False)
    acc_mask = df["accumulation"].fillna(False)
    flow_mask = (df["flow_smooth"] > 0).fillna(False)

    df.loc[trend_mask, "score"] += 25
    df.loc[cfi_mask, "score"] += 25
    df.loc[cfiw_mask, "score"] += 20
    df.loc[acc_mask, "score"] += 15
    df.loc[flow_mask, "score"] += 15

    # =====================================================
    # TEXTO SEÑAL
    # =====================================================

    conditions = [
    df["buy_pro"].fillna(False),
    df["buy_early"].fillna(False),
    df["sell"].fillna(False)
    ]

    choices = [
        "COMPRA FUERTE",
        "COMPRA TEMPRANA",
        "VENTA"
    ]

    df["signal"] = np.select(
        conditions,
        choices,
        default="ESPERA"
    )

    # Limpiar NaN finales
    df = df.fillna(False)
    
    return df

# =========================================================
# ANALIZAR EMPRESAS
# =========================================================

results = []

for ticker in TICKERS:

    try:

        print(f"\nAnalizando {ticker}...")

        # =================================================
        # DESCARGA DATOS
        # =================================================

        df = yf.download(
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

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # =================================================
        # LIMPIEZA
        # =================================================

        df.dropna(inplace=True)

        if df.empty:
            print(f"Sin datos para {ticker}")
            continue

        # =================================================
        # CALCULAR INDICADORES
        # =================================================

        df = calculate_indicators(df)

        # =================================================
        # ÚLTIMA FILA
        # =================================================

        last = df.iloc[-1]

        # =================================================
        # RESULTADOS
        # =================================================

        results.append({

            "Ticker": ticker,

            "Precio": round(float(last["Close"]), 2),

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

    except Exception as e:

        print(f"\nERROR EN {ticker}")
        print(e)

# =========================================================
# DATAFRAME RESULTADOS
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
    # MOSTRAR
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

            workbook = writer.book
            worksheet = writer.sheets["SmartMoney"]

            # =============================================
            # AJUSTAR COLUMNAS
            # =============================================

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

                    except:
                        pass

                adjusted_width = max_length + 3

                worksheet.column_dimensions[
                    column_letter
                ].width = adjusted_width

        print("\n")
        print(f"Excel exportado: {EXCEL_NAME}")

else:

    print("\nNo se generaron resultados.")
    print("Revisa los tickers o conexión.")
    
