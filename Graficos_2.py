import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. Descargar datos de Apple (AAPL) - Último año
datos = yf.download('AAPL', 
                   period='1y',  # Período de 1 año
                   interval='1d')  # Datos diarios

# 2. Configuración del gráfico
estilo = mpf.make_mpf_style(base_mpf_style='charles', 
                          rc={'font.size': 10})

# 3. Calcular medias móviles (SMA 20 y 50 días)
sma20 = datos['Close'].rolling(window=20).mean()
sma50 = datos['Close'].rolling(window=50).mean()

# 4. Personalizar colores (verde=sube, rojo=baja)
colores = mpf.make_marketcolors(up='#2E7D32',  # Verde
                              down='#C62828',  # Rojo
                              wick={'up':'#2E7D32', 'down':'#C62828'},
                              edge={'up':'#2E7D32', 'down':'#C62828'})

estilo_personalizado = mpf.make_mpf_style(base_mpl_style='seaborn',
                                        marketcolors=colores)

# 5. Crear gráfico con:
# - Velas japonesas
# - SMA 20 (azul) y SMA 50 (naranja)
# - Volumen en la parte inferior
mpf.plot(datos,
        type='candle',
        style=estilo_personalizado,
        title='\nApple (AAPL) - Último año',
        ylabel='Precio (USD)',
        volume=True,
        mav=(20, 50),
        figratio=(12, 6),
        figscale=1.1,
        show_nontrading=False)

plt.show()