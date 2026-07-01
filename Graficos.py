import os
import pandas as pd
from pandas import Timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def convert_ohlc_prices_to_percentage_values(df):
    # Create a new DataFrame to store the results
    df_result = pd.DataFrame(index=df.index)

    # Add the 'Start Date' column from the original DataFrame to the new DataFrame
    df_result['Start Date'] = df['Start Date']

    for col in df.columns:
        if 'Price' in col:
            # Calculate the result using the formula
            result = round((df[col] - df['Open Price'].iat[0]) / df['Open Price'].iat[0] * 100, 2)

            # Replace values equal to 'Open Price'.iat[0]' with 0
            result = result.where(result != 0, 0)

            # Add the result to the new DataFrame
            df_result[col] = result

    # Add the 'Volume' and 'End Date' column from the original DataFrame to the new DataFrame
    df_result['Volume'] = df['Volume']
    df_result['End Date'] = df['End Date']

    return df_result


## Asuma que aquí fueron declaradas las variables de df_ohlc, df_chg_btc, df_chg_eth, df_chg con su respectivos datos

df_chg_btc = df_chg_btc.set_index('Start Date', inplace=False)
df_chg_eth = df_chg_eth.set_index('Start Date', inplace=False)
df_chg = df_chg.set_index('Start Date', inplace=False)
df_ohlc_percentages = convert_ohlc_prices_to_percentage_values(df_ohlc)

trading_pair = 'BNB/USDT'
start_index = '14 September 2022'

## Plotting using matplotlib and saving the plot in axlist
# Initialize the plot with #162125 as outer color and a figsize of (12, 6)
fig, ax = plt.subplots(figsize=(12, 6), facecolor='#162125')

# Place the indices and values of df_chg,df_chg_btc and df_chg_eth in the x and y axis correspondingly
symbol = trading_pair.replace("USDT", "") + "/" + "USDT"
ax.plot(df_chg.index, df_chg['% Chg'], marker='o', linestyle='-', color='#39c9bb', label=f'{symbol}')
ax.plot(df_chg_btc.index, df_chg_btc['% Chg'], marker='o', linestyle='-', color='#ff9900', label='BTC/USDT')
ax.plot(df_chg_eth.index, df_chg_eth['% Chg'], marker='o', linestyle='-', color='#8893B1', label='ETH/USDT')

# Creación del gráfico de velas
# Calcula la anchura según el intervalo de tiempo (15 minutos en este caso)
# BUG ORIGINAL: time_diff es un Timedelta; ax.bar() con eje de fechas necesita
# un ancho numérico (en días), no un objeto Timedelta.
time_diff = df_ohlc_percentages["Start Date"].diff().mean()
width = (0.6 * time_diff) / pd.Timedelta(days=1)

for index, row in df_ohlc_percentages.iterrows():
    open_price = row["Open Price"]
    close_price = row["Close Price"]
    high_price = row["High Price"]
    low_price = row["Low Price"]
    date = row["Start Date"]

    color = '#027F7F' if close_price >= open_price else '#FB0000'
    height = abs(close_price - open_price)
    bottom = min(open_price, close_price)

    ax.bar(date, height, width=width, bottom=bottom, align='center', color=color)
    ax.vlines(x=date, ymin=low_price, ymax=high_price, color=color, linewidth=1)

# Set inner color of the plot
ax.set_facecolor("#162125")

# Show every 5th tick to avoid overcrowding
ax.set_xticks(ax.get_xticks()[::5])

# Set the color of x ticks, rotation and the font weight
ax.tick_params(axis='x', colors='white')
plt.xticks(rotation=45, weight='bold', size=10)
ax.set_xlabel('Time UTC', color='white', fontsize=14, fontweight='bold')

# Format the date on the x-axis
# BUG ORIGINAL: el set_xticklabels() con los valores numéricos de los ticks
# se eliminó porque fijaba etiquetas numéricas crudas y anulaba este formatter.
if df_chg.index[1] - df_chg.index[0] == Timedelta(hours=1):
    time_format = mdates.DateFormatter('%H:%M:%S')
    ax.xaxis.set_major_formatter(time_format)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))

# Set the color of y ticks and the font weight
ax.set_yticks(ax.get_yticks())
ax.set_yticklabels(['{:,.2f}%'.format(y) for y in ax.get_yticks()], weight='bold', size=10)
ax.tick_params(axis='y', colors='white')
ax.set_ylabel('% Change', color='white', fontsize=14, fontweight='bold')

# Set the title
if df_chg.index[1] - df_chg.index[0] == Timedelta(hours=1):
    ax.set_title(f'Price Change Comparison - {start_index}', color='white', fontsize=16, fontweight='bold')

# Set grid linestyle, width and color
ax.grid(color='white', linestyle='--', linewidth=1)

# Create the legend with customizations
legend = ax.legend(prop={'size': 12, 'weight': 'bold'})

# Customize the legend text color
# BUG ORIGINAL: solo aplicaba el color al primer texto (legend.get_texts()[0]),
# y encima con un color casi igual al fondo, dejándolo invisible.
for text in legend.get_texts():
    text.set_color('white')
legend.get_frame().set_facecolor('#162125')
legend.get_frame().set_edgecolor('white')
legend.get_frame().set_alpha(1)

plt.tight_layout()

# Update all the spines' outercolors to the same color as facecolor
for spine in ax.spines.values():
    spine.set_edgecolor('#FFFFFF')

# Save the plot
# BUG ORIGINAL: "+trading_pair" era un operador unario inválido sobre un string
# (TypeError), y '//' como separador de ruta no es portable ni crea el directorio.
os.makedirs(trading_pair, exist_ok=True)
filename = start_index + ".png"
filepath = os.path.join(trading_pair, filename)
fig.savefig(filepath, dpi=300, bbox_inches="tight")

# RELEASE THE MEMORY RAM
plt.close('all')