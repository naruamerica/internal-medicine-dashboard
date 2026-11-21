"""Burst Articles page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ④ Burst Articles 準拠:
- 直近確定暦年実績 vs 過去3暦年平均
- Burst Score & Growth Rate ランキング
- Emerging Articles (掲載後3年以内) の独立管理
- 複数論文の引用推移比較グラフ
- 絞り込みフィルター & CSVダウンロード
"""

import streamlit as st
import pandas as pd

try:
    from src.ui.common import render_top_header
    from src.analytics_service import AnalyticsService
    from src.database import list_all_snapshots
    from src.exporter import export_dataframe_to_csv_bytes
    from src.metrics import get_latest_confirmed_year
    from src.ui.charts import render_multi_line_chart
except ImportError:
    from internal_medicine_dashboard.src.ui.common import render_top_header
    from internal_medicine_dashboard.src.analytics_service import AnalyticsService
    from internal_medicine_dashboard.src.database import list_all_snapshots
    from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
    from internal_medicine_dashboard.src.metrics import get_latest_confirmed_year
    from internal_medicine_dashboard.src.ui.charts import render_multi_line_chart


def render_burst_page():
    render_top_header("Burst Articles - 引用急増論文の抽出")
    svc = AnalyticsService()
    confirmed_year = get_latest_confirmed_year()

    snapshots = list_all_snapshots()
    selected_snap_id = snapshots[0]["snapshot_id"] if snapshots else None

    # ロジック解説バナー
    st.markdown(
        f"""
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; font-size: 13px; color: #1E3A8A;">
            <strong>【抽出ロジック（要件 4.1）】</strong><br>
            最新確定暦年 <strong>{confirmed_year}年</strong> の年間被引用数と、その直前3暦年（{confirmed_year-3}〜{confirmed_year-1}年）の平均被引用数を比較します。<br>
            ・<strong>Burst Score:</strong> 直近確定暦年引用数 ÷ 過去3年平均引用数（例: 3.0x）<br>
            ・<strong>Emerging Articles:</strong> 掲載後3年以内の新着論文は、過去3年の履歴が十分でないため別枠で管理します。
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 絞り込みフィルター
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        min_recent = st.number_input("直近確定暦年の最低被引用数", min_value=1, value=1, step=1)
    with col_f2:
        art_type_filter = st.selectbox("Article Type", ["すべて", "Journal Article", "Case Report", "Review", "Editorial"])
    with col_f3:
        year_filter_input = st.text_input("出版年絞り込み (空白で全件)", placeholder="例: 2022")
        year_filter = int(year_filter_input.strip()) if year_filter_input.strip().isdigit() else None

    df_burst, df_emerging = svc.get_burst_articles(
        snapshot_id=selected_snap_id,
        min_recent_citations=min_recent,
        article_type=art_type_filter,
        pub_year_filter=year_filter,
    )

    tab1, tab2 = st.tabs(["🔥 Burst Articles (通常ランキング)", "🌱 Emerging Articles (掲載後3年以内)"])

    with tab1:
        st.markdown(f"<div class='section-title'>Burst Articles ランキング ({len(df_burst):,} 件)</div>", unsafe_allow_html=True)
        if not df_burst.empty:
            c_tbl, c_dl = st.columns([4, 1])
            with c_dl:
                csv_bytes = export_dataframe_to_csv_bytes(df_burst.drop(columns=["counts_by_year"], errors="ignore"))
                st.download_button("📥 BurstランキングCSV", data=csv_bytes, file_name=f"burst_articles_{confirmed_year}.csv", mime="text/csv", use_container_width=True)

            disp_cols = ["Rank", "Title", "Publication Year", "Article Type", "Previous 3-Year Avg", "Recent Year Citations", "Burst Score", "Growth Rate (%)", "Total Citations"]
            st.dataframe(df_burst[disp_cols], use_container_width=True, hide_index=True)

            # 比較グラフ
            st.markdown("<div class='section-title'>複数論文の引用推移比較</div>", unsafe_allow_html=True)
            chosen_titles = st.multiselect(
                "推移を比較する論文を選択（最大5件）",
                options=df_burst["Title"].tolist(),
                default=df_burst["Title"].head(2).tolist() if len(df_burst) >= 2 else df_burst["Title"].tolist(),
            )
            if chosen_titles:
                plot_data = []
                for _, row in df_burst[df_burst["Title"].isin(chosen_titles)].iterrows():
                    counts = row.get("counts_by_year", {})
                    for y, c in counts.items():
                        plot_data.append({"Title": row["Title"][:40] + "...", "Year": y, "Citations": c})
                if plot_data:
                    df_plot = pd.DataFrame(plot_data).sort_values(by="Year")
                    render_multi_line_chart(df_plot, x="Year", y="Citations", color_col="Title", height=350)
        else:
            st.info("条件に一致する Burst Articles がありません（複数年の引用実績が必要です）。")

    with tab2:
        st.markdown(f"<div class='section-title'>Emerging Articles (掲載後3年以内の注目論文: {len(df_emerging):,} 件)</div>", unsafe_allow_html=True)
        if not df_emerging.empty:
            c_tbl_e, c_dl_e = st.columns([4, 1])
            with c_dl_e:
                csv_bytes_e = export_dataframe_to_csv_bytes(df_emerging.drop(columns=["counts_by_year"], errors="ignore"))
                st.download_button("📥 Emerging一覧CSV", data=csv_bytes_e, file_name=f"emerging_articles_{confirmed_year}.csv", mime="text/csv", use_container_width=True)

            disp_cols_e = ["Rank", "Title", "Publication Year", "Article Type", "Recent Year Citations", "Total Citations"]
            st.dataframe(df_emerging[disp_cols_e], use_container_width=True, hide_index=True)
        else:
            st.info("条件に一致する Emerging Articles はありません。")
