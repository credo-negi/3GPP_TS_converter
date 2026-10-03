# 3GPP TS converter

3GPP の技術仕様書 (TS, docx) を次の形式に
変換する Python ツール。

- Markdown: 節ごとに別ファイル、1文1行
- xlsx: 1文1セル、表はセル対応

LLM に渡す文脈を小さくし、文単位で扱えること
を目的とする。

## 特徴
- 数式を LaTeX に復元
  - Word 数式 (OMML)
  - MathType の OLE オブジェクト
  - WMF 画像として貼られた数式
- 表は結合セルを保持 (xlsx) / 展開 (md)
- リリース間の差分比較がしやすい出力

## 必要環境
- Python 3.10 以上
- pip install -r requirements.txt
- LibreOffice (画像変換・数式の補助)
- pdflatex (検証ツールのみ)

## クイックスタート
```
PYTHONPATH=src python3 -m ts_converter \
  TS_docx/38211-j50.docx
```
出力先
- md/38211/Rel-19_V19.5.0/
- xlsx/38211_Rel-19_V19.5.0.xlsx

## ファイル名と版
- 38211-j50 の j は主版 (a=10 ... j=19)
- 例: fa0=Rel-15, ga0=16, hb0=17,
  ia0=18, j50=19

## ドキュメント
- CLAUDE.md 開発者向け要約
- docs/USAGE.md 使い方
- docs/ARCHITECTURE.md 構成
- docs/OUTPUT_FORMAT.md 出力仕様
- docs/EQUATIONS.md 数式の復元
- docs/TESTING.md テスト

## 注意
- docx / xlsx / 生成 md は push しない
  (.gitignore で除外済み)
