import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
ticker='ASML'
data=yf.download(ticker,start="2026-01-01",end="2026-07-01", interval="1d")

df = pd.read_csv('datos.csv')

fig = go.Figure(data=[go.Candlestick(x=df['Fecha'],
                open=df['Apertura'],
                high=df['Máximo'],
                low=df['Mínimo'],
                close=df['Último'])
                      ])

fig.update_layout(
    title=dict(text='The Great Recession'),
    yaxis=dict(
      title=dict(
        text=ticker
        )
    ),
    shapes = [dict(
        x0='2016-12-09', x1='2016-12-09', y0=0, y1=1, xref='x', yref='paper',
        line_width=2)],
    annotations=[dict(
        x='2016-12-09', y=0.05, xref='x', yref='paper',
        showarrow=False, xanchor='left', text='Increase Period Begins')]
)

fig.show()