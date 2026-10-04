# 参照 TS/TR と一括取得

38.211〜38.214 (Rel-19) の「2 References」と
本文の引用を集計し、RAN1 対応で参照すべき
仕様を選んだ。一覧は
`data/recommended_specs.json` が正本。

## core: RAN1 の物理層仕様
- 38.201 38.202 38.211 38.212
- 38.213 38.214 38.215

## cross_wg: 他 WG だが引用が多い
- 38.321 (MAC) 38.331 (RRC)
- 38.306 (UE 能力) 38.133 (RRM, RAN4)
- 38.101-1/-2/-3/-4/-5 (UE RF, RAN4)
- 38.104 (BS RF) 37.213 (共有スペクトラム)
- 38.300 (全体説明)

## feature: 機能ごとに参照
- 38.304 (Idle) 38.108 (衛星 BS)
- 38.106 (リピータ)
- 38.305 / 37.355 (測位)
- 38.473 (F1AP) 38.423 (XnAP)
- 36.211 36.212 36.213 36.321 (LTE 共存)
- 23.287 23.586 (V2X, サイドリンク)

## reports: TR
- TR 21.905 (用語集)
- TR 38.822 (UE feature list)

## 一括取得: tools/download_specs.py
- 3GPP FTP の `Specs/latest/Rel-N/` から取得
- Rel-15 から FTP 上の最新 Release まで
- 各 Release の最新版のみ (自動で最新を検出)
- 取得済み (docx / doc / 同名の dir) は除外
- zip は展開後に残さない
- 入れ子の zip (Band Combinations) は無視
- 展開先は既定で `TS_docx/`
  - 1ファイルの zip は直下に展開
  - 分割 docx の zip は `<名前>/` に展開

```
python3 tools/download_specs.py --dry-run
python3 tools/download_specs.py
python3 tools/download_specs.py --specs 38.321
python3 tools/download_specs.py --tiers core
```

## 変換
- docx は `python3 -m ts_converter <docx>`
- `.doc` は LibreOffice で docx にしてから
- 分割 docx はディレクトリごと指定する
- 未解決の数式 (WMF 画像のまま) が
  36.212, 36.213, 38.133 に多い

## 注意
- 既定の User-Agent は 403 になるため偽装する
- 存在しない Release は 403 が返る
- 他 Release に新版が無い仕様は取得されない
  (例: 38.211 の Rel-20 は未公開)
- `TS_docx/*.docx` を全件変換する場合は、
  RF や RRM の巨大な仕様も対象になる
- 38.822 は TS と書かれるが実体は TR
