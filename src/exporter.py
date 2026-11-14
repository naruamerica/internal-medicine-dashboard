"""CSV Exporter module for Internal Medicine Citation & Research Trend Dashboard.

要件 7. CSV出力 準拠:
- Excelで文字化けしない UTF-8 BOM (utf-8-sig) エンコーディング
- 各種分析結果（論文一覧、年度別推移、Burstランキング、Emerging、High Impact、Keywords）のCSV出力
- exports フォルダへの保存およびダウンロード用バイナリ生成
"""

import io
import os
from typing import List, Dict, Any, Optional
import pandas as pd

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports"
)

def export_dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """DataFrameを UTF-8 BOM (utf-8-sig) 形式のバイトデータとしてエクスポートする。"""
    output = io.BytesIO()
    # Excelで確実に文字化けしない utf-8-sig
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return output.getvalue()

def save_dataframe_to_exports(df: pd.DataFrame, filename: str) -> str:
    """exportsフォルダにCSVを保存し、絶対パスを返す。"""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    if not filename.endswith(".csv"):
        filename += ".csv"
    file_path = os.path.join(EXPORTS_DIR, filename)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path
