# 数式の復元

38.211 には 3 種類の数式が混在する。
リリースにより比率が異なる。

- OMML: Word 標準の数式 (Rel-19 に多い)
- OLE: MathType の埋め込み (Rel-15 に多い)
- 画像: WMF として貼られた数式 (表の中など)

## 解決順序 (equations.py)
1. data/equation_overrides.json (手動)
2. OMML: omml.py で LaTeX に変換
3. OLE: mtef.py で MTEF v3/v5 を解析
4. OLE: LibreOffice の MathML (mathml.py)
5. 画像: WMF 内の MTEF、なければ文字配置
6. 上記で不可なら画像リンク + 報告

LaTeX は validate_latex で構文を検査する。
括弧の不整合などは画像にフォールバックする。

## MathType (mtef.py)
- OLE の "Equation Native" ストリームを読む
- ヘッダ 28 バイトの後が MTEF
- 版 3 (Equation.3) と版 5 (DSMT*) に対応
- 版 3 の文字は 16 ビットで、実質 Unicode
- 版 3 のテンプレート番号は版 3 の仕様表
  (番号体系が版 5 と異なる) を内部で版 5
  相当に正規化する (_v3_tmpl)
- 版 3 の LSCRIPT(44) も右側の添字として扱う
- 版 3 の修飾記号 (EMBELL) の値は 16 ビット
- 上下限の順序は 主、下、上
- 縦積み (PILE) の左揃えは & で表現
- MT Extra の記号は表で変換 (点々など)

## 画像 (wmf.py)
- MathType の画像は AppsMFCC コメントに
  MTEF を持つことがある。あれば優先
- なければ ExtTextOut の文字と座標を読む
  - 基準線より下は下付き、上は上付き
  - Symbol フォントは symbolfont.py で変換
  - ~ ^ ¯ → は上付きアクセント
- 線の描画 (分数線・根号・上線) を含む画像は
  自動復元しない (誤りを防ぐため)

## LibreOffice (ole_math.py)
- docx を複製し、数式の前にマーカーを挿入
- Equation.3 に ProgID を統一して odt に変換
- マーカー直後の draw:object の MathML を採取
- 結果は cache/ole_mathml_<sha1>.json
- 主経路ではなく、MTEF 解析のフォールバック
- 既知の弱点: ダッシュ (m') の崩れ、
  左括弧のみの場合分けの括弧欠落

## 手動上書き
- キーは元データの sha1 (OLE は .bin、画像は
  wmf ファイル)。版をまたいで共通に効く
- 値は LaTeX 文字列
- 目視確認は tools/compare_equations.py
  tools/contact_sheet.py tools/show_wmf.py

## 検証の実績 (38.211 Rel-15〜19)
- 未解決の数式は 0 件
- 全ての一意な式が pdflatex で通る
- OLE は LibreOffice 結果と約 9 割が一致し、
  差分は主にダッシュ表記と括弧の扱い
  (差分は自前解析のほうが画像に近い)

## 既知の限界
- 元データの誤りはそのまま写す
  (例: イタリック指定の不統一)
- 字形の細かな差 (\varphi と \phi など)
- 上下の寄せ (aligned の揃え位置) は近似
