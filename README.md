# Internal Medicine Citation & Research Trend Dashboard

日本内科学会英文誌 *Internal Medicine* 引用動向・研究トレンド分析ダッシュボード（Version 1.2 準拠）

## 1. 概要
- **対象ジャーナル**: Internal Medicine
- **ISSN**: Online 1349-7235 / Print 0918-2918
- **技術スタック**: Python / Streamlit / SQLite / Pandas / Plotly
- **データソース**: PubMed E-utilities / OpenAlex API

## 2. フォルダ構成（構成B）
```text
internal_medicine_dashboard/
├── database/               # SQLiteデータベース専用 (internal_medicine.db)
├── data/                   # JSONキャッシュ・バックアップ・初期データ
├── exports/                # CSVエクスポート出力先 (UTF-8 BOM)
├── src/                    # バックエンド・分析モジュール
│   ├── auth.py             # ログイン認証・セッション管理
│   ├── database.py         # DB初期化・接続管理
│   ├── data_service.py     # スナップショット管理・データ登録
│   ├── metrics.py          # Burst Score, Citation per Year 計算
│   ├── openalex_client.py  # OpenAlex API 通信・照合
│   ├── pubmed_client.py    # PubMed E-utilities 通信
│   ├── analytics_service.py# 各画面用集計サービス
│   ├── exporter.py         # UTF-8 BOM CSV生成
│   └── ui/                 # 画面コンポーネント (6画面)
├── tests/                  # 単体テスト・検証スイート
├── run_dashboard.bat       # ワンクリック起動スクリプト
└── app.py                  # アプリケーションエントリポイント
```

## 3. 初期ログイン情報
- **Login ID**: `n-ogasawara`
- **Password**: `2020408`

※ パスワードはハッシュ化（SHA-256 + Salt）して検証され、平文では保持されません。

## 4. 起動方法

### A. オンライン公開URL（Cloudflare Tunnel）で起動（推奨）
`start_online.bat` をダブルクリックするだけで、インターネット経由でアクセス可能な専用ウェブURL（`https://xxxx.trycloudflare.com`）が発行されます。PCやスマホのブラウザから直接アクセスできます。

### B. ローカル専用で起動
`run_dashboard.bat` をダブルクリック、または以下のコマンドで起動します：
```powershell
cd internal_medicine_dashboard
streamlit run app.py --server.port 8502
```
ブラウザで `http://localhost:8502` にアクセスします。
