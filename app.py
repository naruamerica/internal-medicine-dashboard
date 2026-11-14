"""Internal Medicine Citation & Research Trend Dashboard.

開発要件定義書・基本設計書 Version 1.2 準拠:
- 0. ログイン認証機能（未認証時アクセス完全遮断、ハッシュ照合）
- 2. ダッシュボードの全体構成（6画面ナビゲーション）
- 8. 技術仕様（Python / Streamlit / SQLite / Pandas / Plotly）
"""

import sys
import os

# プロジェクトルートパスの設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
for p in [_current_dir, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st

# Streamlit ページ基本設定
st.set_page_config(
    page_title="Internal Medicine Citation & Research Trend Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. ログイン認証チェック（要件 0 準拠）
try:
    from src.auth import check_authentication, logout
    from src.ui.common import apply_custom_styles
    from src.ui.page_overview import render_overview_page
    from src.ui.page_annual import render_annual_page
    from src.ui.page_article import render_article_page
    from src.ui.page_burst import render_burst_page
    from src.ui.page_topics import render_topics_page
    from src.ui.page_high_impact import render_high_impact_page
    from src.sync_service import sync_papers_for_years
except ImportError:
    from src.auth import check_authentication, logout
    from internal_medicine_dashboard.src.ui.common import apply_custom_styles
    from internal_medicine_dashboard.src.ui.page_overview import render_overview_page
    from internal_medicine_dashboard.src.ui.page_annual import render_annual_page
    from internal_medicine_dashboard.src.ui.page_article import render_article_page
    from internal_medicine_dashboard.src.ui.page_burst import render_burst_page
    from internal_medicine_dashboard.src.ui.page_topics import render_topics_page
    from internal_medicine_dashboard.src.ui.page_high_impact import render_high_impact_page
    from internal_medicine_dashboard.src.sync_service import sync_papers_for_years

check_authentication()

# 4. サイドバー・ナビゲーション
st.sidebar.markdown(
    """
    <div style="padding: 10px 0 20px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #1E3A8A; letter-spacing: 1px; text-transform: uppercase;">Internal Medicine</div>
        <div style="font-size: 17px; font-weight: 700; color: #0F172A;">Citation Dashboard</div>
        <div style="font-size: 11px; color: #64748B;">Research Trend Analysis</div>
    </div>
    """,
    unsafe_allow_html=True,
)

menu_options = [
    "Overview",
    "Annual Citations",
    "Article Analysis",
    "Burst Articles",
    "Topic Analysis",
    "High Impact Articles",
]

menu_icons = {
    "Overview": "📊",
    "Annual Citations": "📈",
    "Article Analysis": "📄",
    "Burst Articles": "🔥",
    "Topic Analysis": "🏷️",
    "High Impact Articles": "⭐",
}

selected_page = st.sidebar.radio(
    "分析メニュー",
    options=menu_options,
    format_func=lambda x: f"{menu_icons.get(x, '')} {x}",
)

st.sidebar.markdown("---")

# データ追加取得・同期パネル（画面上からワンクリック更新）
with st.sidebar.expander("📥 論文データの追加取得・同期", expanded=False):
    st.markdown("<div style='font-size: 12px; color: #475569; margin-bottom: 8px;'>PubMed & OpenAlex から指定年の論文と被引用データを取得してDBに蓄積します。</div>", unsafe_allow_html=True)
    col_sy, col_ey = st.columns(2)
    with col_sy:
        sync_start = st.number_input("開始年", min_value=2015, max_value=2027, value=2024, step=1)
    with col_ey:
        sync_end = st.number_input("終了年", min_value=2015, max_value=2027, value=2025, step=1)

    if st.button("🚀 データ取得・同期を実行", use_container_width=True):
        s_min = min(int(sync_start), int(sync_end))
        s_max = max(int(sync_start), int(sync_end))
        with st.spinner(f"{s_min}〜{s_max}年の論文と被引用データを取得中...（しばらくお待ちください）"):
            try:
                imp_cnt, match_cnt, snap_id = sync_papers_for_years(s_min, s_max)
                st.success(f"同期成功！\n・登録論文: {imp_cnt} 報\n・引用照合: {match_cnt} 件\n・スナップショット: {snap_id}")
                st.rerun()
            except Exception as e:
                st.error(f"同期中にエラーが発生しました: {e}")

st.sidebar.markdown("---")

# サイドバー情報
st.sidebar.markdown(
    f"""
    <div style="font-size: 12px; color: #64748B; line-height: 1.6;">
        <strong>Target Journal:</strong><br>Internal Medicine<br>
        <strong>ISSN:</strong> 1349-7235 (Online)<br>
        <strong>User:</strong> {st.session_state.get('logged_in_user', 'n-ogasawara')}<br>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.sidebar.button("Logout", key="sidebar_logout_btn", use_container_width=True):
    logout()

# 5. 画面ルーティング
if selected_page == "Overview":
    render_overview_page()
elif selected_page == "Annual Citations":
    render_annual_page()
elif selected_page == "Article Analysis":
    render_article_page()
elif selected_page == "Burst Articles":
    render_burst_page()
elif selected_page == "Topic Analysis":
    render_topics_page()
elif selected_page == "High Impact Articles":
    render_high_impact_page()
