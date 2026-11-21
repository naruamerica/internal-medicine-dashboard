"""Topic Analysis page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ⑤ Topic Analysis 準拠:
- Author Keywords & MeSH Terms 分析
- 出現頻度ランキング（Top 20〜30 棒グラフ）
- 選択したキーワードの年度別推移（折れ線グラフ）
- Keyword Heatmap（横軸: 年度, 縦軸: キーワード）
- 絞り込みフィルター & CSVダウンロード
"""

import streamlit as st
import pandas as pd

try:
    from src.ui.common import render_top_header
    from src.analytics_service import AnalyticsService
    from src.exporter import export_dataframe_to_csv_bytes
    from src.ui.charts import render_horizontal_bar, render_multi_line_chart, render_heatmap
except ImportError:
    from internal_medicine_dashboard.src.ui.common import render_top_header
    from internal_medicine_dashboard.src.analytics_service import AnalyticsService
    from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
    from internal_medicine_dashboard.src.ui.charts import render_horizontal_bar, render_multi_line_chart, render_heatmap


def render_topics_page():
    render_top_header("Topic Analysis - 研究テーマ・キーワードの変遷分析")
    svc = AnalyticsService()

    # コントロールバー
    c1, c2, c3 = st.columns(3)
    with c1:
        kw_type = st.radio(
            "分析対象種別",
            options=["Author Keyword", "MeSH Descriptor"],
            horizontal=True,
        )
    with c2:
        top_n = st.slider("表示ランキング件数", min_value=10, max_value=40, value=20, step=5)
    with c3:
        min_freq = st.number_input("最低出現回数", min_value=1, value=2, step=1)

    df_freq = svc.get_topic_frequencies(keyword_type=kw_type, min_count=min_freq)

    if df_freq.empty:
        st.warning(f"該当する {kw_type} のデータが登録されていません。")
        return

    # CSVダウンロード
    col_t, col_dl = st.columns([4, 1])
    with col_dl:
        csv_bytes = export_dataframe_to_csv_bytes(df_freq)
        st.download_button(
            "📥 キーワード頻度CSV",
            data=csv_bytes,
            file_name=f"topic_frequencies_{kw_type}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # グラフ A: Top Keywords 棒グラフ
    st.markdown(f"<div class='section-title'>A. Top {kw_type}s (出現頻度上位 {top_n} 件)</div>", unsafe_allow_html=True)
    df_top = df_freq.head(top_n).sort_values(by="Frequency", ascending=True)
    render_horizontal_bar(df_top, x="Frequency", y="Keyword", height=max(400, top_n * 22))

    # グラフ B: 年別推移折れ線グラフ
    st.markdown("<div class='section-title'>B. Keyword Trends (年度別出現回数の推移)</div>", unsafe_allow_html=True)
    available_top_kws = df_freq.head(15)["Keyword"].tolist()
    default_select = available_top_kws[:3] if len(available_top_kws) >= 3 else available_top_kws

    chosen_kws = st.multiselect(
        "推移を表示するキーワードを選択（複数選択可）",
        options=df_freq["Keyword"].tolist(),
        default=default_select,
    )

    if chosen_kws:
        df_trends = svc.get_topic_annual_trends(chosen_kws, keyword_type=kw_type)
        if not df_trends.empty:
            render_multi_line_chart(df_trends, x="Year", y="Count", color_col="Keyword", height=350)
        else:
            st.info("選択されたキーワードの年別推移データがありません。")

    # グラフ D: Keyword Heatmap
    st.markdown("<div class='section-title'>D. Keyword Heatmap (年度 × キーワード出現分布)</div>", unsafe_allow_html=True)
    top_heatmap_kws = df_freq.head(15)["Keyword"].tolist()
    df_heat_data = svc.get_topic_annual_trends(top_heatmap_kws, keyword_type=kw_type)

    if not df_heat_data.empty:
        pivot_df = df_heat_data.pivot(index="Keyword", columns="Year", values="Count").fillna(0)
        render_heatmap(pivot_df, height=420)
