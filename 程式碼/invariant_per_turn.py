#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反向抽鬼牌 — 逐輪不變量驗證
============================
每一輪結束後（另含開局清洗後、明牌期後）檢查三項：

  I1 獎勵牌守恆：未退出者手上的獎勵牌 ＋ 已退出者帶走的分數，恰為 {10,8,4,2}
  I2 手牌上限：任何未退出玩家手牌達 5 張時，手上不得仍有對子
  I3 坍縮後清對子：坍縮後，當輪抽牌者在該輪結束時不得持有 2 對以上

只包裝引擎的 setup / open_round / run_turn，不改任何處理邏輯。
種子 0 到 N-1。

    python3 invariant_per_turn.py -e 反向抽鬼牌vC7.py
    python3 invariant_per_turn.py -e 反向抽鬼牌vC7.py -n 100000 --no-cap
    python3 invariant_per_turn.py -e 反向抽鬼牌vC7.py --no-collapse
"""
import argparse
import importlib.util
import os
import random

REWARDS = [2, 4, 8, 10]
NAMES = {"I1": "獎勵牌守恆（含退出者）", "I2": "手牌上限", "I3": "坍縮後清對子"}


def load_engine(path):
    spec = importlib.util.spec_from_file_location("engine_under_test", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.print = lambda *a, **k: None      # 關掉引擎輸出，不影響亂數
    return m


class Checker:
    def __init__(self):
        self.count = {k: 0 for k in NAMES}      # 違規次數
        self.games = {k: set() for k in NAMES}  # 出現違規的種子
        self.first = {}                          # 第一個反例
        self.checks = 0
        self.seed = None

    def flag(self, key, g, where):
        self.count[key] += 1
        self.games[key].add(self.seed)
        self.first.setdefault(key, (self.seed, g.turn_count, where))

    def check(self, g, where, drawer=None):
        self.checks += 1
        held = [c.points for p in g.players if not p.exited
                for c in p.hand if c.is_reward]
        taken = [p.score for p in g.players if p.exited]
        if sorted(held + taken) != REWARDS:
            self.flag("I1", g, where)
        for p in g.players:
            if not p.exited and len(p.hand) >= 5 and p.get_pairs()[0]:
                self.flag("I2", g, f"{where}:{p.name}")
        if (drawer is not None and g.disaster_triggered and not drawer.exited
                and len(drawer.get_pairs()[0]) >= 2):
            self.flag("I3", g, f"{where}:{drawer.name}")


def instrument(engine, ck):
    E = engine.GameEngine
    setup, open_round, run_turn = E.setup, E.open_round, E.run_turn

    def w_setup(self):
        setup(self)
        ck.check(self, "開局清洗後")

    def w_open(self):
        open_round(self)
        ck.check(self, "明牌期後")

    def w_turn(self, drawer, *a, **k):
        r = run_turn(self, drawer, *a, **k)
        ck.check(self, f"第{self.turn_count}輪", drawer)
        return r

    E.setup, E.open_round, E.run_turn = w_setup, w_open, w_turn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-e", "--engine", required=True)
    ap.add_argument("-n", "--games", type=int, default=100000)
    ap.add_argument("--no-cap", action="store_true")
    ap.add_argument("--no-collapse", action="store_true")
    args = ap.parse_args()

    engine = load_engine(args.engine)
    if args.no_cap:
        engine.TURN_CAP = 10 ** 9
    if args.no_collapse:
        engine.COLLAPSE_TURN = 10 ** 9
    ck = Checker()
    instrument(engine, ck)

    turns = 0
    for seed in range(args.games):
        ck.seed = seed
        random.seed(seed)
        g = engine.GameEngine()
        g.run_game()
        turns += g.turn_count

    print("=" * 60)
    print(f"引擎   {os.path.basename(args.engine)}")
    print(f"局數   {args.games:,}（種子 0–{args.games - 1}）  "
          f"坍縮 {'關' if args.no_collapse else '第 20 輪'}  "
          f"上限 {'無' if args.no_cap else 200}")
    print(f"檢查點 {ck.checks:,}（總輪數 {turns:,}）")
    print("-" * 60)
    for k, name in NAMES.items():
        line = f"{k} {name:<14} 違規 {ck.count[k]:>7,} 次 ／ {len(ck.games[k]):>6,} 局"
        if k in ck.first:
            s, t, w = ck.first[k]
            line += f"   首例 seed {s}（{w}）"
        print(line)


if __name__ == "__main__":
    main()
