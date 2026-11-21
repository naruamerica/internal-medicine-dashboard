"""Overview page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ① Overview 準拠:
- KPIカード (Publications, Total Citations, Annual Citations, Average Citations)
- 出版年（単年・年範囲）絞り込みフィルター
- グラフ (Annual Citation Trends, Cumulative Citations)
- Top Cited Articles と Top Burst Articles の上下分離表示
- スナップショット選択およびデータ情報表示
"""

import streamlit as st
import pandas as pd
from typing import Optional

try:
    from src.ui.common import render_kpi_card, render_top_header
    from src.analytics_service import AnalyticsService
    from src.database import list_all_snapshots
    from src.ui.charts import render_bar_chart, render_line_chart
except ImportError:
    from internal_medicine_dashboard.src.ui.common import render_kpi_card, render_top_header
    from internal_medicine_dashboard.src.analytics_service import AnalyticsService
    from internal_medicine_dashboard.src.database import list_all_snapshots
    from internal_medicine_dashboard.src.ui.charts import render_bar_chart, render_line_chart


def render_overview_page():
    render_top_header("Overview - ジャーナル全体の現況")
    svc = AnalyticsService()

    # コントロール行（スナップショット選択 & 出版年フィルター & ジャーナル情報）
    snapshots = list_all_snapshots()
    available_years = svc.get_available_publication_years()

    col_snap, col_year, col_info = st.columns([1.2, 1.3, 1.5])
    selected_snap_id = None

    with col_snap:
        if snapshots:
            snap_options = {s["snapshot_id"]: f"{s['snapshot_datetime']} ({s['snapshot_id']})" for s in snapshots}
            chosen_key = st.selectbox(
                "調査スナップショット",
                options=list(snap_options.keys()),
                format_func=lambda x: snap_options[x],
            )
            selected_snap_id = chosen_key
        else:
            st.info("スナップショットが登録されていません。")

    start_pub_year = None
    end_pub_year = None

    with col_year:
        if available_years:
            min_y = min(available_years)
            max_y = max(available_years)
            year_mode = st.radio(
                "出版年フィルター",
                options=["全期間", "範囲指定", "単年指定"],
                horizontal=True,
                key="ov_year_mode",
            )
            if year_mode == "範囲指定":
                if min_y < max_y:
                    y_range = st.slider("対象出版年の範囲", min_value=min_y, max_value=max_y, value=(min_y, max_y))
                    start_pub_year, end_pub_year = y_range
                else:
                    st.caption(f"登録出版年: {min_y}年")
                    start_pub_year = end_pub_year = min_y
            elif year_mode == "単年指定":
                sel_y = st.selectbox("対象出版年", options=list(reversed(available_years)))
                start_pub_year = end_pub_year = sel_y
            else:
                start_pub_year = None
                end_pub_year = None
        else:
            st.caption("出版年情報なし")

    with col_info:
        period_text = "全期間"
        if start_pub_year and end_pub_year:
            period_text = f"{start_pub_year}年" if start_pub_year == end_pub_year else f"{start_pub_year}年 〜 {end_pub_year}年"

        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px; font-size: 12px; color: #475569; margin-top: 5px;">
                <strong>対象ジャーナル:</strong> Internal Medicine (1349-7235 / 0918-2918)<br>
                <strong>分析対象期間:</strong> <span style="color:#1E3A8A; font-weight:700;">{period_text}</span> 掲載論文<br>
                <strong>データソース:</strong> PubMed E-utilities / OpenAlex API
            </div>
            """,
            unsafe_allow_html=True,
        )

    # KPI集計（指定出版年で絞り込み）
    kpis = svc.get_overview_kpis(
        snapshot_id=selected_snap_id,
        start_pub_year=start_pub_year,
        end_pub_year=end_pub_year,
    )

    # 4連 KPI カード
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card(
            label="Publications",
            value=f"{kpis['total_pubs']:,} 報",
            subtext=f"指定期間（{period_text}）の対象論文数",
            border_color="#1E3A8A",
        )
    with c2:
        render_kpi_card(
            label="Total Citations",
            value=f"{kpis['total_citations']:,} 回",
            subtext=f"調査時点 ({kpis['last_updated'][:10]}) の累積引用数",
            border_color="#0284C7",
        )
    with c3:
        render_kpi_card(
            label=f"Annual Citations ({kpis['confirmed_year']}年)",
            value=f"{kpis['annual_confirmed_cites']:,} 回",
            subtext="直近の確定暦年実績",
            border_color="#10B981",
        )
    with c4:
        render_kpi_card(
            label="Average Citations",
            value=f"{kpis['avg_citations']:.2f} 回/報",
            subtext="累積引用数 ÷ 論文総数",
            border_color="#8B5CF6",
        )

    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

    # グラフ表示（Annual & Cumulative）
    col_chart1, col_chart2 = st.columns(2)
    df_annual = svc.get_annual_citations_summary(
        snapshot_id=selected_snap_id,
        start_pub_year=start_pub_year,
        end_pub_year=end_pub_year,
    )

    with col_chart1:
        st.markdown("<div class='section-title'>A. Annual Citation Trends (年度別被引用数)</div>", unsafe_allow_html=True)
        render_bar_chart(df_annual, x="Citation Year", y="Annual Citations", color="#1E3A8A", height=320)

    with col_chart2:
        st.markdown("<div class='section-title'>B. Cumulative Citations (累積被引用数推移)</div>", unsafe_allow_html=True)
        render_line_chart(df_annual, x="Citation Year", y="Cumulative Citations", color="#0284C7", height=320)

    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)

    # Top Articles セクション（同じ行に並べず、上下に分離して全幅で表示）
    # 1. Top Cited Articles (上位10件)
    st.markdown("<div class='section-title'>Top Cited Articles (累積被引用数 上位10件)</div>", unsafe_allow_html=True)
    df_top_cited = svc.search_articles(
        snapshot_id=selected_snap_id,
        start_pub_year=start_pub_year,
        end_pub_year=end_pub_year,
        limit=10,
    )
    if not df_top_cited.empty:
        display_cols = ["PMID", "Title", "Authors", "Publication Year", "Article Type", "DOI", "Cited by Count"]
        st.dataframe(
            df_top_cited[display_cols],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("条件に一致する論文データがありません。")

    st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)

    # 2. Top Burst Articles (上位10件)
    st.markdown("<div class='section-title'>Top Burst Articles (注目度急上昇 上位10件)</div>", unsafe_allow_html=True)
    df_burst, _ = svc.get_burst_articles(
        snapshot_id=selected_snap_id,
        start_pub_year=start_pub_year,
        end_pub_year=end_pub_year,
    )
    if not df_burst.empty:
        burst_display_cols = [
            "Rank",
            "Title",
            "Publication Year",
            "Article Type",
            "Recent Year Citations",
            "Previous 3-Year Avg",
            "Burst Score",
            "Growth Rate (%)",
            "Total Citations",
        ]
        st.dataframe(
            df_burst[burst_display_cols].head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("※十分な複数年引用実績を持つ急増論文が蓄積されるとここに表示されます。")
