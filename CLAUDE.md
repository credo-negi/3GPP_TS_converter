# CLAUDE.md

3GPP TS (docx) を Markdown と xlsx に変換する
Python プロジェクト。LLM への入力文脈を小さく
するための前処理が目的。

## 目的と要件
- 入力: `TS_docx/` の docx (例: 38.211 Rel-15〜19)
- md: 節ごとに別ファイル、1文を1行に対応
- xlsx: 1文を1セルに対応
- 数式は LaTeX へ限界まで復元する
  - OMML、MathType(OLE)、WMF 画像を処理
  - 復元できない場合のみ画像リンクで残す
- 実行テストは 38.211 の Rel-15〜19 で行う

## Git の運用ルール
- ローカルのみ。リモートリポジトリは無い
- `TS_docx/*.docx`, `xlsx/*.xlsx`, `md/` 配下の
  生成物は `.gitignore` 済み。push しない
- コミットは依頼があったときだけ行う

## ディレクトリ
- `src/ts_converter/` 変換ライブラリ本体
- `tools/` 検証・補助スクリプト
- `tests/` unittest (標準ライブラリのみ)
- `data/` 手動の数式上書き (JSON)
- `docs/` 詳細ドキュメント
- `TS_docx/` 入力 docx (git 管理外)
- `md/` 出力 Markdown (リリース別, git 管理外)
- `xlsx/` 出力 xlsx (git 管理外)
- `cache/` LibreOffice 変換結果 (git 管理外)

## よく使うコマンド
- 変換: `PYTHONPATH=src python3 -m ts_converter
  TS_docx/38211-j50.docx`
- 全件: 上記に `TS_docx/*.docx` を渡す
- テスト: `python3 -m unittest discover
  -s tests -t .`
- 数式の構文検査: `python3 tools/check_latex.py
  md/38211/Rel-19_V19.5.0`
- 文書の検査: `python3 tools/check_docs.py`

## ドキュメント規約 (必須)
- 各 .md は 200 行以内、1行 50 文字以内
- 文字数はプログラムで数える
  (`tools/check_docs.py、len()` で数える)
- .md を作成・編集したら必ず実行して確認する
- 検査対象: `CLAUDE.md` `README.md` `docs/**/*.md`
- 生成物の `md/` 配下は対象外

## コーディング規約
- 既存コードの命名・コメント密度に合わせる
- 新しい数式変換は `tests/` に例を追加する
- LaTeX 文字列は `strip()` ではなく
  `latex_util.trim()` で整える (`\` の残り防止)

## 数式復元の方針 (詳細は `docs/EQUATIONS.md`)
1. `data/equation_overrides.json` (手動)
2. OMML を自前で LaTeX へ変換
3. MathType の MTEF v3/v5 を自前で解析
4. LibreOffice の MathML (フォールバック)
5. WMF の文字レコードから位置を復元
6. 以上で不可なら画像として残し報告する
- 目視確認: `tools/compare_equations.py`
- 手動で直したら overrides に sha1 で登録

## 参照
- `docs/ARCHITECTURE.md` 構成と処理の流れ
- `docs/USAGE.md` 使い方
- `docs/OUTPUT_FORMAT.md` 出力仕様
- `docs/EQUATIONS.md` 数式の復元
- `docs/TESTING.md` テストと検証
