"""High Impact Articles page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ⑥ High Impact Articles 準拠:
- Citation per Year (累積引用数 ÷ 経過年数(日数/365.25))
- High Impact ランキング
- Early Impact Articles (掲載12ヶ月未満) の独立表示
- 複数論文の比較グラフ
- 絞り込みフィルター & CSVダウンロード
"""

import streamlit as st
import pandas as pd

from internal_medicine_dashboard.src.ui.common import render_top_header
from internal_medicine_dashboard.src.analytics_service import AnalyticsService
from internal_medicine_dashboard.src.database import list_all_snapshots
from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
from internal_medicine_dashboard.src.ui.charts import render_scatter_chart


def render_high_impact_page():
    render_top_header("High Impact Articles - 短期間高影響力論文の抽出")
    svc = AnalyticsService()

    snapshots = list_all_snapshots()
    selected_snap_id = snapshots[0]["snapshot_id"] if snapshots else None

    # ロジック解説バナー
    st.markdown(
        """
        <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; font-size: 13px; color: #166534;">
            <strong>【評価指標（要件 6.1）】 Citation per Year</strong><br>
            古くから掲載されている論文が有利になりやすい累積引用数だけでなく、
            掲載からの経過期間（日数 ÷ 365.25）で割った「<strong>年間平均被引用回数（Citation per Year）</strong>」で短期間に高い影響力を持つ論文を評価します。<br>
            ・<strong>Early Impact Articles:</strong> 掲載後12か月未満の論文は経過期間が短いため、別カテゴリーとして独立評価します。
        </div>
        """,
        unsafe_allow_html=True,
    )

    # フィルターバー
    c1, c2, c3 = st.columns(3)
    with c1:
        top_limit = st.selectbox("表示件数", options=[10, 20, 50, 100], index=1)
    with c2:
        type_filter = st.selectbox("Article Type", options=["すべて", "Journal Article", "Case Report", "Review", "Editorial"])
    with c3:
        year_filter_input = st.text_input("発行年絞り込み (空白で全件)", placeholder="例: 2024")
        year_val = int(year_filter_input.strip()) if year_filter_input.strip().isdigit() else None

    df_high, df_early = svc.get_high_impact_articles(
        snapshot_id=selected_snap_id,
        article_type=type_filter,
        pub_year=year_val,
    )

    tab1, tab2 = st.tabs(["⭐ High Impact Articles (掲載1年以上)", "🌱 Early Impact Articles (掲載12ヶ月未満)"])

    with tab1:
        st.markdown(f"<div class='section-title'>High Impact Articles ランキング ({len(df_high):,} 件)</div>", unsafe_allow_html=True)
        if not df_high.empty:
            c_tbl, c_dl = st.columns([4, 1])
            with c_dl:
                csv_bytes = export_dataframe_to_csv_bytes(df_high)
                st.download_button(
                    "📥 High Impact CSV",
                    data=csv_bytes,
                    file_name="high_impact_articles.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            disp_cols = ["Rank", "Title", "Publication Year", "Article Type", "Total Citations", "Years Since Publication", "Citation per Year", "Last Updated"]
            st.dataframe(df_high[disp_cols].head(top_limit), use_container_width=True, hide_index=True)

            # 散布図: 経過年数 vs 累積引用数
            st.markdown("<div class='section-title'>経過年数と累積被引用数の分布（上位論文）</div>", unsafe_allow_html=True)
            df_plot = df_high.head(top_limit)
            render_scatter_chart(
                df_plot,
                x="Years Since Publication",
                y="Total Citations",
                size="Citation per Year",
                color="Citation per Year",
                hover="Title",
                text="Rank",
                height=400,
            )
        else:
            st.info("条件に合致する High Impact Articles はありません。")

    with tab2:
        st.markdown(f"<div class='section-title'>Early Impact Articles (掲載12ヶ月未満の急上昇論文: {len(df_early):,} 件)</div>", unsafe_allow_html=True)
        if not df_early.empty:
            c_tbl_e, c_dl_e = st.columns([4, 1])
            with c_dl_e:
                csv_bytes_e = export_dataframe_to_csv_bytes(df_early)
                st.download_button(
                    "📥 Early Impact CSV",
                    data=csv_bytes_e,
                    file_name="early_impact_articles.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            disp_cols_e = ["Rank", "Title", "Publication Year", "Article Type", "Total Citations", "Years Since Publication", "Citation per Year"]
            st.dataframe(df_early[disp_cols_e].head(top_limit), use_container_width=True, hide_index=True)
        else:
            st.info("掲載後12ヶ月未満で被引用実績を持つ論文はありません。")
