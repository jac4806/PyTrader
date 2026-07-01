#*******************************************************************
#
#             16/06/2026
#
##******************************************************************
import sys
import time
import os
import smtplib
from datetime import datetime, time as dt_time
from email.message import EmailMessage
from urllib.parse import quote_plus

from PyQt6 import uic
from PyQt6.QtCore import (  # pylint: disable=no-name-in-module
    Qt,
    QEvent,
    QUrl,
    QThread,
    QTimer,
    QTime,
    QSettings,
    pyqtSignal,
    QStringListModel,
)
from PyQt6.QtGui import (  # pylint: disable=no-name-in-module
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QTextCursor,
)
from PyQt6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QMainWindow,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QTableWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QHeaderView,
    QTextEdit,
    QFormLayout,
    QVBoxLayout,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QTimeEdit,
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


def load_env_file(path):
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(APP_DIR / ".env")


def resource_path(filename):
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / filename  # pylint: disable=protected-access
    return APP_DIR / filename


UI_FILE = resource_path("F_Trader_4.ui")

DELAY_BETWEEN_REQUESTS = 1
TXT_FILE = "Mi_Lista.txt"
MIN_SCORE_TO_DISPLAY = 60
DEFAULT_RESULT_HEADERS = [
    "Ticker",
    "Precio",
    "Signal",
    "Score",
    "Trend",
    "CFI Diario",
    "CFI Semanal",
    "Flow",
    "Smart Money",
    "Vol Relativo",
    "Fecha",
]
EMAIL_RESULTS_TO = "titogilito64@gmail.com"
EMAIL_MIN_SCORE = 80
SMTP_HOST = os.getenv("PYTRADER_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("PYTRADER_SMTP_PORT", "587"))
SMTP_USER = os.getenv("PYTRADER_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("PYTRADER_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("PYTRADER_SMTP_FROM", "") or SMTP_USER
SMTP_USE_TLS = os.getenv("PYTRADER_SMTP_TLS", "1") != "0"
EUROPE_MARKET_START = dt_time(9, 30)
EUROPE_MARKET_END = dt_time(17, 0)
US_MARKET_START = dt_time(15, 30)
US_MARKET_END = dt_time(22, 0)
LOOP_ACTIVE_START = dt_time(10, 0)
LOOP_ACTIVE_END = dt_time(21, 0)

DEFAULT_APP_OPTIONS = {
    "period": PERIOD,
    "interval": INTERVAL,
    "delay_between_requests": DELAY_BETWEEN_REQUESTS,
    "export_excel": EXPORT_EXCEL,
    "excel_name": EXCEL_NAME,
    "min_score_to_display": MIN_SCORE_TO_DISPLAY,
    "email_min_score": EMAIL_MIN_SCORE,
    "email_results_to": EMAIL_RESULTS_TO,
    "europe_market_start": EUROPE_MARKET_START,
    "europe_market_end": EUROPE_MARKET_END,
    "us_market_start": US_MARKET_START,
    "us_market_end": US_MARKET_END,
    "loop_active_start": LOOP_ACTIVE_START,
    "loop_active_end": LOOP_ACTIVE_END,
}


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
        ".SW", ".OL", ".CO", ".BR", ".LS", ".VI", ".AX",
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


def build_high_score_email_body(results):
    lines = [
        "Resultados del analisis Smart Money con Score igual o superior a "
        f"{EMAIL_MIN_SCORE}:",
        "",
    ]

    for row in results:
        lines.append(
            " | ".join(
                [
                    f"Ticker: {row.get('Ticker', '')}",
                    f"Score: {row.get('Score', '')}",
                    f"Precio: {row.get('Precio', '')}",
                    f"Signal: {row.get('Signal', '')}",
                    f"Trend: {row.get('Trend', '')}",
                    f"CFI Diario: {row.get('CFI Diario', '')}",
                    f"CFI Semanal: {row.get('CFI Semanal', '')}",
                    f"Flow: {row.get('Flow', '')}",
                    f"Smart Money: {row.get('Smart Money', '')}",
                ]
            )
        )

    return "\n".join(lines)


def send_high_score_email(results):
    if not results:
        return (
            False,
            f"No hay resultados con Score igual o superior a {EMAIL_MIN_SCORE} para enviar.",
        )

    missing = []
    if not SMTP_HOST:
        missing.append("PYTRADER_SMTP_HOST")
    if not SMTP_USER:
        missing.append("PYTRADER_SMTP_USER")
    if not SMTP_PASSWORD:
        missing.append("PYTRADER_SMTP_PASSWORD")

    if missing:
        return (
            False,
            "Correo no enviado: faltan variables SMTP "
            + ", ".join(missing)
            + ". Crea un archivo .env desde .env.example o define esas variables en el sistema.",
        )

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = EMAIL_RESULTS_TO
    message["Subject"] = (
        f"PyTrader: {len(results)} resultados con Score >= {EMAIL_MIN_SCORE}"
    )
    message.set_content(build_high_score_email_body(results))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)

    return True, f"Correo enviado a {EMAIL_RESULTS_TO} con {len(results)} resultados."


def time_to_text(value):
    return value.strftime("%H:%M")


def text_to_time(value, fallback):
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except (TypeError, ValueError):
        return fallback


def qt_time_from_python(value):
    return QTime(value.hour, value.minute, value.second)


def python_time_from_qt(value):
    return dt_time(value.hour(), value.minute(), value.second())


class OptionsDialog(QDialog):
    option_changed = pyqtSignal(object)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opciones")
        self.setModal(True)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

        self.period = QComboBox()
        self.period.addItems(["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"])
        self.period.setEditable(True)

        self.interval = QComboBox()
        self.interval.addItems(["1d", "5d", "1wk", "1mo"])
        self.interval.setEditable(True)

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 60)
        self.delay.setDecimals(1)
        self.delay.setSuffix(" s")

        self.export_excel = QCheckBox()
        self.excel_name = QLineEdit()

        self.min_score_table = QSpinBox()
        self.min_score_table.setRange(0, 100)

        self.min_score_email = QSpinBox()
        self.min_score_email.setRange(0, 100)

        self.email_to = QLineEdit()

        self.loop_start = QTimeEdit()
        self.loop_end = QTimeEdit()
        for widget in (self.loop_start, self.loop_end):
            widget.setDisplayFormat("HH:mm")

        form = QFormLayout()
        form.addRow("Periodo de datos", self.period)
        form.addRow("Intervalo de datos", self.interval)
        form.addRow("Espera entre tickers", self.delay)
        form.addRow("Exportar Excel", self.export_excel)
        form.addRow("Nombre Excel", self.excel_name)
        form.addRow("Score minimo en tabla", self.min_score_table)
        form.addRow("Score minimo para email", self.min_score_email)
        form.addRow("Email resultados", self.email_to)
        form.addRow("Loop activo inicio", self.loop_start)
        form.addRow("Loop activo fin", self.loop_end)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(
            QDialogButtonBox.StandardButton.RestoreDefaults
        ).clicked.connect(self.restore_defaults)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.buttons)
        self.setLayout(layout)
        self.set_options(options)
        self._connect_immediate_updates()

    def _connect_immediate_updates(self):
        for widget in (self.period, self.interval):
            widget.currentTextChanged.connect(self._emit_options_changed)
        self.delay.valueChanged.connect(self._emit_options_changed)
        self.export_excel.toggled.connect(self._emit_options_changed)
        self.excel_name.textChanged.connect(self._emit_options_changed)
        self.min_score_table.valueChanged.connect(self._emit_options_changed)
        self.min_score_email.valueChanged.connect(self._emit_options_changed)
        self.email_to.textChanged.connect(self._emit_options_changed)
        self.loop_start.timeChanged.connect(self._emit_options_changed)
        self.loop_end.timeChanged.connect(self._emit_options_changed)

    def _emit_options_changed(self):
        self.option_changed.emit(self.options())

    def restore_defaults(self):
        self.set_options(DEFAULT_APP_OPTIONS)
        self._emit_options_changed()

    def set_options(self, options):
        self.period.setCurrentText(str(options["period"]))
        self.interval.setCurrentText(str(options["interval"]))
        self.delay.setValue(float(options["delay_between_requests"]))
        self.export_excel.setChecked(bool(options["export_excel"]))
        self.excel_name.setText(str(options["excel_name"]))
        self.min_score_table.setValue(int(options["min_score_to_display"]))
        self.min_score_email.setValue(int(options["email_min_score"]))
        self.email_to.setText(str(options["email_results_to"]))
        self.loop_start.setTime(qt_time_from_python(options["loop_active_start"]))
        self.loop_end.setTime(qt_time_from_python(options["loop_active_end"]))

    def options(self):
        return {
            "period": self.period.currentText().strip() or DEFAULT_APP_OPTIONS["period"],
            "interval": self.interval.currentText().strip() or DEFAULT_APP_OPTIONS["interval"],
            "delay_between_requests": self.delay.value(),
            "export_excel": self.export_excel.isChecked(),
            "excel_name": self.excel_name.text().strip() or DEFAULT_APP_OPTIONS["excel_name"],
            "min_score_to_display": self.min_score_table.value(),
            "email_min_score": self.min_score_email.value(),
            "email_results_to": self.email_to.text().strip(),
            "europe_market_start": DEFAULT_APP_OPTIONS["europe_market_start"],
            "europe_market_end": DEFAULT_APP_OPTIONS["europe_market_end"],
            "us_market_start": DEFAULT_APP_OPTIONS["us_market_start"],
            "us_market_end": DEFAULT_APP_OPTIONS["us_market_end"],
            "loop_active_start": python_time_from_qt(self.loop_start.time()),
            "loop_active_end": python_time_from_qt(self.loop_end.time()),
        }


class AnalysisThread(QThread):
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(object)
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
                result = {
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
                }
                results.append(result)
                self.result_ready.emit(result)
            except Exception as exc:
                self.progress.emit(f"Error procesando {ticker}: {exc}")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.finished.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(UI_FILE, self)
        self.apply_visual_style()
        self.settings = QSettings("PyTrader", "PyTrader")
        self.app_options = self.load_app_options()
        self.apply_app_options(self.app_options, save=False)
        self.setup_options_menu()

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
        self.E_Resultados.setAlternatingRowColors(True)
        self.E_Resultados.setShowGrid(False)
        self.E_Resultados.verticalHeader().setVisible(False)
        self.E_Resultados.verticalHeader().setDefaultSectionSize(30)
        self.E_Lista.setAlternatingRowColors(True)
        self.E_Visor.setAlternatingRowColors(True)

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
        self.analysis_show_current_results = False
        self._loop_market_close_handled = False
        self.lcd_Reloj.setDigitCount(8)
        if hasattr(self, "lcd_Loop"):
            self.lcd_Loop.setDigitCount(8)
        self.set_table_headers([])
        self.update_lcd_reloj()
        self.update_market_progress_bars()

    def apply_visual_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget#centralwidget {
                background-color: #f3f6f8;
                color: #17212b;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 10pt;
            }

            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #d6dde4;
                padding: 3px 8px;
            }

            QMenuBar::item {
                background: transparent;
                padding: 5px 10px;
                border-radius: 4px;
            }

            QMenuBar::item:selected {
                background-color: #e8eef4;
            }

            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd4dd;
                padding: 4px;
            }

            QMenu::item {
                padding: 6px 28px 6px 12px;
            }

            QMenu::item:selected {
                background-color: #e5f0f8;
                color: #0f3b57;
            }

            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #cbd6df;
                border-radius: 7px;
                margin-top: 15px;
                font-weight: 600;
                color: #243442;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 7px;
                color: #0f5f87;
                background-color: #f3f6f8;
            }

            QPushButton {
                background-color: #176b8f;
                color: #ffffff;
                border: 1px solid #145a78;
                border-radius: 6px;
                padding: 7px 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #1e7fa8;
            }

            QPushButton:pressed {
                background-color: #11506c;
            }

            QPushButton:disabled {
                background-color: #b8c3cb;
                border-color: #aab5bd;
                color: #f2f4f5;
            }

            QPushButton#B_LimpiarResultados {
                background-color: #5b6670;
                border-color: #4d5962;
            }

            QPushButton#B_Cancelar {
                background-color: #b85252;
                border-color: #964141;
            }

            QPushButton#B_Salir {
                background-color: #34404a;
                border-color: #2b353d;
            }

            QPushButton#B_Lista,
            QPushButton#B_Carpeta {
                background-color: #eef4f8;
                color: #17364a;
                border-color: #b7c7d2;
                padding: 0;
            }

            QTextEdit, QListView, QTableWidget, QLineEdit, QComboBox, QSpinBox,
            QDoubleSpinBox, QTimeEdit {
                background-color: #fbfdff;
                border: 1px solid #c5d0d9;
                border-radius: 5px;
                selection-background-color: #cfe7f5;
                selection-color: #102433;
            }

            QTextEdit:focus, QListView:focus, QTableWidget:focus, QLineEdit:focus,
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {
                border: 1px solid #2687b2;
            }

            QListView::item {
                min-height: 24px;
                padding: 3px 7px;
            }

            QListView::item:alternate, QTableWidget {
                alternate-background-color: #f5f9fc;
            }

            QListView::item:selected {
                background-color: #d6edf7;
                color: #0d3349;
            }

            QTableWidget {
                gridline-color: #d9e2e9;
                border-radius: 6px;
            }

            QTableWidget::item {
                padding: 5px 7px;
                border-bottom: 1px solid #edf1f4;
            }

            QTableWidget::item:selected {
                background-color: #cfe7f5;
                color: #102433;
            }

            QHeaderView::section {
                background-color: #20313f;
                color: #ffffff;
                border: 0;
                border-right: 1px solid #344858;
                padding: 8px 7px;
                font-weight: 600;
            }

            QProgressBar {
                background-color: #dfe7ed;
                border: 1px solid #c3cdd6;
                border-radius: 6px;
                text-align: center;
                color: #243442;
                font-weight: 600;
            }

            QProgressBar::chunk {
                background-color: #2d9c72;
                border-radius: 5px;
            }

            QProgressBar#P_MercadoAmericano::chunk {
                background-color: #e29b39;
            }

            QLCDNumber {
                background-color: #18232e;
                color: #bdefff;
                border: 1px solid #0d151c;
                border-radius: 6px;
            }

            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid #9fb0bd;
                border-radius: 4px;
                background-color: #ffffff;
            }

            QCheckBox::indicator:checked {
                background-color: #176b8f;
                border-color: #176b8f;
            }

            QLabel {
                color: #2d3e4b;
                font-weight: 600;
            }
            """
        )

    def setup_options_menu(self):
        self.action_configurar_opciones = QAction("Configurar...", self)
        self.action_configurar_opciones.triggered.connect(self.on_configure_options)
        self.menuOpciones.addAction(self.action_configurar_opciones)

    def load_app_options(self):
        options = DEFAULT_APP_OPTIONS.copy()
        options["period"] = self.settings.value("period", options["period"])
        options["interval"] = self.settings.value("interval", options["interval"])
        options["delay_between_requests"] = float(
            self.settings.value(
                "delay_between_requests",
                options["delay_between_requests"],
            )
        )
        options["export_excel"] = self._settings_bool(
            "export_excel",
            options["export_excel"],
        )
        options["excel_name"] = self.settings.value("excel_name", options["excel_name"])
        options["min_score_to_display"] = int(
            self.settings.value(
                "min_score_to_display",
                options["min_score_to_display"],
            )
        )
        options["email_min_score"] = int(
            self.settings.value("email_min_score", options["email_min_score"])
        )
        options["email_results_to"] = self.settings.value(
            "email_results_to",
            options["email_results_to"],
        )

        for key in (
            "loop_active_start",
            "loop_active_end",
        ):
            options[key] = text_to_time(
                self.settings.value(key, time_to_text(options[key])),
                DEFAULT_APP_OPTIONS[key],
            )
        return options

    def _settings_bool(self, key, default):
        value = self.settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "si", "sí"}

    def save_app_options(self, options):
        for key, value in options.items():
            if isinstance(value, dt_time):
                self.settings.setValue(key, time_to_text(value))
            else:
                self.settings.setValue(key, value)
        self.settings.sync()

    def apply_app_options(self, options, save=True):
        global PERIOD, INTERVAL, DELAY_BETWEEN_REQUESTS, EXPORT_EXCEL, EXCEL_NAME
        global MIN_SCORE_TO_DISPLAY, EMAIL_MIN_SCORE, EMAIL_RESULTS_TO
        global EUROPE_MARKET_START, EUROPE_MARKET_END, US_MARKET_START, US_MARKET_END
        global LOOP_ACTIVE_START, LOOP_ACTIVE_END

        PERIOD = str(options["period"])
        INTERVAL = str(options["interval"])
        DELAY_BETWEEN_REQUESTS = float(options["delay_between_requests"])
        EXPORT_EXCEL = bool(options["export_excel"])
        EXCEL_NAME = str(options["excel_name"])
        MIN_SCORE_TO_DISPLAY = int(options["min_score_to_display"])
        EMAIL_MIN_SCORE = int(options["email_min_score"])
        EMAIL_RESULTS_TO = str(options["email_results_to"])
        EUROPE_MARKET_START = options["europe_market_start"]
        EUROPE_MARKET_END = options["europe_market_end"]
        US_MARKET_START = options["us_market_start"]
        US_MARKET_END = options["us_market_end"]
        LOOP_ACTIVE_START = options["loop_active_start"]
        LOOP_ACTIVE_END = options["loop_active_end"]

        self.app_options = options.copy()
        if save:
            self.save_app_options(self.app_options)
            self.refresh_results_table()
            self.update_market_progress_bars()
            self.update_lcd_reloj()

    def refresh_results_table(self):
        if not hasattr(self, "E_Resultados"):
            return
        self.set_table_headers(DEFAULT_RESULT_HEADERS)
        for result in self.cumulative_results:
            self._add_result_to_table(result)

    def on_configure_options(self):
        dialog = OptionsDialog(self.app_options, self)
        dialog.option_changed.connect(lambda options: self.apply_app_options(options, save=True))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.apply_app_options(dialog.options(), save=True)
        self.append_to_visor(
            f"Opciones actualizadas. Score minimo en tabla: {MIN_SCORE_TO_DISPLAY}."
        )

    def set_table_headers(self, headers):
        self.E_Resultados.setSortingEnabled(False)
        if not headers:
            headers = DEFAULT_RESULT_HEADERS
        self.E_Resultados.setColumnCount(len(headers))
        self.E_Resultados.setHorizontalHeaderLabels(headers)
        self.E_Resultados.setRowCount(0)
        # Ajustar tamaño de columnas al tamaño de la ventana
        try:
            header = self.E_Resultados.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

            column_widths = {
                "Ticker": 70,
                "Precio": 70,
                "Signal": 120,
                "Score": 70,
                "Trend": 70,
                "CFI Diario": 100,
                "CFI Semanal": 100,
                "Flow": 100,
                "Smart Money": 100,
                "Vol Relativo":100,
                "Fecha": 129,
            }

            for col, name in enumerate(headers):
                self.E_Resultados.setColumnWidth(col, column_widths.get(name, 100))
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

    def _time_to_seconds(self, value):
        return value.hour * 3600 + value.minute * 60 + value.second

    def _is_loop_time_allowed(self, now=None):
        now_time = (now or datetime.now()).time()
        return LOOP_ACTIVE_START <= now_time < LOOP_ACTIVE_END

    def _market_progress_percent(self, now_time, start_time, end_time):
        start_seconds = self._time_to_seconds(start_time)
        end_seconds = self._time_to_seconds(end_time)
        now_seconds = self._time_to_seconds(now_time)
        if now_seconds <= start_seconds:
            return 0
        if now_seconds >= end_seconds:
            return 100
        return round(((now_seconds - start_seconds) / (end_seconds - start_seconds)) * 100)

    def _set_market_progress(self, widget_name, percent):
        progress_bar = getattr(self, widget_name, None)
        if progress_bar is None:
            return
        progress_bar.setValue(percent)
        progress_bar.setFormat(f"{percent}%")

    def update_market_progress_bars(self):
        now_time = datetime.now().time()
        europe_percent = self._market_progress_percent(
            now_time,
            EUROPE_MARKET_START,
            EUROPE_MARKET_END,
        )
        us_percent = self._market_progress_percent(
            now_time,
            US_MARKET_START,
            US_MARKET_END,
        )
        self._set_market_progress("P_MercadoEuropeo", europe_percent)
        self._set_market_progress("P_MercadoAmericano", us_percent)

    def _stop_loop_for_market_close(self):
        if self.loop_timer.isActive():
            self.loop_timer.stop()
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.request_stop()
            self.B_Cancelar.setEnabled(False)
            self.append_to_visor("Cierre de horario: cancelando análisis en curso.")
        if self.C_Tiempo.isChecked():
            self.C_Tiempo.setChecked(False)
        else:
            self.update_lcd_reloj()
        self.append_to_visor(
            f"Loop detenido: fuera del horario {time_to_text(LOOP_ACTIVE_START)} - "
            f"{time_to_text(LOOP_ACTIVE_END)}."
        )

    def _schedule_next_timed_analysis(self):
        if not self.C_Tiempo.isChecked():
            self._stop_loop_timer()
            return

        if not self._is_loop_time_allowed():
            self._stop_loop_for_market_close()
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
        self.update_market_progress_bars()
        self.lcd_Reloj.display(datetime.now().strftime("%H:%M:%S"))

        if self.C_Tiempo.isChecked():
            if self._is_loop_time_allowed():
                self._loop_market_close_handled = False
            elif not self._loop_market_close_handled:
                self._loop_market_close_handled = True
                self._stop_loop_for_market_close()
                return

        loop_lcd = getattr(self, "lcd_Loop", None)
        if loop_lcd is None:
            return

        if self.C_Tiempo.isChecked():
            remaining = self.loop_timer.remainingTime()
            if remaining > 0:
                loop_lcd.display(self._format_countdown(remaining))
            else:
                loop_lcd.display("00:00:00")
            return

        loop_lcd.display("00:00:00")

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
        self.clear_ticker_input()
        self.start_analysis(
            tickers,
            clear_results=False,
            show_current_results=len(tickers) == 1,
        )

    def start_analysis(
        self,
        tickers,
        clear_results=False,
        replace_results=False,
        show_current_results=False,
    ):
        self._stop_loop_timer()
        self.analysis_clear_results = clear_results
        self.analysis_replace_results = replace_results
        self.analysis_show_current_results = show_current_results
        self.cumulative_results = []
        self.set_table_headers([])
        self.append_to_visor("Iniciando análisis...")

        self.B_Lista.setEnabled(False)
        self.B_Carpeta.setEnabled(False)
        self.B_Ticker.setEnabled(False)
        self.B_Cancelar.setEnabled(True)

        self.analysis_thread = AnalysisThread(tickers)
        self.analysis_thread.progress.connect(self.append_to_visor)
        self.analysis_thread.result_ready.connect(self.on_analysis_result)
        self.analysis_thread.finished.connect(self.on_analysis_finished)
        self.analysis_thread.error.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_e_ticker_edited(self, *args, **kwargs):  # pylint: disable=W0613
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

    def on_analysis_result(self, result):
        self.cumulative_results.append(result)
        self._add_result_to_table(result)

    def _add_result_to_table(self, result):
        if int(result.get("Score", 0)) <= MIN_SCORE_TO_DISPLAY:
            return

        columns = list(result.keys())
        if self.E_Resultados.columnCount() == 0:
            self.set_table_headers(columns)

        self.E_Resultados.setSortingEnabled(False)
        row_idx = self.E_Resultados.rowCount()
        self.E_Resultados.insertRow(row_idx)
        numeric_columns = {"Precio", "Score", "Vol Relativo"}
        for col_idx, header in enumerate(columns):
            value = result.get(header, "")
            display_value = str(value)
            if header == "Fecha":
                display_value = display_value.split()[0]
            item = QTableWidgetItem(display_value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if header in numeric_columns:
                item.setData(Qt.ItemDataRole.EditRole, value)
            self._style_result_item(item, header, value)
            self.E_Resultados.setItem(row_idx, col_idx, item)
        self.E_Resultados.setSortingEnabled(True)
        self.E_Resultados.sortItems(columns.index("Score"), Qt.SortOrder.DescendingOrder)

    def _style_result_item(self, item, header, value):
        text = str(value).upper()

        if header == "Score":
            try:
                score = int(value)
            except (TypeError, ValueError):
                return
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            if score >= 80:
                item.setBackground(QBrush(QColor("#dff3e6")))
                item.setForeground(QBrush(QColor("#17633a")))
            else:
                item.setBackground(QBrush(QColor("#fff1d6")))
                item.setForeground(QBrush(QColor("#7a4b00")))
            return

        if header == "Signal":
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            if "COMPRA" in text:
                item.setBackground(QBrush(QColor("#e1f4eb")))
                item.setForeground(QBrush(QColor("#15613a")))
            elif "VENTA" in text:
                item.setBackground(QBrush(QColor("#f8e1e1")))
                item.setForeground(QBrush(QColor("#8a2f2f")))
            else:
                item.setBackground(QBrush(QColor("#eef3f7")))
                item.setForeground(QBrush(QColor("#4a5b66")))
            return

        if header in {"Flow", "Smart Money"}:
            if any(word in text for word in ("COMPRANDO", "ACUMULANDO")):
                item.setForeground(QBrush(QColor("#17633a")))
            elif any(word in text for word in ("VENDIENDO", "DISTRIBUYENDO")):
                item.setForeground(QBrush(QColor("#8a2f2f")))

    def on_analysis_finished(self, results):
        self.append_to_visor("Análisis finalizado.")
        self.B_Lista.setEnabled(True)
        self.B_Carpeta.setEnabled(True)
        self.B_Ticker.setEnabled(True)
        self.B_Cancelar.setEnabled(False)
        self._schedule_next_timed_analysis()

        self.analysis_replace_results = False
        self.analysis_show_current_results = False

        result_keys = {
            (row.get("Ticker"), row.get("Fecha"))
            for row in self.cumulative_results
        }
        for row in results:
            key = (row.get("Ticker"), row.get("Fecha"))
            if key not in result_keys:
                self.cumulative_results.append(row)
                self._add_result_to_table(row)
                result_keys.add(key)

        if not results and not self.cumulative_results:
            self.append_to_visor("No se generaron resultados.")
            return

        if not self.cumulative_results:
            self.append_to_visor("No hay resultados para mostrar.")
            return

        sorted_results = sorted(
            self.cumulative_results,
            key=lambda row: int(row.get("Score", 0)),
            reverse=True,
        )
        self.cumulative_results = sorted_results

        if self.E_Resultados.rowCount() == 0:
            self.append_to_visor(
                f"No hay resultados con Score superior a {MIN_SCORE_TO_DISPLAY}."
            )

        if EXPORT_EXCEL:
            df = pd.DataFrame(self.cumulative_results)
            try:
                df.to_excel(EXCEL_NAME, index=False)
                self.append_to_visor(f"Excel exportado: {EXCEL_NAME}")
            except Exception as exc:
                self.append_to_visor(f"Error exportando Excel: {exc}")

        high_score_results = [
            row for row in sorted_results if int(row.get("Score", 0)) >= EMAIL_MIN_SCORE
        ]
        try:
            email_sent, email_message = send_high_score_email(high_score_results)
            self.append_to_visor(email_message)
            if not email_sent and high_score_results:
                self.append_to_visor(
                    "Configura PYTRADER_SMTP_HOST, PYTRADER_SMTP_USER y "
                    "PYTRADER_SMTP_PASSWORD para activar el envio automatico."
                )
        except Exception as exc:
            self.append_to_visor(f"Error enviando correo: {exc}")

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

        if not self._is_loop_time_allowed():
            QMessageBox.warning(
                self,
                "Loop fuera de horario",
                f"El loop solo puede activarse entre las "
                f"{time_to_text(LOOP_ACTIVE_START)} y las {time_to_text(LOOP_ACTIVE_END)}.",
            )
            self.C_Tiempo.setChecked(False)
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

        self._loop_market_close_handled = False
        self.append_to_visor("Loop activado.")
        if not (self.analysis_thread and self.analysis_thread.isRunning()):
            self._schedule_next_timed_analysis()
        self.update_lcd_reloj()

    def on_loop_timer_timeout(self):
        self.update_lcd_reloj()
        if not self.C_Tiempo.isChecked():
            return
        if not self._is_loop_time_allowed():
            self._stop_loop_for_market_close()
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
