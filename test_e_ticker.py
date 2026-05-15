import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt6.QtWidgets import QApplication
import F_Trader_4 as appmod

app = QApplication([])
w = appmod.MainWindow()

# Cargar tickers desde Mi_Lista.txt si existe
try:
    tickers = appmod.load_tickers('Mi_Lista.txt')
except Exception:
    tickers = ['AAPL', 'MSFT']

# Poner archivo en E_Lista_model
if w.E_Lista_model is not None:
    w.E_Lista_model.setStringList(['Mi_Lista.txt'])

# Poner tickers en E_Ticker
w._suppress_e_ticker_edit_signal = True
if getattr(w, '_ticker_is_model', False) and w.E_Ticker_model is not None:
    w.E_Ticker_model.setStringList(tickers)
else:
    try:
        w.E_Ticker.setPlainText('\n'.join(tickers))
    except Exception:
        pass
w._suppress_e_ticker_edit_signal = False

print('Before edit, E_Lista:', w.E_Lista_model.stringList() if w.E_Lista_model is not None else None)

# Simular edición por el usuario
if getattr(w, '_ticker_is_model', False) and w.E_Ticker_model is not None:
    # modificar el primer elemento
    w._suppress_e_ticker_edit_signal = False
    w.E_Ticker_model.setData(w.E_Ticker_model.index(0,0), 'TSLA')
    # llamar manualmente al manejador
    w.on_e_ticker_edited()
else:
    try:
        w.E_Ticker.setPlainText('TSLA\nGOOG')
    except Exception:
        pass
    w.on_e_ticker_edited()

print('After edit, E_Lista:', w.E_Lista_model.stringList() if w.E_Lista_model is not None else None)

# Simular iniciar análisis (vacía E_Ticker)
w.start_analysis(['TSLA','GOOG'])

if getattr(w, '_ticker_is_model', False) and w.E_Ticker_model is not None:
    print('After start_analysis, E_Ticker model count:', w.E_Ticker_model.rowCount())
else:
    try:
        print('After start_analysis, E_Ticker text:', repr(w.E_Ticker.toPlainText()))
    except Exception:
        print('After start_analysis, E_Ticker not available')

print('Test finished')
