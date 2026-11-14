"""Common UI styling and layout components for Internal Medicine Dashboard."""

from typing import Any
import streamlit as st


def apply_custom_styles():
    """洗練された学術誌ダッシュボード用CSSスタイルを適用する。"""
    st.markdown(
        """
        <style>
        /* 全体フォント・ベース */
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #1E293B;
        }

        /* ヘッダー・ナビゲーション */
        .main-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
            border-radius: 8px;
            color: white;
            margin-bottom: 24px;
        }
        .main-header-title {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .main-header-subtitle {
            font-size: 12px;
            color: #94A3B8;
        }
        .user-badge {
            display: inline-flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.15);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            color: #F8FAFC;
        }

        /* KPI カード */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .kpi-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.03);
            border-top: 4px solid #1E3A8A;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .kpi-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.06);
            transform: translateY(-2px);
        }
        .kpi-label {
            font-size: 12px;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 28px;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
        }
        .kpi-subtext {
            font-size: 11px;
            color: #94A3B8;
            margin-top: 6px;
        }

        /* テーブル & データフレーム */
        .stDataFrame {
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            overflow: hidden;
        }

        /* セクション見出し */
        .section-title {
            font-size: 17px;
            font-weight: 700;
            color: #0F172A;
            margin-top: 20px;
            margin-bottom: 12px;
            padding-left: 10px;
            border-left: 4px solid #2563EB;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_header(current_page: str):
    """上部ヘッダー（ジャーナル名、現在画面、ログイン情報、ログアウトボタン）を描画する。"""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"""
            <div style="margin-bottom: 15px;">
                <span style="font-size: 12px; font-weight: 600; color: #1E3A8A; text-transform: uppercase; letter-spacing: 1px;">Internal Medicine</span>
                <h2 style="margin: 0; font-size: 24px; font-weight: 700; color: #0F172A;">{current_page}</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        user_name = st.session_state.get("logged_in_user", "n-ogasawara")
        st.markdown(
            f"""
            <div style="text-align: right; padding-top: 5px;">
                <span style="font-size: 13px; color: #475569; margin-right: 12px;">👤 <strong>{user_name}</strong></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Logout", key="logout_btn", use_container_width=True):
            from internal_medicine_dashboard.src.auth import logout
            logout()


def render_kpi_card(label: str, value: Any, subtext: str = "", border_color: str = "#1E3A8A"):
    """統一デザインのKPIカードを描画する。"""
    st.markdown(
        f"""
        <div class="kpi-card" style="border-top-color: {border_color};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtext">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
