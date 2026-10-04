# 使い方

## 準備
```
pip install -r requirements.txt
```
- LibreOffice は `/Applications/LibreOffice.app`
  を自動検出する (soffice が PATH でも可)
- docx は `TS_docx/` に置く (git 管理外)

## 変換
```
cd 3GPP_TS_converter
PYTHONPATH=src python3 -m ts_converter \
  TS_docx/38211-fa0.docx
```
複数ファイルを続けて指定できる。
分割 docx (36.211, 38.101-1, 38.133 等) は
`TS_docx/<名前>/` のディレクトリを指定する。
パーツを `cache/merged/` で1本に結合して変換。

## オプション
- `--md-dir` md の出力ルート (既定 `md/`)
- `--xlsx-dir` xlsx の出力ルート (既定 `xlsx/`)
- `--cache-dir` 変換キャッシュ (既定 `cache/`)
- `--overrides` 数式の手動上書き JSON
- `--no-md` md を出力しない
- `--no-xlsx` xlsx を出力しない

## 出力先
- `md/<仕様>/Rel-<N>_V<版>/*.md`
  (仕様は枝番付き。例 `38101-2`)
- `md/<仕様>/Rel-<N>_V<版>/images/`
- `md/<仕様>/Rel-<N>_V<版>/_meta/`
- `xlsx/<仕様>_Rel-<N>_V<版>.xlsx`

## 実行結果の見方
標準出力の JSON に次が含まれる。
- `equations`: 数式の復元方法ごとの件数
- `equation_issues`: 未解決・警告の件数
- `seconds`: 所要時間 (キャッシュ有で数秒)

`_meta/equation_issues.json` に詳細が出る。
0 件が正常。1件以上ならば数式を確認する。

## 数式が復元できなかったとき
1. `tools/show_wmf.py` で元画像を確認する
2. LaTeX を手で書く
3. `data/equation_overrides.json` に
   画像または OLE の sha1 をキーに登録する
4. 再実行して issues が 0 になるか確認する

## 補助ツール (tools/)
- `check_latex.py` 全数式を `pdflatex` で検査
- `compare_equations.py` 元画像と LaTeX を並べる
- `contact_sheet.py` WMF 画像の一覧を作る
- `show_wmf.py` 画像を1枚 PNG にする
- `check_docs.py` ドキュメントの行数・文字数
- `download_specs.py` 参照 TS/TR の一括取得
  (`docs/REFERENCED_SPECS.md`)

## キャッシュ
- LibreOffice 変換は docx の sha1 で保存
- 削除しても再生成される (数十秒かかる)
