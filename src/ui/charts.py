"""Chart helper with seamless fallback between Plotly and Streamlit/Altair.

環境に Plotly がインストールされていれば Plotly を使用し、
未インストールの場合は Altair / Streamlit 標準チャートで美しく描画する。
"""

import pandas as pd
import streamlit as st

HAS_PLOTLY = False
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    pass

try:
    import altair as alt
    HAS_ALTAIR = True
except ImportError:
    HAS_ALTAIR = False


def render_bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "", color: str = "#1E3A8A", height: int = 320):
    """棒グラフの描画"""
    if df.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.bar(df, x=x, y=y, text=y, color_discrete_sequence=[color])
        fig.update_traces(textposition="outside")
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        chart = (
            alt.Chart(df)
            .mark_bar(color=color)
            .encode(
                x=alt.X(f"{x}:O", title=x),
                y=alt.Y(f"{y}:Q", title=y),
                tooltip=[x, y],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(df.set_index(x)[y], height=height)


def render_horizontal_bar(df: pd.DataFrame, x: str, y: str, title: str = "", height: int = 400):
    """横棒グラフの描画"""
    if df.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.bar(df, x=x, y=y, orientation="h", text=x, color=x, color_continuous_scale="Blues")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(f"{x}:Q", title="出現回数"),
                y=alt.Y(f"{y}:N", sort="-x", title=""),
                color=alt.Color(f"{x}:Q", scale=alt.Scale(scheme="blues"), legend=None),
                tooltip=[y, x],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(df.set_index(y)[x], height=height)


def render_line_chart(df: pd.DataFrame, x: str, y: str, title: str = "", color: str = "#0284C7", height: int = 320):
    """折れ線グラフの描画"""
    if df.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.line(df, x=x, y=y, markers=True, color_discrete_sequence=[color])
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        chart = (
            alt.Chart(df)
            .mark_line(point=True, color=color)
            .encode(
                x=alt.X(f"{x}:O", title=x),
                y=alt.Y(f"{y}:Q", title=y),
                tooltip=[x, y],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.line_chart(df.set_index(x)[y], height=height)


def render_multi_line_chart(df: pd.DataFrame, x: str, y: str, color_col: str, height: int = 350):
    """複数系列の折れ線グラフの描画"""
    if df.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.line(df, x=x, y=y, color=color_col, markers=True)
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        chart = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X(f"{x}:O", title=x),
                y=alt.Y(f"{y}:Q", title=y),
                color=alt.Color(f"{color_col}:N", title=color_col),
                tooltip=[x, color_col, y],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        piv = df.pivot(index=x, columns=color_col, values=y).fillna(0)
        st.line_chart(piv, height=height)


def render_scatter_chart(df: pd.DataFrame, x: str, y: str, size: str, color: str, hover: str, text: str, height: int = 400):
    """散布図の描画"""
    if df.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.scatter(
            df,
            x=x,
            y=y,
            size=size,
            color=color,
            hover_name=hover,
            text=text,
            color_continuous_scale="Viridis",
        )
        fig.update_traces(textposition="top right")
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        chart = (
            alt.Chart(df)
            .mark_circle()
            .encode(
                x=alt.X(f"{x}:Q", title=x),
                y=alt.Y(f"{y}:Q", title=y),
                size=alt.Size(f"{size}:Q", title=size),
                color=alt.Color(f"{color}:Q", scale=alt.Scale(scheme="viridis")),
                tooltip=[text, hover, x, y, size],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.dataframe(df[[text, hover, x, y, size]], use_container_width=True)


def render_heatmap(df_pivot: pd.DataFrame, height: int = 420):
    """ヒートマップの描画"""
    if df_pivot.empty:
        st.info("表示可能なデータがありません。")
        return

    if HAS_PLOTLY:
        fig = px.imshow(
            df_pivot,
            labels=dict(x="年度", y="キーワード", color="出現数"),
            x=[str(c) for c in df_pivot.columns],
            y=df_pivot.index,
            aspect="auto",
            color_continuous_scale="YlGnBu",
        )
        fig.update_layout(height=height, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_ALTAIR:
        # Altair用melt
        melted = df_pivot.reset_index().melt(id_vars="Keyword", var_name="Year", value_name="Count")
        chart = (
            alt.Chart(melted)
            .mark_rect()
            .encode(
                x=alt.X("Year:O", title="年度"),
                y=alt.Y("Keyword:N", title="キーワード"),
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="yellowgreenblue"), title="出現数"),
                tooltip=["Keyword", "Year", "Count"],
            )
            .properties(height=height)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.dataframe(df_pivot, use_container_width=True)
