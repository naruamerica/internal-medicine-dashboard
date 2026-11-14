"""Annual Citations page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ② Annual Citations 準拠:
- 年度別被引用回数、累積被引用回数、前年比(YoY Growth Rate)
- 3つのグラフ (Annual, Cumulative, Growth Rate)
- 年度範囲フィルター
- UTF-8 BOM対応 CSVエクスポート
"""

import streamlit as st
import pandas as pd

from internal_medicine_dashboard.src.ui.common import render_top_header
from internal_medicine_dashboard.src.analytics_service import AnalyticsService
from internal_medicine_dashboard.src.database import list_all_snapshots
from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
from internal_medicine_dashboard.src.ui.charts import render_bar_chart, render_line_chart


def render_annual_page():
    render_top_header("Annual Citations - 年度別被引用状況の分析")
    svc = AnalyticsService()

    # スナップショット選択
    snapshots = list_all_snapshots()
    col_snap, col_empty = st.columns([2, 2])
    selected_snap_id = None
    if snapshots:
        with col_snap:
            snap_options = {s["snapshot_id"]: f"{s['snapshot_datetime']} ({s['snapshot_id']})" for s in snapshots}
            selected_snap_id = st.selectbox(
                "調査スナップショット",
                options=list(snap_options.keys()),
                format_func=lambda x: snap_options[x],
                key="annual_snap_select",
            )

    df_annual = svc.get_annual_citations_summary(selected_snap_id)
    if df_annual.empty:
        st.warning("年度別被引用データが存在しません。")
        return

    # 年度範囲フィルター
    min_year = int(df_annual["Citation Year"].min())
    max_year = int(df_annual["Citation Year"].max())
    
    col_range, col_btn = st.columns([3, 1])
    with col_range:
        if min_year < max_year:
            year_range = st.slider("表示年度範囲", min_value=min_year, max_value=max_year, value=(min_year, max_year))
            filtered_df = df_annual[(df_annual["Citation Year"] >= year_range[0]) & (df_annual["Citation Year"] <= year_range[1])].copy()
        else:
            filtered_df = df_annual.copy()
            st.caption(f"対象年度: {min_year}年")

    with col_btn:
        st.write("") # スペーサー
        csv_bytes = export_dataframe_to_csv_bytes(filtered_df)
        st.download_button(
            label="📥 CSVダウンロード (BOM付)",
            data=csv_bytes,
            file_name=f"annual_citations_{selected_snap_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # テーブル表示
    st.markdown("<div class='section-title'>年度別被引用集計データ</div>", unsafe_allow_html=True)
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )

    # 3つのグラフ
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("<div class='section-title'>A. Annual Citations (年度別棒グラフ)</div>", unsafe_allow_html=True)
        render_bar_chart(filtered_df, x="Citation Year", y="Annual Citations", color="#1E3A8A", height=320)

    with c2:
        st.markdown("<div class='section-title'>B. Cumulative Citations (累積被引用数折れ線)</div>", unsafe_allow_html=True)
        render_line_chart(filtered_df, x="Citation Year", y="Cumulative Citations", color="#0284C7", height=320)

    st.markdown("<div class='section-title'>C. Year-over-Year Growth Rate (前年比の推移 %)</div>", unsafe_allow_html=True)
    valid_growth = filtered_df.dropna(subset=["YoY Growth Rate (%)"])
    if not valid_growth.empty:
        render_line_chart(valid_growth, x="Citation Year", y="YoY Growth Rate (%)", color="#10B981", height=300)
    else:
        st.info("前年比を算出するには2年度以上のデータが必要です。")
