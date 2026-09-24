#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反向抽鬼牌 — 消融實驗（對應軟體測試的變異測試）
================================================
以基準引擎為底，一次關掉一條處理邏輯（不是關掉檢查），產生六個變體：

  M1 主動湊成對子：抽完當下的丟對子（含坍縮清到一對、手牌上限）
  M2 主動達成退出資格：抽完當下宣告退出
  M3 主動達成清空
  M4 被動達成退出資格：被抽後標記 pending
  M5 被動達成強制退出：被抽後標記 pending
  M6 被動達成清空：被抽後標記 pending

每個變體只把對應的判斷改成 `if False:`，其餘原始碼一字不動。
每個變體跑兩種測試：
  1. 構造測試：九個情境各 N 次（construct_test.py）
  2. 隨機對局：M 局，逐輪不變量、是否在上限內結束、與基準逐局結果相同的比例

  python3 ablation.py -e 反向抽鬼牌vC7_0919修正.py              # 全部
  python3 ablation.py -e 反向抽鬼牌vC7_0919修正.py --only M5    # 只跑一個
"""
import argparse, collections, os, random

import construct_test_v6 as CT
import invariant_per_turn as IV

GAME_CAP = 2000   # 變體可能走不完，給一個外部上限；撞到上限的局數另外報告

MUTANTS = {
    "M1": ("主動湊成對子（抽完當下丟對子）", [
        ("        # === 抽完牌當下：丟對子的決定 ===\n        if not drawer.exited and drawer.get_pairs()[0]:",
         "        # === 抽完牌當下：丟對子的決定 ===\n        if False:  # 消融 M1")]),
    "M2": ("主動達成退出資格（抽完當下宣告退出）", [
        ("        # === 主動達成（自己抽牌後當下）===\n        if not drawer.exited and drawer.has_exit_condition():",
         "        # === 主動達成（自己抽牌後當下）===\n        if False:  # 消融 M2"),
        ("            if drawer.has_exit_condition() and drawer.want_to_exit_now():\n                if self.do_voluntary_exit(drawer, reason=\"voluntary_declared\"):",
         "            if False:  # 消融 M2\n                if self.do_voluntary_exit(drawer, reason=\"voluntary_declared\"):")]),
    "M3": ("主動達成清空", [
        ("            elif len(rewards) == 0 and len(pairs) > 0 and len(singles) == 0:\n                print(f\"  🃏 {drawer.name} 主動達成清空！\")",
         "            elif False:  # 消融 M3\n                print(f\"  🃏 {drawer.name} 主動達成清空！\")")]),
    "M4": ("被動達成退出資格（標記 pending）", [
        ("        if target.has_exit_condition():\n            target.pending_exit = True",
         "        if False:  # 消融 M4\n            target.pending_exit = True")]),
    "M5": ("被動強制退出（當場退出）", [
        ("        if target.can_exit():\n            # [2026/09/22 v3] 被動強制退出不需等待",
         "        if False:  # 消融 M5\n            # [2026/09/22 v3] 被動強制退出不需等待")]),
    "M7": ("被動歸零（回合開始手牌為零時保底）", [
        ("        if drawer.is_hand_empty():\n            self._call_redistribution(drawer)\n\n        # 抽牌前只處理強制收斂",
         "        if False:  # 消融 M7\n            self._call_redistribution(drawer)\n\n        # 抽牌前只處理強制收斂")]),
    # [v4] 事前預期：關掉後 7a 只在「等待期間被選為抽牌對象」的那幾次不符；隨機對局約 6% 的局改變；不變量 0
    "M8": ("空手者被選中時提前保底", [
        ("        if target is not None and not target.exited and not target.hand:",
         "        if False:  # 消融 M8")]),
    "M6": ("被動達成清空（標記 pending）", [
        ("        if target.all_pairs_no_singles():\n            target.pending_clear = True",
         "        if False:  # 消融 M6\n            target.pending_clear = True")]),
}


def make_mutant(base_path, key):
    src = open(base_path, encoding="utf-8").read()
    for old, new in MUTANTS[key][1]:
        assert src.count(old) == 1, f"{key}: 找不到唯一的替換位置"
        src = src.replace(old, new)
    out = os.path.splitext(base_path)[0] + f"_消融{key}.py"
    open(out, "w", encoding="utf-8").write(src)
    return out


def random_games(path, n):
    """回傳：每局 (輪數, 分數) 的清單、不變量違規局數、撞到上限的局數"""
    m = IV.load_engine(path)
    m.TURN_CAP = GAME_CAP
    ck = IV.Checker()
    IV.instrument(m, ck)
    results = []
    capped = 0
    for seed in range(n):
        ck.seed = seed
        random.seed(seed)
        g = m.GameEngine()
        g.run_game()
        if g.turn_count > GAME_CAP:
            capped += 1
        results.append((g.turn_count, tuple(p.score for p in g.players)))
    inv = {k: len(v) for k, v in ck.games.items()}
    return results, inv, capped


def construct(path, n):
    m = CT.load_engine(path)
    m.TURN_CAP = GAME_CAP
    out = []
    for idx, sc in enumerate(CT.SPEC):
        bad = 0
        firsts = collections.Counter()
        for i in range(n):
            (ok, where), _ = CT.run_once(m, sc, (idx + 1) * 100000 + i)
            if ok is None:
                firsts["（不判定）" + where] += 1
            elif not ok:
                bad += 1
                firsts[where] += 1
        out.append((idx + 1, CT.SPEC[sc][0], bad, firsts))
    return out


def report(label, path, n_ct, n_games, base_results):
    print("=" * 66)
    print(label)
    print("=" * 66)
    res, inv, capped = random_games(path, n_games)
    same = sum(a == b for a, b in zip(res, base_results)) if base_results else n_games
    turns = [t for t, _ in res]
    print(f"隨機對局 {n_games:,} 局：平均輪數 {sum(turns) / len(turns):.1f}   "
          f"撞到 {GAME_CAP} 輪上限 {capped} 局   與基準逐局相同 {same / n_games * 100:.1f}%")
    print(f"  逐輪不變量（違規局數）守恆 {inv['I1']}・手牌上限 {inv['I2']}・坍縮後清對子 {inv['I3']}")
    print(f"構造測試（每個情境 {n_ct} 次，不符次數）")
    for num, name, bad, firsts in construct(path, n_ct):
        extra = "；".join(f"{k} {v}" for k, v in firsts.most_common())
        print(f"  {num} {name:<22} {bad:>3}" + (f"   第一個不符：{extra}" if extra else ""))
    print()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-e", "--engine", required=True, help="基準引擎")
    ap.add_argument("-n", type=int, default=100, help="構造測試每個情境次數")
    ap.add_argument("-g", "--games", type=int, default=20000, help="隨機對局局數")
    ap.add_argument("--only", default=None, help="只跑某一個變體，例如 M5")
    args = ap.parse_args()

    base_res, _, _ = random_games(args.engine, args.games)
    keys = [args.only] if args.only else list(MUTANTS)
    if not args.only:
        report(f"基準 {os.path.basename(args.engine)}", args.engine, args.n, args.games, base_res)
    for k in keys:
        path = make_mutant(args.engine, k)
        report(f"{k} 關閉：{MUTANTS[k][0]}", path, args.n, args.games, base_res)


if __name__ == "__main__":
    main()
