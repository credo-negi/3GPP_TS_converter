# テストと検証

## 単体・結合テスト
```
python3 -m unittest discover -s tests -t .
```
- pytest 不要 (標準 unittest のみ)
- docx が無い環境では結合テストを自動で skip

## テストの構成 (tests/)
- test_sentences.py 文分割
- test_latex_util.py 文字変換・検証関数
- test_omml.py OMML の主要構造
- test_mtef.py 合成した MTEF v3/v5 を解析
- test_writers.py md / xlsx の出力
- test_integration.py 実 docx の不変条件

## 結合テストの確認項目
- 数式の未解決・警告が 0 件
- 全ての数式が構文的に正しい
- 見出し数が目次と一致 (H6 を加味)
- 最上位の節 1〜7 と Annex A が存在
  (節 8 は Rel-16 以降のみ)
- 3.2 Symbols に定義が 20 件以上

## 数式の追加検証 (tools/)
- check_latex.py md出力の全数式を pdflatex に通す
  `python3 tools/check_latex.py md/38211/Rel-19*`
- compare_equations.py
  元の数式画像と LaTeX 描画を並べた PNG を作る
  `--select complex|random --count 16`
- contact_sheet.py
  WMF 画像の LaTeX 復元結果を一覧にする

## 回帰確認の手順
1. 全リリースを変換する
2. equation_issues が全て 0 であること
3. tools/check_latex.py のエラーが 0 であること
4. unittest が全て通ること
5. tools/check_docs.py が OK であること

## ドキュメントの検査
```
python3 tools/check_docs.py
```
- 200 行以内、1行 50 文字以内
- 文字数は len() (Unicode のコードポイント数)
