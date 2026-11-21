"""Article Analysis page for Internal Medicine Citation & Research Trend Dashboard.

要件 3. ③ Article Analysis 準拠:
- 論文検索（Title, Author, PMID, DOI, Year, Article Type）
- 論文一覧表示
- 個別論文詳細ビュー
- グラフ (Citation Trend by Year, Cumulative Citation Trend)
- 過去スナップショット調査履歴の比較
"""

import streamlit as st
import pandas as pd

try:
    from src.ui.common import render_top_header
    from src.analytics_service import AnalyticsService
    from src.database import list_all_snapshots
    from src.exporter import export_dataframe_to_csv_bytes
    from src.ui.charts import render_bar_chart, render_line_chart
except ImportError:
    from internal_medicine_dashboard.src.ui.common import render_top_header
    from internal_medicine_dashboard.src.analytics_service import AnalyticsService
    from internal_medicine_dashboard.src.database import list_all_snapshots
    from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
    from internal_medicine_dashboard.src.ui.charts import render_bar_chart, render_line_chart


def render_article_page():
    render_top_header("Article Analysis - 個別論文の分析")
    svc = AnalyticsService()

    # スナップショット選択
    snapshots = list_all_snapshots()
    selected_snap_id = None
    if snapshots:
        selected_snap_id = snapshots[0]["snapshot_id"]

    # 検索フィルターパネル
    with st.expander("🔍 論文検索・絞り込みフィルター", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            q_title = st.text_input("タイトル / キーワード", placeholder="キーワードを入力")
            q_pmid = st.text_input("PMID", placeholder="例: 42983800")
        with col2:
            q_author = st.text_input("著者名", placeholder="例: Ogasawara")
            q_doi = st.text_input("DOI", placeholder="例: 10.2169/...")
        with col3:
            q_year_str = st.text_input("発行年", placeholder="例: 2025")
            q_type = st.selectbox("Article Type", ["すべて", "Journal Article", "Case Report", "Review", "Editorial", "Letter"])

    q_year = int(q_year_str.strip()) if q_year_str.strip().isdigit() else None

    # 検索実行
    df_results = svc.search_articles(
        keyword=q_title,
        author=q_author,
        pmid=q_pmid,
        doi=q_doi,
        pub_year=q_year,
        article_type=q_type,
        snapshot_id=selected_snap_id,
        limit=200,
    )

    st.markdown(f"<div class='section-title'>検索結果一覧 ({len(df_results):,} 件)</div>", unsafe_allow_html=True)
    if df_results.empty:
        st.info("該当する論文が見つかりませんでした。条件を変更して再検索してください。")
        return

    # CSVダウンロード
    col_table, col_dl = st.columns([4, 1])
    with col_dl:
        csv_bytes = export_dataframe_to_csv_bytes(df_results)
        st.download_button(
            "📥 検索結果CSV出力",
            data=csv_bytes,
            file_name="article_search_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 一覧表表示
    display_cols = ["PMID", "Title", "Authors", "Publication Year", "Article Type", "DOI", "Cited by Count"]
    st.dataframe(df_results[display_cols], use_container_width=True, hide_index=True)

    # 個別論文詳細セレクター
    st.markdown("<div class='section-title'>個別論文詳細ビュー</div>", unsafe_allow_html=True)
    pmid_list = df_results["PMID"].tolist()
    title_dict = {row["PMID"]: f"[{row['PMID']}] {row['Title'][:80]}..." for _, row in df_results.iterrows()}

    selected_pmid = st.selectbox(
        "詳細を表示する論文を選択",
        options=pmid_list,
        format_func=lambda x: title_dict.get(x, x),
    )

    if selected_pmid:
        detail = svc.get_article_details(selected_pmid, selected_snap_id)
        if detail:
            art = detail["article"]
            
            # メタデータボックス
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
                    <div style="font-size: 18px; font-weight: 700; color: #0F172A; margin-bottom: 10px;">{art['title']}</div>
                    <div style="font-size: 13px; color: #475569; margin-bottom: 6px;"><strong>著者:</strong> {art['authors'] or '情報なし'}</div>
                    <div style="display: flex; gap: 20px; font-size: 13px; color: #475569;">
                        <span><strong>PMID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/{art['pmid']}/" target="_blank">{art['pmid']}</a></span>
                        <span><strong>DOI:</strong> {art['doi'] or 'なし'}</span>
                        <span><strong>発行年:</strong> {art['publication_year']}</span>
                        <span><strong>種別:</strong> {art['article_type']}</span>
                        <span><strong>累積被引用数:</strong> <span style="font-weight:700; color:#1E3A8A; font-size:15px;">{detail['total_citations']} 回</span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # グラフ（年度別引用推移 & 累積推移）
            yearly = detail["yearly_cites"]
            if yearly:
                df_y = pd.DataFrame([{"Year": y, "Citations": c} for y, c in sorted(yearly.items())])
                df_y["Cumulative"] = df_y["Citations"].cumsum()

                c_g1, c_g2 = st.columns(2)
                with c_g1:
                    st.markdown("<div class='section-title'>A. Citation Trend by Year (年別被引用数)</div>", unsafe_allow_html=True)
                    render_bar_chart(df_y, x="Year", y="Citations", color="#1E3A8A", height=280)

                with c_g2:
                    st.markdown("<div class='section-title'>B. Cumulative Trend (累積推移)</div>", unsafe_allow_html=True)
                    render_line_chart(df_y, x="Year", y="Cumulative", color="#0284C7", height=280)
            else:
                st.info("この論文の年度別引用推移データはまだ取得されていません。")

            # 調査履歴テーブル
            st.markdown("<div class='section-title'>調査スナップショット別 引用履歴</div>", unsafe_allow_html=True)
            hist = detail["history"]
            if hist:
                df_h = pd.DataFrame(hist).rename(columns={
                    "snapshot_datetime": "調査日時",
                    "snapshot_id": "スナップショットID",
                    "cited_by_count": "累積引用数",
                    "source": "データ取得元",
                    "retrieval_status": "ステータス",
                })
                st.dataframe(df_h, use_container_width=True, hide_index=True)
            else:
                st.info("調査履歴がありません。")
