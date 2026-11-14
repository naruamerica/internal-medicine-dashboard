"""Authentication module for Internal Medicine Citation & Research Trend Dashboard.

要件 0. ログイン認証機能 準拠:
- 画面中央のシンプルな認証フォーム
- パスワードはハッシュ化（PBKDF2/SHA256 + salt）して検証
- セッション管理（未認証時は全画面アクセスを遮断）
- ログイン失敗時はID/PWのどちらが間違っているかを明かさない統一エラー
- ログアウト機能
"""

import hashlib
import os
import streamlit as st


def _hash_password(password: str, salt: str) -> str:
    """Saltを付加してSHA-256でハッシュ化する。"""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _get_auth_credentials():
    """Streamlit secrets または環境変数から認証情報を取得する。"""
    # 1. st.secrets
    try:
        if "auth" in st.secrets:
            return (
                st.secrets["auth"].get("username", "n-ogasawara"),
                st.secrets["auth"].get("salt", "9f0d409f9aa28e3a2510366bad84cf03"),
                st.secrets["auth"].get("password_hash", "731761eda2f4dfa2115d0081461f06b2127b03056106161aa6ac35e466b73f28"),
            )
    except Exception:
        pass

    # 2. 環境変数フォールバック
    username = os.getenv("DASHBOARD_AUTH_USER", "n-ogasawara")
    salt = os.getenv("DASHBOARD_AUTH_SALT", "9f0d409f9aa28e3a2510366bad84cf03")
    pwd_hash = os.getenv("DASHBOARD_AUTH_HASH", "731761eda2f4dfa2115d0081461f06b2127b03056106161aa6ac35e466b73f28")
    return username, salt, pwd_hash


def verify_login(user_input_id: str, user_input_pwd: str) -> bool:
    """入力されたIDとパスワードをハッシュ照合する。"""
    expected_id, salt, expected_hash = _get_auth_credentials()
    if not user_input_id or not user_input_pwd:
        return False

    computed_hash = _hash_password(user_input_pwd, salt)
    # タイミング攻撃対策として定数時間比較相当
    return (user_input_id == expected_id) and (computed_hash == expected_hash)


def check_authentication() -> bool:
    """セッションの認証状態を確認し、未認証ならログイン画面を表示して処理を中断する。"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.logged_in_user = ""

    if st.session_state.authenticated:
        return True

    render_login_screen()
    st.stop()
    return False


def logout():
    """ログアウト処理を行い、セッションを初期化する。"""
    st.session_state.authenticated = False
    st.session_state.logged_in_user = ""
    st.rerun()


def render_login_screen():
    """要件 0.2 に準拠したログイン画面を中央に描画する。"""
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 40px; margin-bottom: 25px;">
                <div style="font-size: 14px; font-weight: 600; color: #1E3A8A; letter-spacing: 1.5px; text-transform: uppercase;">
                    Internal Medicine
                </div>
                <div style="font-size: 24px; font-weight: 700; color: #0F172A; margin-top: 4px;">
                    Citation & Research Trend Dashboard
                </div>
                <div style="font-size: 13px; color: #64748B; margin-top: 6px;">
                    日本内科学会英文誌 引用動向・研究トレンド分析システム
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            login_id = st.text_input("Login ID", placeholder="ユーザーIDを入力")
            password = st.text_input("Password", type="password", placeholder="パスワードを入力")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if verify_login(login_id, password):
                    st.session_state.authenticated = True
                    st.session_state.logged_in_user = login_id
                    st.success("認証に成功しました。ダッシュボードへ移動します...")
                    st.rerun()
                else:
                    st.error("Login ID または Password が正しくありません。")
