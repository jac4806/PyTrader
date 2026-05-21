"""Smart Money stock screener with a PyQt6 user interface."""

#*******************************************************************
#
#               18/05/2026
#
#******************************************************************
import sys
import time
from datetime import datetime
from urllib.parse import quote_plus

from PyQt6 import uic
from PyQt6.QtGui import QDesktopServices, QTextCursor  # pylint: disable=no-name-in-module
from PyQt6.QtCore import (  # pylint: disable=no-name-in-module
    Qt,
    QEvent,
    QUrl,
    QThread,
    QTimer,
    pyqtSignal,
    QStringListModel,
)
from PyQt6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QMainWindow,
    QFileDialog,
    QTableWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QHeaderView,
    QTextEdit,
)

import numpy as np
import pandas as pd
import yfinance as yf
import io
import contextlib
from pathlib import Path

# =========================================================
# CONFIGURACIÓN
# =========================================================

PERIOD = "1y"
INTERVAL = "1d"

EXPORT_EXCEL = True
EXCEL_NAME = "SmartMoney_Screener.xlsx"
APP_DIR = Path(__file__).resolve().parent
UI_FILE = APP_DIR / "F_Trader_4.ui"

DELAY_BETWEEN_REQUESTS = 1
TXT_FILE = "Mi_Lista.txt"
MIN_SCORE_TO_DISPLAY = 60


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================


def download_data_safe(ticker, period="1y", interval="1d", max_retries=3):
    """
    Intenta descargar datos con yfinance. Si no se encuentran datos para el ticker
    sin sufijo de exchange, intenta añadir sufijos comunes de exchanges europeos
    para permitir analizar acciones de Europa.
    """
    # Sufijos comunes para exchanges europeos (se intentan si no vienen en el ticker)
    eu_suffixes = [
        ".MC", ".PA", ".L", ".DE", ".F", ".AS", ".MI", ".HE", ".ST",
        ".SW", ".OL", ".CO", ".BR", ".LS", ".VI",
    ]

    def try_download(sym):
        for attempt in range(max_retries):
            try:
                # Silenciar la salida de yfinance
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    stock_data = yf.download(
                        sym,
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
                    return None, None

                return stock_data, None

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None, f"Error después de {max_retries} intentos: {str(e)}"

    # 1) Intentar con el ticker tal cual
    data, err = try_download(ticker)
    if data is not None:
        return data, None

    # 2) Si el ticker no tiene sufijo (no contiene '.' ni ':'), probar sufijos EU
    if "." not in ticker and ":" not in ticker:
        for suf in eu_suffixes:
            sym = ticker + suf
            data, err = try_download(sym)
            if data is not None:
                return data, None

    # 3) Si el ticker tenía sufijo, intentar con el símbolo base sin sufijo
    if "." in ticker or ":" in ticker:
        base = ticker.split(".")[0].split(":")[0]
        if base != ticker:
            data, err = try_download(base)
            if data is not None:
                return data, None

    # 4) No se encontraron datos
    if err:
        return None, err
    return None, f"Sin datos disponibles para {ticker} (intentadas variaciones)"



def load_tickers(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        return []

    tickers = []

    for item in content.replace(";", ",").replace("\n", ",").split(","):
        item = item.strip()
        if not item:
            continue
        item = normalize_ticker(item)
        tickers.append(item)

    return [ticker for ticker in tickers if ticker]


def normalize_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker:
        return ""

    exchange_suffix_map = {
        "BME": ".MC",
        "BM": ".MC",
        "MC": ".MC",
        "EPA": ".PA",
        "PAR": ".PA",
        "LON": ".L",
        "LSE": ".L",
        "XETR": ".DE",
        "ETR": ".DE",
        "FRA": ".F",
        "MIL": ".MI",
        "BIT": ".MI",
        "AMS": ".AS",
        "HEL": ".HE",
        "STO": ".ST",
        "SWX": ".SW",
        "SIX": ".SW",
        "OSL": ".OL",
        "CPH": ".CO",
        "BRU": ".BR",
        "LIS": ".LS",
        "VIE": ".VI",
    }
    exchange_without_suffix = {"NASDAQ", "NYSE", "AMEX", "ARCA", "CBOE"}

    if ":" in ticker:
        exchange, symbol = ticker.split(":", 1)
        symbol = symbol.strip().replace(" ", "").replace("/", "-")
        if not symbol:
            return ""
        if exchange in exchange_suffix_map and "." not in symbol:
            return f"{symbol}{exchange_suffix_map[exchange]}"
        if exchange in exchange_without_suffix:
            return symbol
        return symbol

    return ticker.replace(" ", "").replace("/", "-")


def calculate_indicators(dataframe):
    """
    Calcula indicadores Smart Money, CFI, Flow, Tendencia y señales.
    """
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
                self.finished.emit(results)
                return

            self.progress.emit(f"Analizando {ticker}...")
            stock_data, error_msg = download_data_safe(ticker, period=PERIOD, interval=INTERVAL)

            if self._stop_requested:
                self.progress.emit("Análisis cancelado.")
                self.finished.emit(results)
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
        uic.loadUi(UI_FILE, self)

        self.E_Lista_model = QStringListModel()
        self.E_Lista.setModel(self.E_Lista_model)

        # Soportar dos tipos de widgets para E_Ticker: un view con modelo (QStringListModel)
        # o un QTextEdit (más simple y editable por defecto).
        self._ticker_is_model = False
        try:
            # Intentar usar como lista ligada a modelo
            self.E_Ticker_model = QStringListModel()
            self.E_Ticker.setModel(self.E_Ticker_model)
            self.E_Ticker.setSelectionMode(self.E_Ticker.SelectionMode.SingleSelection)
            self.E_Ticker.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
            self._ticker_is_model = True
        except Exception:
            # Si falla, tratamos E_Ticker como QTextEdit
            self.E_Ticker_model = None
            self._ticker_is_model = False
            if isinstance(self.E_Ticker, QTextEdit):
                # dejar el widget editable (por defecto ya lo es)
                self.E_Ticker.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        # Señal para suprimir efectos durante cambios programáticos
        self._suppress_e_ticker_edit_signal = False
        # Conectar señales para detectar edición del E_Ticker
        try:
            if self._ticker_is_model and self.E_Ticker_model is not None:
                self.E_Ticker_model.dataChanged.connect(self.on_e_ticker_edited)
                self.E_Ticker_model.rowsInserted.connect(self.on_e_ticker_edited)
                self.E_Ticker_model.rowsRemoved.connect(self.on_e_ticker_edited)
            else:
                if isinstance(self.E_Ticker, QTextEdit):
                    self.E_Ticker.textChanged.connect(self.on_e_ticker_edited)
        except Exception:
            pass

        self.E_Visor_model = QStringListModel()
        self.E_Visor.setModel(self.E_Visor_model)

        self.B_Lista.clicked.connect(self.on_b_lista)
        self.B_Carpeta.clicked.connect(self.on_b_carpeta)
        self.B_Ticker.clicked.connect(self.on_b_analizar)
        self.B_Cancelar.clicked.connect(self.on_b_cancelar)
        self.B_Borrar = getattr(self, "B_Borrar", None)
        if self.B_Borrar is None:
            self.B_Borrar = self.B_LimpiarResultados
        self.B_Borrar.setText("Borrar")
        self.B_Borrar.clicked.connect(self.on_b_clear_results)
        self.B_Salir.clicked.connect(self.close)
        self.C_Tiempo.toggled.connect(self.on_c_tiempo_toggled)
        self.E_Tiempo.textChanged.connect(self.on_e_tiempo_edited)

        self.E_Ticker.installEventFilter(self)
        self.E_Resultados.setSortingEnabled(True)
        self.E_Resultados.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.E_Resultados.cellDoubleClicked.connect(self.on_result_double_clicked)

        self.analysis_thread = None
        self.current_tickers = []
        self.loop_source_type = None
        self.loop_source_path = None
        self.loop_timer = QTimer(self)
        self.loop_timer.setSingleShot(True)
        self.loop_timer.timeout.connect(self.on_loop_timer_timeout)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_lcd_reloj)
        self.clock_timer.start(1000)
        self._suppress_e_tiempo_edit_signal = False
        self.cumulative_results = []
        self.analysis_clear_results = False
        self.analysis_replace_results = False
        self.lcd_Reloj.setDigitCount(8)
        self.set_table_headers([])
        self.update_lcd_reloj()

    def set_table_headers(self, headers):
        self.E_Resultados.setSortingEnabled(False)
        if not headers:
            self.E_Resultados.setColumnCount(0)
            self.E_Resultados.setRowCount(0)
            self.E_Resultados.setSortingEnabled(True)
            return
        self.E_Resultados.setColumnCount(len(headers))
        self.E_Resultados.setHorizontalHeaderLabels(headers)
        self.E_Resultados.setRowCount(0)
        # Ajustar tamaño de columnas al tamaño de la ventana
        try:
            header = self.E_Resultados.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            score_col = headers.index("Score")
            header.setSortIndicator(score_col, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass
        self.E_Resultados.setSortingEnabled(True)

    def clear_ticker_input(self):
        try:
            self._suppress_e_ticker_edit_signal = True
            if self._ticker_is_model and self.E_Ticker_model is not None:
                self.E_Ticker_model.setStringList([])
            elif isinstance(self.E_Ticker, QTextEdit):
                self.E_Ticker.clear()
        finally:
            self._suppress_e_ticker_edit_signal = False

    def _format_e_ticker_text(self, text):
        parts = [part.strip() for part in str(text).replace(";", ",").splitlines()]
        return ",".join(part for part in parts if part).upper()

    def _enforce_e_ticker_single_uppercase_line(self):
        if self._ticker_is_model and self.E_Ticker_model is not None:
            current_items = [
                self.E_Ticker_model.data(
                    self.E_Ticker_model.index(i, 0),
                    Qt.ItemDataRole.DisplayRole,
                )
                for i in range(self.E_Ticker_model.rowCount())
            ]
            current_text = "\n".join(str(item) for item in current_items if item)
            formatted_text = self._format_e_ticker_text(current_text)
            formatted_items = [formatted_text] if formatted_text else []
            if current_items != formatted_items:
                self._suppress_e_ticker_edit_signal = True
                try:
                    self.E_Ticker_model.setStringList(formatted_items)
                finally:
                    self._suppress_e_ticker_edit_signal = False
            return

        if isinstance(self.E_Ticker, QTextEdit):
            current_text = self.E_Ticker.toPlainText()
            formatted_text = self._format_e_ticker_text(current_text)
            if current_text != formatted_text:
                self._suppress_e_ticker_edit_signal = True
                try:
                    self.E_Ticker.setPlainText(formatted_text)
                    cursor = self.E_Ticker.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    self.E_Ticker.setTextCursor(cursor)
                finally:
                    self._suppress_e_ticker_edit_signal = False

    def _get_e_tiempo_text(self):
        if isinstance(self.E_Tiempo, QTextEdit):
            return self.E_Tiempo.toPlainText().strip()
        try:
            return self.E_Tiempo.text().strip()
        except Exception:
            return ""

    def _set_e_tiempo_text(self, text):
        if isinstance(self.E_Tiempo, QTextEdit):
            self.E_Tiempo.setPlainText(text)
            cursor = self.E_Tiempo.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.E_Tiempo.setTextCursor(cursor)
            return
        try:
            self.E_Tiempo.setText(text)
        except Exception:
            pass

    def _enforce_e_tiempo_numbers(self):
        current_text = self._get_e_tiempo_text()
        numeric_text = "".join(ch for ch in current_text if ch.isdigit())
        if current_text != numeric_text:
            self._suppress_e_tiempo_edit_signal = True
            try:
                self._set_e_tiempo_text(numeric_text)
            finally:
                self._suppress_e_tiempo_edit_signal = False

    def _get_loop_minutes(self, show_warning=False):
        self._enforce_e_tiempo_numbers()
        minutes_text = self._get_e_tiempo_text()
        if not minutes_text:
            if show_warning:
                QMessageBox.warning(
                    self,
                    "Tiempo no indicado",
                    "Introduce los minutos en E_Tiempo para activar el loop.",
                )
            return None

        minutes = int(minutes_text)
        if minutes <= 0:
            if show_warning:
                QMessageBox.warning(
                    self,
                    "Tiempo no válido",
                    "E_Tiempo debe ser mayor que 0 minutos.",
                )
            return None
        return minutes

    def _set_loop_source(self, source_type, source_path):
        self.loop_source_type = source_type
        self.loop_source_path = source_path

    def _stop_loop_timer(self):
        if self.loop_timer.isActive():
            self.loop_timer.stop()
        self.update_lcd_reloj()

    def _schedule_next_timed_analysis(self):
        if not self.C_Tiempo.isChecked():
            self._stop_loop_timer()
            return

        minutes = self._get_loop_minutes(show_warning=False)
        if not minutes or not self.loop_source_type or not self.loop_source_path:
            self._stop_loop_timer()
            return

        self.loop_timer.start(minutes * 60 * 1000)
        self.update_lcd_reloj()
        self.append_to_visor(f"Próximo análisis automático en {minutes} minutos.")

    def _format_countdown(self, milliseconds):
        total_seconds = max(0, (milliseconds + 999) // 1000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_lcd_reloj(self):
        if self.C_Tiempo.isChecked():
            remaining = self.loop_timer.remainingTime()
            if remaining > 0:
                self.lcd_Reloj.display(self._format_countdown(remaining))
            else:
                self.lcd_Reloj.display("00:00:00")
            return

        self.lcd_Reloj.display(datetime.now().strftime("%H:%M:%S"))

    def _load_folder_tickers(self, folder_path, log_files=False):
        txt_files = sorted(Path(folder_path).glob("*.txt"))
        if not txt_files:
            return []

        return self._load_list_tickers(txt_files, log_files=log_files)

    def _load_list_tickers(self, file_paths, log_files=False):
        all_tickers = []
        for file_path in file_paths:
            tickers = load_tickers(str(file_path))
            all_tickers.extend(tickers)
            if log_files:
                self.append_to_visor(
                    f"Cargando lista: {Path(file_path).name} ({len(tickers)} tickers)"
                )

        seen = set()
        unique_tickers = []
        for ticker in all_tickers:
            if ticker not in seen:
                seen.add(ticker)
                unique_tickers.append(ticker)
        return unique_tickers

    def _load_loop_tickers(self):
        if self.loop_source_type == "file":
            tickers = load_tickers(self.loop_source_path)
            if not tickers:
                self.append_to_visor("Loop detenido: la lista no contiene tickers válidos.")
                return []
            self.append_to_visor(f"Loop: recargando lista {self.loop_source_path}")
            return tickers

        if self.loop_source_type == "files":
            tickers = self._load_list_tickers(self.loop_source_path, log_files=True)
            if not tickers:
                self.append_to_visor("Loop detenido: las listas no contienen tickers válidos.")
                return []
            self.append_to_visor(f"Loop: recargando {len(self.loop_source_path)} listas")
            return tickers

        if self.loop_source_type == "folder":
            tickers = self._load_folder_tickers(self.loop_source_path)
            if not tickers:
                self.append_to_visor("Loop detenido: la carpeta no contiene tickers válidos.")
                return []
            self.append_to_visor(f"Loop: recargando carpeta {self.loop_source_path}")
            return tickers

        self.append_to_visor("Loop detenido: selecciona una lista o carpeta.")
        return []

    def eventFilter(self, source, event):
        if source is self.E_Ticker and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.on_b_analizar()
                return True
        return super().eventFilter(source, event)

    def append_to_visor(self, message):
        current = self.E_Visor_model.stringList()
        current.append(message)
        self.E_Visor_model.setStringList(current)
        self.E_Visor.scrollToBottom()

    def clear_visor(self):
        self.E_Visor_model.setStringList([])

    def on_b_lista(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar Archivos de Tickers",
            "",
            "Archivos TXT (*.txt)",
        )
        if not file_paths:
            return

        self.E_Lista_model.setStringList(file_paths)
        self.append_to_visor(f"Archivos seleccionados: {len(file_paths)}")

        tickers = self._load_list_tickers(file_paths, log_files=True)
        if not tickers:
            QMessageBox.warning(
                self,
                "Advertencia",
                "No se encontraron tickers en los archivos seleccionados.",
            )
            return

        self._set_loop_source("files", file_paths)
        self.current_tickers = tickers
        self.clear_ticker_input()
        self.start_analysis(tickers, clear_results=False)

    def get_selected_tracker(self):
        if self._ticker_is_model:
            selected_indexes = self.E_Ticker.selectionModel().selectedIndexes()
            if selected_indexes:
                return selected_indexes[0].data()
            if self.E_Ticker_model and self.E_Ticker_model.rowCount() > 0:
                return self.E_Ticker_model.data(
                    self.E_Ticker_model.index(0, 0),
                    Qt.ItemDataRole.DisplayRole,
                )
            return None
        else:
            text = self.E_Ticker.toPlainText().strip()
            if not text:
                return None
            # devolver la primera línea
            return text.splitlines()[0].strip()

    def parse_tickers_from_model(self):
        # Extrae y normaliza tickers desde el modelo editable de E_Ticker
        combined = []
        if self._ticker_is_model and self.E_Ticker_model:
            raw_items = [
                self.E_Ticker_model.data(
                    self.E_Ticker_model.index(i, 0),
                    Qt.ItemDataRole.DisplayRole,
                )
                for i in range(self.E_Ticker_model.rowCount())
            ]
            iterator = raw_items
        else:
            text = self.E_Ticker.toPlainText()
            # dividir en líneas
            iterator = [ln for ln in text.splitlines()]

        for it in iterator:
            if it is None:
                continue
            # dividir por comas, punto y coma
            parts = [p.strip() for p in str(it).replace(";", ",").split(",")]
            for p in parts:
                if not p:
                    continue
                p = normalize_ticker(p)
                if p:
                    combined.append(p)

        # eliminar duplicados preservando orden
        seen = set()
        result = []
        for t in combined:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def on_b_analizar(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(
                self,
                "Proceso en curso",
                "Ya hay un análisis en curso. Cancela antes de iniciar otro.",
            )
            return

        tickers = self.parse_tickers_from_model()
        if not tickers:
            QMessageBox.warning(self, "Sin tickers", "No hay tickers en E_Ticker para analizar.")
            return

        self.append_to_visor(f"Iniciando análisis para {len(tickers)} tickers...")
        self._set_loop_source(None, None)
        self.clear_ticker_input()
        self.start_analysis(tickers, clear_results=False)

    def start_analysis(self, tickers, clear_results=False, replace_results=False):
        self._stop_loop_timer()
        self.analysis_clear_results = clear_results
        self.analysis_replace_results = replace_results
        if clear_results:
            self.cumulative_results = []
            self.set_table_headers([])
        self.append_to_visor("Iniciando análisis...")

        self.B_Lista.setEnabled(False)
        self.B_Carpeta.setEnabled(False)
        self.B_Ticker.setEnabled(False)
        self.B_Cancelar.setEnabled(True)

        self.analysis_thread = AnalysisThread(tickers)
        self.analysis_thread.progress.connect(self.append_to_visor)
        self.analysis_thread.finished.connect(self.on_analysis_finished)
        self.analysis_thread.error.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_e_ticker_edited(self, *args, **kwargs):
        # Si el cambio fue programático, no borramos E_Lista
        if getattr(self, "_suppress_e_ticker_edit_signal", False):
            return
        self._enforce_e_ticker_single_uppercase_line()
        try:
            # Limpiar E_Lista (archivo seleccionado)
            if self.E_Lista_model is not None:
                self.E_Lista_model.setStringList([])
            self._set_loop_source(None, None)
            self._stop_loop_timer()
            # Limpiar visor y otras ventanas de texto
            try:
                self.clear_visor()
            except Exception:
                pass
        except Exception:
            pass

    def on_result_double_clicked(self, row, _column):
        ticker_col = None
        for col in range(self.E_Resultados.columnCount()):
            header_item = self.E_Resultados.horizontalHeaderItem(col)
            if header_item and header_item.text() == "Ticker":
                ticker_col = col
                break

        if ticker_col is None:
            return

        item = self.E_Resultados.item(row, ticker_col)
        if item is None:
            return

        ticker = item.text().strip()
        if not ticker:
            return

        url = QUrl(f"https://www.google.com/finance/beta/?hl=es&q={quote_plus(ticker)}")
        if not QDesktopServices.openUrl(url):
            self.append_to_visor(f"No se pudo abrir Google Finance para {ticker}.")

    def on_analysis_finished(self, results):
        self.append_to_visor("Análisis finalizado.")
        self.B_Lista.setEnabled(True)
        self.B_Carpeta.setEnabled(True)
        self.B_Ticker.setEnabled(True)
        self.B_Cancelar.setEnabled(False)
        self._schedule_next_timed_analysis()

        replace_results = self.analysis_replace_results
        self.analysis_replace_results = False

        if replace_results:
            self.cumulative_results = []

        if not results and not self.cumulative_results:
            if replace_results:
                self.set_table_headers([])
            self.append_to_visor("No se generaron resultados.")
            return

        filtered_results = [
            row
            for row in results
            if int(row.get("Score", 0)) > MIN_SCORE_TO_DISPLAY
        ]

        if filtered_results:
            self.cumulative_results.extend(filtered_results)

        if not self.cumulative_results:
            if replace_results:
                self.set_table_headers([])
            self.append_to_visor(
                f"No hay resultados con Score superior a {MIN_SCORE_TO_DISPLAY}."
            )
            return

        sorted_results = sorted(
            self.cumulative_results,
            key=lambda row: int(row.get("Score", 0)),
            reverse=True,
        )
        self.cumulative_results = sorted_results

        columns = list(sorted_results[0].keys())
        self.set_table_headers(columns)
        self.E_Resultados.setSortingEnabled(False)
        self.E_Resultados.setRowCount(len(sorted_results))
        numeric_columns = {"Precio", "Score", "Vol Relativo"}
        for row_idx, row_data in enumerate(sorted_results):
            for col_idx, header in enumerate(columns):
                value = row_data.get(header, "")
                item = QTableWidgetItem(str(value))
                if header in numeric_columns:
                    item.setData(Qt.ItemDataRole.EditRole, value)
                self.E_Resultados.setItem(row_idx, col_idx, item)
        self.E_Resultados.setSortingEnabled(True)
        self.E_Resultados.sortItems(columns.index("Score"), Qt.SortOrder.DescendingOrder)

        if EXPORT_EXCEL:
            df = pd.DataFrame(self.cumulative_results)
            try:
                df.to_excel(EXCEL_NAME, index=False)
                self.append_to_visor(f"Excel exportado: {EXCEL_NAME}")
            except Exception as exc:
                self.append_to_visor(f"Error exportando Excel: {exc}")

    def on_analysis_error(self, message):
        self.append_to_visor(message)

    def on_e_tiempo_edited(self):
        if getattr(self, "_suppress_e_tiempo_edit_signal", False):
            return
        self._enforce_e_tiempo_numbers()
        if self.C_Tiempo.isChecked() and not (
            self.analysis_thread and self.analysis_thread.isRunning()
        ):
            self._schedule_next_timed_analysis()
        self.update_lcd_reloj()

    def on_c_tiempo_toggled(self, checked):
        if not checked:
            self._stop_loop_timer()
            self.update_lcd_reloj()
            self.append_to_visor("Loop desactivado.")
            return

        if not self._get_loop_minutes(show_warning=True):
            self.C_Tiempo.setChecked(False)
            return

        if not self.loop_source_type or not self.loop_source_path:
            QMessageBox.warning(
                self,
                "Sin lista o carpeta",
                "Selecciona una lista o carpeta antes de activar el loop.",
            )
            self.C_Tiempo.setChecked(False)
            return

        self.append_to_visor("Loop activado.")
        if not (self.analysis_thread and self.analysis_thread.isRunning()):
            self._schedule_next_timed_analysis()
        self.update_lcd_reloj()

    def on_loop_timer_timeout(self):
        self.update_lcd_reloj()
        if not self.C_Tiempo.isChecked():
            return
        if self.analysis_thread and self.analysis_thread.isRunning():
            self._schedule_next_timed_analysis()
            return

        tickers = self._load_loop_tickers()
        if not tickers:
            self.C_Tiempo.setChecked(False)
            return

        self.current_tickers = tickers
        self.start_analysis(tickers, replace_results=True)

    def on_b_carpeta(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de listas")
        if not folder_path:
            return

        txt_files = sorted(Path(folder_path).glob("*.txt"))
        if not txt_files:
            QMessageBox.warning(
                self,
                "Advertencia",
                "No se encontraron archivos .txt en la carpeta seleccionada.",
            )
            return

        self.E_Lista_model.setStringList([folder_path])
        self.append_to_visor(f"Carpeta seleccionada: {folder_path}")

        unique_tickers = self._load_folder_tickers(folder_path, log_files=True)

        if not unique_tickers:
            QMessageBox.warning(
                self,
                "Advertencia",
                "No se encontraron tickers válidos en las listas de la carpeta.",
            )
            return

        self._set_loop_source("folder", folder_path)
        self.current_tickers = unique_tickers
        self.clear_ticker_input()
        self.start_analysis(unique_tickers, clear_results=False)

    def on_b_clear_results(self):
        self.cumulative_results = []
        self.set_table_headers([])
        self.append_to_visor("Ventana de resultados borrada.")

    def on_b_cancelar(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.request_stop()
            self.append_to_visor("Cancelando análisis...")
            self.B_Cancelar.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
