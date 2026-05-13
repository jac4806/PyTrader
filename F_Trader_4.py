import sys
import time
from datetime import datetime

from PyQt6 import uic
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QStringListModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QTableWidgetItem,
    QMessageBox,
)

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

DELAY_BETWEEN_REQUESTS = 1
TXT_FILE = "Mi_Lista.txt"


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================


def download_data_safe(ticker, period="1y", interval="1d", max_retries=3):
    for attempt in range(max_retries):
        try:
            stock_data = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                group_by="column",
            )

            if isinstance(stock_data.columns, pd.MultiIndex):
                stock_data.columns = stock_data.columns.get_level_values(0)

            stock_data.dropna(inplace=True)
            if stock_data.empty:
                return None, f"Sin datos disponibles para {ticker}"

            return stock_data, None

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None, f"Error después de {max_retries} intentos: {str(e)}"



def load_tickers(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        return []

    prefixes = ["NASDAQ:", "NYSE:", "AMEX:"]
    tickers = []

    for item in content.split(","):
        item = item.strip()
        if not item:
            continue
        for prefix in prefixes:
            item = item.replace(prefix, "")
        item = item.upper().replace(":", ".")
        tickers.append(item)

    return [ticker for ticker in tickers if ticker]



def calculate_indicators(dataframe):
    data = dataframe.copy()

    cfi_raw = data["Volume"] * (data["Close"] - data["Open"])
    data["cfi"] = cfi_raw.ewm(span=20, adjust=False).mean()
    data["cfi_ma"] = data["cfi"].ewm(span=20, adjust=False).mean()
    data["cfi_up"] = data["cfi"] > data["cfi_ma"]

    weekly = data.resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    })
    weekly_cfi_raw = weekly["Volume"] * (weekly["Close"] - weekly["Open"])
    weekly["cfi_w"] = weekly_cfi_raw.ewm(span=20, adjust=False).mean()
    weekly["cfi_w_ma"] = weekly["cfi_w"].ewm(span=20, adjust=False).mean()
    weekly["cfi_w_up"] = weekly["cfi_w"] > weekly["cfi_w_ma"]
    data["cfi_w_up"] = weekly["cfi_w_up"].reindex(data.index, fill_value=False).ffill()

    data["vol_ma"] = data["Volume"].rolling(50).mean()
    data["vol_strong"] = data["Volume"] > data["vol_ma"]

    spread = np.maximum(data["High"] - data["Low"], 0.0001)
    data["close_pos"] = (data["Close"] - data["Low"]) / spread
    data["strength"] = 2 * data["close_pos"] - 1
    data["flow"] = np.where(data["vol_strong"], data["strength"] * data["Volume"], 0)
    data["flow_smooth"] = data["flow"].ewm(span=5, adjust=False).mean()

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

    data["ema21"] = data["Close"].ewm(span=21, adjust=False).mean()
    data["sma50"] = data["Close"].rolling(50).mean()
    data["sma200"] = data["Close"].rolling(200).mean()
    data["trend_up"] = (
        (data["Close"] > data["ema21"]) &
        (data["ema21"] > data["sma50"]) &
        (data["sma50"] > data["sma200"])
    )

    data["bull_div"] = (
        (data["Low"].shift(5) < data["Low"].shift(10)) &
        (data["flow_smooth"].shift(5) > data["flow_smooth"].shift(10))
    )
    data["bear_div"] = (
        (data["High"].shift(5) > data["High"].shift(10)) &
        (data["flow_smooth"].shift(5) < data["flow_smooth"].shift(10))
    )

    data["buy_pro"] = (
        data["trend_up"] &
        data["cfi_up"] &
        ((data["flow_smooth"] > 0) | data["accumulation"])
    )
    data["buy_early"] = data["bull_div"] & (data["flow_smooth"] > 0)
    data["sell"] = data["distribution"] | data["bear_div"] | (data["flow_smooth"] < 0)

    bool_cols = [
        "cfi_up", "cfi_w_up", "vol_strong", "accumulation",
        "distribution", "trend_up", "bull_div", "bear_div",
        "buy_pro", "buy_early", "sell",
    ]
    data[bool_cols] = data[bool_cols].fillna(False)

    data["score"] = (
        (data["trend_up"].astype(int) * 25) +
        (data["cfi_up"].astype(int) * 25) +
        (data["cfi_w_up"].astype(int) * 20) +
        (data["accumulation"].astype(int) * 15) +
        ((data["flow_smooth"] > 0).astype(int) * 15)
    )

    conditions = [data["buy_pro"], data["buy_early"], data["sell"]]
    choices = ["COMPRA FUERTE", "COMPRA TEMPRANA", "VENTA"]
    data["signal"] = np.select(conditions, choices, default="ESPERA")

    return data


class AnalysisThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, tickers):
        super().__init__()
        self.tickers = tickers
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        results = []
        for ticker in self.tickers:
            if self._stop_requested:
                self.progress.emit("Análisis cancelado.")
                return

            self.progress.emit(f"Analizando {ticker}...")
            stock_data, error_msg = download_data_safe(ticker, period=PERIOD, interval=INTERVAL)

            if self._stop_requested:
                self.progress.emit("Análisis cancelado.")
                return

            if stock_data is None:
                self.progress.emit(error_msg)
                continue

            try:
                stock_data = calculate_indicators(stock_data)
                last = stock_data.iloc[-1]
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
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
            except Exception as exc:
                self.progress.emit(f"Error procesando {ticker}: {exc}")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.finished.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("F_Trader_4.ui", self)

        self.E_Lista_model = QStringListModel()
        self.E_Lista.setModel(self.E_Lista_model)

        self.E_Tracker_model = QStringListModel()
        self.E_Tracker.setModel(self.E_Tracker_model)
        self.E_Tracker.setSelectionMode(self.E_Tracker.SelectionMode.SingleSelection)

        self.E_Visor_model = QStringListModel()
        self.E_Visor.setModel(self.E_Visor_model)

        self.B_Lista.clicked.connect(self.on_b_lista)
        self.B_Analizar.clicked.connect(self.on_b_analizar)
        self.B_Cancelar.clicked.connect(self.on_b_cancelar)
        self.B_Salir.clicked.connect(self.close)

        self.analysis_thread = None
        self.current_tickers = []
        self.set_table_headers([])

    def set_table_headers(self, headers):
        if not headers:
            self.E_Resultados.setColumnCount(0)
            self.E_Resultados.setRowCount(0)
            return
        self.E_Resultados.setColumnCount(len(headers))
        self.E_Resultados.setHorizontalHeaderLabels(headers)
        self.E_Resultados.setRowCount(0)

    def append_to_visor(self, message):
        current = self.E_Visor_model.stringList()
        current.append(message)
        self.E_Visor_model.setStringList(current)
        self.E_Visor.scrollToBottom()

    def clear_visor(self):
        self.E_Visor_model.setStringList([])

    def on_b_lista(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo de Tickers", "", "Archivos TXT (*.txt)")
        if not file_path:
            return

        self.E_Lista_model.setStringList([file_path])
        self.append_to_visor(f"Archivo seleccionado: {file_path}")

        tickers = load_tickers(file_path)
        if not tickers:
            QMessageBox.warning(self, "Advertencia", "No se encontraron tickers en el archivo.")
            return

        self.current_tickers = tickers
        self.E_Tracker_model.setStringList(tickers)
        self.E_Tracker.setCurrentIndex(self.E_Tracker_model.index(0, 0))

        self.start_analysis(tickers)

    def get_selected_tracker(self):
        selected_indexes = self.E_Tracker.selectionModel().selectedIndexes()
        if selected_indexes:
            return selected_indexes[0].data()
        if self.E_Tracker_model.rowCount() > 0:
            return self.E_Tracker_model.data(self.E_Tracker_model.index(0, 0), Qt.ItemDataRole.DisplayRole)
        return None

    def on_b_analizar(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un análisis en curso. Cancela antes de iniciar otro.")
            return

        ticker = self.get_selected_tracker()
        if not ticker:
            QMessageBox.warning(self, "Sin ticker", "No hay ningún ticker seleccionado en E_Tracker.")
            return

        self.append_to_visor(f"Iniciando análisis para {ticker}...")
        self.start_analysis([ticker])

    def start_analysis(self, tickers):
        self.clear_visor()
        self.append_to_visor("Iniciando análisis...")
        self.B_Lista.setEnabled(False)
        self.B_Analizar.setEnabled(False)
        self.B_Cancelar.setEnabled(True)
        self.set_table_headers([])
        self.analysis_thread = AnalysisThread(tickers)
        self.analysis_thread.progress.connect(self.append_to_visor)
        self.analysis_thread.finished.connect(self.on_analysis_finished)
        self.analysis_thread.error.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_analysis_finished(self, results):
        self.append_to_visor("Análisis finalizado.")
        self.B_Lista.setEnabled(True)
        self.B_Analizar.setEnabled(True)
        self.B_Cancelar.setEnabled(False)

        if not results:
            self.append_to_visor("No se generaron resultados.")
            return

        columns = list(results[0].keys())
        self.set_table_headers(columns)
        self.E_Resultados.setRowCount(len(results))
        for row_idx, row_data in enumerate(results):
            for col_idx, header in enumerate(columns):
                item = QTableWidgetItem(str(row_data[header]))
                self.E_Resultados.setItem(row_idx, col_idx, item)

        if EXPORT_EXCEL:
            df = pd.DataFrame(results)
            try:
                df.to_excel(EXCEL_NAME, index=False)
                self.append_to_visor(f"Excel exportado: {EXCEL_NAME}")
            except Exception as exc:
                self.append_to_visor(f"Error exportando Excel: {exc}")

    def on_analysis_error(self, message):
        self.append_to_visor(message)

    def on_b_cancelar(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.request_stop()
            self.analysis_thread.terminate()
            self.analysis_thread.wait(1000)
            self.append_to_visor("Se solicitó cancelar el análisis.")
            self.B_Lista.setEnabled(True)
            self.B_Analizar.setEnabled(True)
            self.B_Cancelar.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
