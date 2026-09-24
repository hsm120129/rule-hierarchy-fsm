# -*- coding: utf-8 -*-
"""
run_demo.py — 以 vC7 實際跑一局，產出事件擷取層的兩層紀錄

跑法：python3 run_demo.py
輸出：history.json（歷史層事件序列）、snapshots.json（快照層狀態序列）

vC7 內建五個事件觸發點（抽牌／湊對丟棄／保底轉化／退出／環境坍縮），
預設不記錄；本腳本把 event_capture.RECORDER 掛上引擎後才開始記錄，
不需要另外維護一份插入記錄呼叫的引擎副本。
"""
import argparse
import contextlib
import io
import os
import random

from event_capture import RECORDER
from _common import load_engine, HERE

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("-e", "--engine", default=None)
ap.add_argument("--verbose", action="store_true", help="顯示遊戲過程")
args = ap.parse_args()

engine, name = load_engine(args.engine, module_name="engine_demo")
engine.RECORDER = RECORDER

random.seed(args.seed)
game = engine.GameEngine()
if args.verbose:
    game.run_game()
else:
    with contextlib.redirect_stdout(io.StringIO()):
        game.run_game()

RECORDER.dump(os.path.join(HERE, "history.json"), os.path.join(HERE, "snapshots.json"))

s = RECORDER.summary()
print("=" * 55)
print("📦 [事件擷取層] 落地結果")
print("=" * 55)
print(f"  引擎：{name}　seed = {args.seed}")
print(f"  輪數：{game.turn_count}")
print(f"  歷史層總事件數：{s['total_events']}")
print(f"  快照層總快照數：{s['total_snapshots']}")
print("  各事件類型計數：")
for k in ("DRAW", "DISCARD_PAIRS", "REDISTRIBUTION", "EXIT", "COLLAPSE"):
    print(f"    - {k}: {s['by_event_type'].get(k, 0)}")
print("  最終得分：" + "、".join(f"{p.name} {p.score} 分" for p in game.players))
