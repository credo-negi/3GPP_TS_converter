# アーキテクチャ

## 処理の流れ
1. docx を zip として開き document.xml を解析
2. 段落・表・数式を中間表現 (IR) に変換
3. 数式は EquationResolver が LaTeX 化
4. IR を md / xlsx に書き出す

```
docx -> docx_parser -> IR -> md_writer
                         \-> xlsx_writer
          ^
          |
     equations (OMML/MTEF/WMF/LO)
```

## モジュール (src/ts_converter/)
- cli.py コマンドライン入口
- docx_parser.py docx から IR を作る
- ir.py 中間表現 (Seg, Para, Table, ...)
- sentences.py 文分割 (数式は不可分)
- render.py 文の描画 (md/xlsx 共通)
- md_writer.py 節ごとの md と画像の出力
- xlsx_writer.py 1文1セルの xlsx 出力

## 数式関連のモジュール
- equations.py 数式の解決順序と検証
- omml.py OMML を LaTeX へ
- mtef.py MathType MTEF v3/v5 の解析
- mathml.py MathML を LaTeX へ (LO 用)
- ole_math.py LibreOffice で OLE を変換
- wmf.py WMF の解析 (MTEF/文字配置)
- symbolfont.py Symbol フォントの対応表
- latex_util.py 文字変換と整形の共通関数

## 中間表現 (ir.py)
- Seg: text / math / sup / sub / image
- Para: text, bullet, note, def, caption
- DisplayMath: 独立行の数式
- ImageBlock: 図
- Table: Cell の二次元配列
- Section: 見出し1つ分 (level, number)
- Document: Section を文書順に平坦化

## 設計上の判断
- 見出し番号は本文の先頭テキストから取る
- 節の粒度は全ての見出し (最下層まで)
- TOC 段落は読み飛ばし、索引は自前で作る
- 数式を含む文でも文境界を壊さない
  (数式を私用領域の1文字に置換して分割)
- LibreOffice は外部プロセスで呼び、結果を
  cache/ に保存して再利用する

## 拡張のしかた
- 新しい段落スタイル: docx_parser.make_para
- 新しい出力形式: IR を読む writer を追加
- 別の TS: ファイル名規則は parse_filename
