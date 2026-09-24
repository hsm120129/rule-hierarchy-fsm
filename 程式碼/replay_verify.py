# -*- coding: utf-8 -*-
"""
事件擷取層交叉驗證：以歷史層事件重播，逐一重建快照層並比對。

驗證的命題
----------
快照層與歷史層各自獨立記錄，但描述的是同一個系統。若架構正確，
任一時點的完整局面都應能單靠「前一張快照之後的歷史事件」推進出來，
不需要再讀快照層本身。

作法
----
兩層紀錄共用同一個遞增序號（event_id／snapshot_id），據此交錯排序。
遇到事件就套用到重播狀態上；遇到快照就把重播狀態與該快照逐位玩家
比對（手牌集合與退出狀態）。初始狀態僅取自第一張快照，之後完全不再
讀快照層。套用的事件：DRAW、DISCARD_PAIRS、REDISTRIBUTION、EXIT。

使用方式
--------
    python3 run_demo.py
    python3 replay_verify.py

基準結果：以 vC7、seed = 42 執行後，數字見 run_demo.py 與本檔輸出。
（舊版 vC6.1 的 65 事件／44 快照／172 比對點已不適用。）

作者：許軒銘（Mac Hsu）
"""
import argparse
import json
import os
import sys

# Windows 繁中環境（cp950）下，把輸出導向檔案時，部分符號無法編碼會中斷。
# 導向檔案時一律以 UTF-8 寫出；直接顯示在終端機時，無法顯示的字元以問號替代。
if hasattr(sys.stdout, "reconfigure"):
    if sys.stdout.isatty():
        sys.stdout.reconfigure(errors="replace")
    else:
        sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description="快照層／歷史層交叉驗證")
ap.add_argument("--history", default=os.path.join(HERE, "history.json"))
ap.add_argument("--snapshots", default=os.path.join(HERE, "snapshots.json"))
args = ap.parse_args()

H = json.load(open(args.history, encoding="utf-8"))
S = json.load(open(args.snapshots, encoding="utf-8"))

timeline = ([("E", e.get("event_id", e["ts"]), e) for e in H] +
            [("S", s.get("snapshot_id", s["ts"]), s) for s in S])
timeline.sort(key=lambda x: x[1])

hands, exited, started = {}, {}, False
ok = bad = checked = 0
fails = []


def apply(e):
    t, d = e["event_type"], e["payload"]
    if t == "DRAW":
        hands[d["target"]].remove(d["card"])
        hands[d["drawer"]].append(d["card"])
    elif t == "REDISTRIBUTION":
        hands[d["target"]].remove(d["card"])
        hands[d["player"]].append(d["card"])
    elif t == "DISCARD_PAIRS":
        for c in d["discarded_cards"]:
            hands[d["player"]].remove(c)
    elif t == "EXIT":
        hands[d["player"]].clear()
        exited[d["player"]] = True


for kind, _key, rec in timeline:
    if kind == "S":
        if not started:
            hands = {p["name"]: list(p["hand"]) for p in rec["state"]["players"]}
            exited = {p["name"]: p["exited"] for p in rec["state"]["players"]}
            started = True
            continue
        checked += 1
        for p in rec["state"]["players"]:
            n = p["name"]
            if sorted(p["hand"]) == sorted(hands[n]) and p["exited"] == exited[n]:
                ok += 1
            else:
                bad += 1
                fails.append((rec["label"], n, sorted(p["hand"]), sorted(hands[n])))
    elif started:
        apply(rec)

total = ok + bad
print("=" * 62)
print("事件擷取層 — 快照層／歷史層交叉驗證")
print("=" * 62)
print(f"歷史層事件   {len(H)} 筆")
print(f"快照層快照   {len(S)} 筆（首張作為初始狀態，其餘 {checked} 張納入比對）")
print(f"比對點       {total} 個（每張快照 × 每位玩家的手牌與退出狀態）")
print(f"吻合         {ok}（{ok / max(1, total) * 100:.2f}%）")
print(f"不吻合       {bad}")
for f in fails[:5]:
    print(f"  ✗ {f[0]} / {f[1]}\n     快照 {f[2]}\n     重播 {f[3]}")
if bad == 0 and total > 0:
    print()
    print("結論：每一張快照都能單靠歷史層事件推進重建，兩層獨立記錄且完全一致。")
sys.exit(1 if bad else 0)
