import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from F_Trader_4 import (
    calculate_indicators,
    export_unanalyzed_tickers,
    load_tickers,
)


def make_df():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    return pd.DataFrame(
        {
            "Open": [100 + i * 0.5 for i in range(60)],
            "High": [105 + i * 0.5 for i in range(60)],
            "Low": [95 + i * 0.5 for i in range(60)],
            "Close": [102 + i * 0.4 for i in range(60)],
            "Volume": [1000 + i * 10 for i in range(60)],
        },
        index=dates,
    )


def test_calculate_indicators_adds_rsi_macd_and_pe_columns():
    df = make_df()
    params = {
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "score_weight_rsi": 5,
        "score_weight_macd": 5,
        "score_weight_per": 5,
        "per_max": 25,
        "adx_period": 14,
        "adx_threshold": 20,
        "score_weight_adx": 5,
        "score_weight_vwap": 5,
    }

    result = calculate_indicators(df, pe_ratio=18.5, params=params)

    assert "rsi" in result.columns
    assert "macd" in result.columns
    assert "macd_signal" in result.columns
    assert "per" in result.columns
    assert "vwap" in result.columns
    assert "adx" in result.columns
    assert result["score"].notna().all()
    assert result["score"].iloc[-1] >= 0


def test_load_tickers_ignores_continent_headers(tmp_path):
    screener = tmp_path / "screener.txt"
    screener.write_text(
        "###ESPAÑA,NYSE:ABC\n###AMERICA,NASDAQ:XYZ\n###ASIA,HKEX:123\n",
        encoding="utf-8",
    )

    assert load_tickers(screener) == ["ABC", "XYZ", "123"]


def test_export_unanalyzed_tickers_writes_unique_values(tmp_path):
    output_file = tmp_path / "No_Analizados.txt"

    output_path, count = export_unanalyzed_tickers(
        ["ABC", " XYZ ", "ABC", ""], output_file
    )

    assert output_path == output_file
    assert count == 2
    assert output_file.read_text(encoding="utf-8") == "ABC\nXYZ\n"
