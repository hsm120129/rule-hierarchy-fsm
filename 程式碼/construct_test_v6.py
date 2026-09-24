#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反向抽鬼牌 — 構造測試 0922v6（清不清空由玩家決定：情境 3 固定積極型、新增 3b 保守型；7a 加入空手者被選中時當場保底；被動強制退出改為當場退出；刪除 7b；新增情境 7a、7b 被動歸零；預期依作者確認的接續規則改寫；README v5 六組主被動局面，拆成九個情境）
============================================================
每個情境跑 N 次（預設 100）。每一次都完整走一條預期順序，任何一步不符就算一次不符，
並記下第一個不符的步驟。同時每輪檢查不變量（守恆含退出者、手牌上限、坍縮後清對子）。

觸發那一次抽牌固定「A 抽 B 的指定那張」；表中固定的條件之外，其餘維度隨機：
其他人的傾向、獎勵牌面額與分配、B 坐在 A 的哪一側、是否坍縮。
觸發之後整局照引擎自己的流程跑完。

  python3 construct_test.py -e 反向抽鬼牌vC7_0919修正.py
"""
import argparse, collections, importlib.util, os, random

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
PERSONALITIES = ["aggressive", "conservative", "balanced", "random"]
POINTS = [10, 8, 4, 2]


# ---------------------------------------------------------------- 引擎載入
class RandomProxy:
    """只在觸發那一次抽牌強制方向與被抽的牌，其餘全部交給 random。"""
    def __init__(self):
        self.force_dir = None
        self.force_card = None

    def choice(self, seq):
        seq = list(seq)
        if self.force_dir is not None and seq == [1, -1]:
            v, self.force_dir = self.force_dir, None
            return v
        if self.force_card is not None and any(c is self.force_card for c in seq):
            v, self.force_card = self.force_card, None
            return v
        return random.choice(seq)

    def __getattr__(self, name):
        return getattr(random, name)


def load_engine(path):
    spec = importlib.util.spec_from_file_location("engine_ct", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.print = lambda *a, **k: None
    m.TURN_CAP = 10 ** 9
    m.random = RandomProxy()
    return m


class Builder:
    """每個點數最多用一次：跨兩人各一張（跨人對），或同一人兩張（手上一對）。
    場上每個點數張數皆為偶數，保證不會出現永久單張。"""
    def __init__(self, m):
        self.m = m
        self.ranks = RANKS[:]
        random.shuffle(self.ranks)
        self.hands = {i: [] for i in range(4)}

    def _card(self, rank):
        return self.m.Card(random.choice(SUITS), rank)

    def cross(self, a, b):
        r = self.ranks.pop()
        ca, cb = self._card(r), self._card(r)
        self.hands[a].append(ca)
        self.hands[b].append(cb)
        return ca, cb

    def pair(self, a):
        r = self.ranks.pop()
        self.hands[a] += [self._card(r), self._card(r)]

    def rewards(self, counts):
        pts = POINTS[:]
        random.shuffle(pts)
        for seat, k in counts.items():
            for _ in range(k):
                p = pts.pop()
                self.hands[seat].append(self.m.Card('Reward', f'S{p}', is_reward=True, points=p))


def split_rewards(total, seats):
    """把 total 張獎勵牌隨機分給 seats。"""
    counts = {s: 0 for s in seats}
    for _ in range(total):
        counts[random.choice(seats)] += 1
    return counts



SPEC = {
    # 情境: (名稱, 固定傾向 {角色: 傾向}, 坍縮 True/False/None=隨機)
    "1a": ("湊成對子・達上限（保守型）", {"A": "conservative"}, False),
    "1b": ("湊成對子・未達上限（積極型）", {"A": "aggressive"}, False),
    "1c": ("湊成對子・坍縮後（積極型）", {"A": "aggressive"}, True),
    "2a": ("退出資格・持一張（積極型）", {"A": "aggressive"}, None),
    "2b": ("退出資格・持兩張（積極型）", {"A": "aggressive"}, None),
    "3":  ("主動清空（積極型，選擇清空）", {"A": "aggressive"}, None),
    "4":  ("被動退出資格（B 積極型）", {"B": "aggressive"}, None),
    "5":  ("被動強制退出（當場）", {}, None),
    "6":  ("被動清空（B 積極型）", {"B": "aggressive"}, None),
    "2c": ("退出資格・持一張（保守型、8 分以上）", {"A": "conservative"}, False),
    # [2026/09/22 新增] 被動歸零：與情境 3（主動清空→保底）相對
    "7a": ("被動歸零・最後一張單張被抽走", {}, None),
    "3b": ("主動達成清空條件（保守型，選擇保留）", {"A": "conservative"}, None),
}


def build(m, sc):
    b = Builder(m)
    A = 0
    B = random.choice([1, 3])
    others = [s for s in (1, 2, 3) if s != B]
    meta = {"A": A, "B": B, "dir": 1 if B == 1 else -1}
    if sc in ("1a", "1c"):          # A：獎勵＋r＋一對（4 張）→ 抽完 5 張兩對
        _, key = b.cross(A, B); b.pair(A)
        rw = {A: 1, **split_rewards(3, [B] + others)}
    elif sc == "1b":                # A：獎勵＋r＋1 張單張（3 張）→ 抽完 4 張、一對
        _, key = b.cross(A, B)
        b.cross(A, random.choice(others + [B]))
        rw = {A: 1, **split_rewards(3, [B] + others)}
    elif sc in ("2a", "2b", "2c"):        # A：r＋1 或 2 張獎勵牌
        _, key = b.cross(A, B)
        k = 2 if sc == "2b" else 1
        rw = {A: k, **split_rewards(4 - k, [B] + others)}
    elif sc in ("3", "3b"):         # A：r（＋一對），無獎勵牌
        _, key = b.cross(A, B)
        if random.random() < 0.5:
            b.pair(A)
        rw = {A: 0, **split_rewards(4, [B] + others)}
    elif sc == "4":                 # B：單張 s＋一對＋一張獎勵牌
        key, _ = b.cross(B, random.choice(others)); b.pair(B)
        rw = {B: 1, **split_rewards(3, [A] + others)}
    elif sc == "5":                 # B：單張 s＋一張獎勵牌
        key, _ = b.cross(B, random.choice(others))
        rw = {B: 1, **split_rewards(3, [A] + others)}
    elif sc == "7a":                # B：只有一張普通單張，無獎勵牌
        key, _ = b.cross(B, random.choice([A] + others))
        rw = {B: 0, **split_rewards(4, [A] + others)}
    elif sc == "7b":                # B：只剩一張獎勵牌（已被動達成強制退出、等待中）
        key = None
        rw = {B: 1, **split_rewards(3, [A] + others)}
    elif sc == "6":                 # B：單張 s＋1–2 對，無獎勵牌
        key, _ = b.cross(B, random.choice(others))
        for _ in range(random.randint(1, 2)):
            b.pair(B)
        rw = {B: 0, **split_rewards(4, [A] + others)}
    b.rewards(rw)
    if sc == "7b":
        key = [c for c in b.hands[B] if c.is_reward][0]
        meta["b_card"] = key.points
    if sc == "2c":                   # 保守型只有持 8 分以上才會宣告退出
        hi = random.choice([8, 10])
        mine = [x for x in b.hands[A] if x.is_reward][0]
        if mine.points != hi:
            for _s in range(4):
                for c in b.hands[_s]:
                    if c.is_reward and c.points == hi:
                        c.points, mine.points = mine.points, hi
                        c.rank, mine.rank = f'S{c.points}', f'S{hi}'
                        break
    for s in range(4):
        if sc == "7b" and s == B:
            continue                 # 7b 的 B 手上只能有那張獎勵牌
        while not [c for c in b.hands[s] if not c.is_reward]:
            b.cross(s, random.choice([o for o in (1, 2, 3) if o != s and o != B] or [2]))
    meta["key"] = key
    return b.hands, meta


def start_state_ok(m, hands, meta):
    """起始局面要合法：手牌達 5 張不得有對子；觸發者以外的人不處在退出／清空條件上。"""
    for s, h in hands.items():
        p = m.Player("x")
        p.hand = h
        pairs, singles = p.get_pairs()
        if len(h) >= 5 and pairs:
            return False
        if s in (meta["A"], meta["B"]):
            continue
        rewards = p.get_reward_cards()
        if p.can_exit() or (len(rewards) == 1 and len(pairs) == 1 and not singles):
            return False
        if not rewards and pairs and not singles:
            return False
    return True


# ---------------------------------------------------------------- 事件紀錄
def neighbor(g, seat, direction):
    n = len(g.players)
    for k in range(1, n):
        q = (seat + direction * k) % n
        if not g.players[q].exited:
            return q
    return None


def instrument(m, g, log):
    seat = {p.name: i for i, p in enumerate(g.players)}
    phase = {"v": None}
    E = type(g)

    def wrap_game(name, before=None, after=None):
        orig = getattr(E, name)
        def f(self, *a, **k):
            if before: before(self, *a, **k)
            r = orig(self, *a, **k)
            if after: after(self, r, *a, **k)
            return r
        setattr(g, name, f.__get__(g))

    def t_before(self, drawer, *a, **k):
        phase["v"] = "pre"
        log.append(dict(ev="TURN", who=seat[drawer.name], tc=self.turn_count,
                        pe=drawer.pending_exit, pc=drawer.pending_clear,
                        dir=self.direction,
                        ce=drawer.can_exit(), hec=drawer.has_exit_condition(),
                        ap=drawer.all_pairs_no_singles(), emp=drawer.is_hand_empty()))
    def t_after(self, r, drawer, *a, **k):
        log.append(dict(ev="TURN_END", who=seat[drawer.name], tc=self.turn_count,
                        dir=self.direction, exited=drawer.exited))
        phase["v"] = None
    wrap_game("run_turn", t_before, t_after)

    def drawn(self, target):
        phase["v"] = "post"
        log.append(dict(ev="DRAW", target=seat[target.name]))
    orig_pass = E._check_passive_after_drawn
    def pas(self, target):
        drawn(self, target)
        r = orig_pass(self, target)
        log.append(dict(ev="PASSIVE", target=seat[target.name],
                        pe=target.pending_exit, pc=target.pending_clear, exited=target.exited))
        return r
    g._check_passive_after_drawn = pas.__get__(g)

    def red_before(self, player):
        cands = [(i, p) for i, p in enumerate(self.players)
                 if not p.exited and p is not player and p.get_reward_cards()]
        if player.is_hand_empty() and cands:
            best = max(cands, key=lambda ip: (len(ip[1].get_reward_cards()),
                                              sum(c.points for c in ip[1].get_reward_cards())))
            key = (len(best[1].get_reward_cards()), sum(c.points for c in best[1].get_reward_cards()))
            ok = [i for i, p in cands if (len(p.get_reward_cards()),
                                           sum(c.points for c in p.get_reward_cards())) == key]
            self._ct_red = (seat[player.name], ok, {i: len(p.get_reward_cards()) for i, p in cands})
        else:
            self._ct_red = None
    def red_after(self, r, player):
        info = getattr(self, "_ct_red", None)
        if info:
            victim = [i for i, p in enumerate(self.players)
                      if not p.exited and p is not player
                      and len(p.get_reward_cards()) < info[2].get(i, 0)]
            log.append(dict(ev="REDIST", who=info[0], expect=info[1],
                            victim=victim[0] if victim else None, phase=phase["v"]))
    wrap_game("redistribution", red_before, red_after)

    orig_exit = E.do_exit
    def ex(self, player, *a, **k):
        was = player.exited
        r = orig_exit(self, player, *a, **k)
        if player.exited and not was:
            log.append(dict(ev="EXIT", who=seat[player.name], phase=phase["v"]))
        return r
    g.do_exit = ex.__get__(g)

    orig_vol = E.do_voluntary_exit
    def vol(self, player, *a, **k):
        phase["declaring"] = True
        try:
            r = orig_vol(self, player, *a, **k)
        finally:
            phase["declaring"] = False
        log.append(dict(ev="DECLARE", who=seat[player.name], ok=r, phase=phase["v"]))
        return r
    g.do_voluntary_exit = vol.__get__(g)

    for p in g.players:
        for meth in ("discard_pairs", "discard_by_rule", "discard_to_one_pair"):
            if hasattr(p, meth):
                orig = getattr(p, meth)
                def d(*a, _o=orig, _p=p, _m=meth, **k):
                    before = len(_p.get_pairs()[0])
                    r = _o(*a, **k)
                    gone = before - len(_p.get_pairs()[0])
                    if gone:
                        log.append(dict(ev="DISCARD", who=seat[_p.name], n=gone,
                                        phase=phase["v"],
                                        how="declare" if phase.get("declaring") else _m))
                    return r
                setattr(p, meth, d)


# ---------------------------------------------------------------- 單次執行
def run_once(m, sc, rng_seed):
    random.seed(rng_seed)
    while True:
        hands, meta = build(m, sc)
        if start_state_ok(m, hands, meta):
            break
    name, fixed, coll = SPEC[sc]
    collapse = (random.random() < 0.5) if coll is None else coll
    A, B = meta["A"], meta["B"]
    meta["collapse"] = collapse
    pers = [None] * 4
    rest = PERSONALITIES[:]
    for role, p in fixed.items():
        pers[meta[role]] = p
        rest.remove(p)
    random.shuffle(rest)
    for i in range(4):
        if pers[i] is None:
            pers[i] = rest.pop()

    g = m.GameEngine()
    for i, p in enumerate(g.players):
        p.personality = pers[i]

    def setup():
        for i, p in enumerate(g.players):
            p.hand = hands[i]
        g.turn_count = 30 if collapse else 10
        g.disaster_triggered = collapse
        g.direction = meta["dir"]
        if sc == "7b":
            g.players[B].pending_exit = True   # 代表 B 先前已被動達成強制退出、正在等待
    def open_round():
        g._first_drawer = g.players[A]
        g._last_target = None
    g.setup, g.open_round = setup, open_round

    log = []
    instrument(m, g, log)
    m.random.force_dir = None if collapse else meta["dir"]
    m.random.force_card = meta["key"]

    snap = {}
    orig_passive = g._check_passive_after_drawn
    def passive_snap(target):
        if "post" not in snap:
            a = g.players[A]
            snap["post"] = dict(size=len(a.hand), pairs=len(a.get_pairs()[0]))
        return orig_passive(target)
    g._check_passive_after_drawn = passive_snap

    inv = collections.Counter()
    orig_turn = g.run_turn
    def turn(drawer, *a, **k):
        r = orig_turn(drawer, *a, **k)
        m.random.force_dir = None
        m.random.force_card = None
        held = [c.points for p in g.players if not p.exited for c in p.hand if c.is_reward]
        taken = [p.score for p in g.players if p.exited]
        if sorted(held + taken) != [2, 4, 8, 10]:
            inv["I1"] += 1
        for p in g.players:
            if not p.exited and len(p.hand) >= 5 and p.get_pairs()[0]:
                inv["I2"] += 1
        if g.disaster_triggered and not drawer.exited and len(drawer.get_pairs()[0]) >= 2:
            inv["I3"] += 1
        if "endA" not in snap:
            a, b = g.players[A], g.players[B]
            snap["endA"] = dict(exited=a.exited, pairs=len(a.get_pairs()[0]))
            snap["endB"] = dict(exited=b.exited, pe=b.pending_exit, pc=b.pending_clear)
        return r
    g.run_turn = turn
    g.run_game()
    return steps(sc, meta, log, snap), inv


# ---------------------------------------------------------------- 預期順序
def turns_of(log):
    """把紀錄切成每一輪：[(TURN, [events...], TURN_END), ...]"""
    out, cur = [], None
    for e in log:
        if e["ev"] == "TURN":
            cur = [e, []]
        elif e["ev"] == "TURN_END":
            out.append((cur[0], cur[1], e))
            cur = None
        elif cur is not None:
            cur[1].append(e)
    return out


def steps(sc, meta, log, snap):
    """依序檢查預期順序，回傳 (是否全部符合, 第一個不符的步驟名稱)；(None, 原因)＝不判定。
    [2026/09/22 v2] 預期依作者確認的規則改寫，改動三類：
      一、A 抽完留場 → 下一手由 A 的鄰座來抽 A（坍縮後固定為 -方向 側）。
      二、非保底退出（A 抽完退出、B 抽牌前退出）→ 下一位是退出者的鄰座（坍縮後固定為 -方向 側）。
          保底退出 → 下一位是被奪取者（原規則）。
      三、情境 4、5、6：B 在自己下一次輪到時才處理。等待期間若 B 被抽走牌：
          輪到時條件仍在 → 照原本處理；條件已破壞 → 不退出／不清空，照常抽牌。
          等待期間轉成另一種條件、或局在輪到 B 之前結束 → 不判定。
    [跑完第一次之後補的三處，執行前沒有寫下，另外標明]
      甲、「條件已破壞」只禁止抽牌前退出／清空；B 照常抽牌之後自己又達成條件而退出，是合法的主動達成。
          （第一次寫成整回合不得退出，是檢查寫錯。）
      乙、等待期間手牌被抽光 → 輪到時手牌歸零，依憲法 6 保底 → 強制退出 → 下一位是被奪取者。
          （第一次沒有列出這條路徑。）
      丙、退出之後局就結束、沒有下一位 → 「下一位」這一步不判定。"""
    A, B = meta["A"], meta["B"]
    T = turns_of(log)
    t0, ev0, end0 = T[0]
    nxt = T[1][0]["who"] if len(T) > 1 else None

    def ev(events, kind, **cond):
        return [e for e in events if e["ev"] == kind and all(e.get(k) == v for k, v in cond.items())]
    def own_discards(events, who):
        return [e for e in ev(events, "DISCARD", who=who) if e["how"] != "declare"]

    def next_is_neighbor(X, i):
        """第 i 回合的抽牌者是 X 的鄰座；坍縮後必須是 X 的 -方向 側。"""
        if len(T) <= i:
            return None     # 丙
        who = T[i][0]["who"]
        if who not in {_neighbor_from_log(X, 1, T, i), _neighbor_from_log(X, -1, T, i)}:
            return False
        return (not meta["collapse"]) or who == _neighbor_from_log(X, -T[i][0]["dir"], T, i)

    def next_after_A():
        if ev(ev0, "REDIST", who=A) and end0["exited"]:
            red = ev(ev0, "REDIST", who=A)
            return nxt == red[0]["victim"]
        if end0["exited"]:
            return next_is_neighbor(A, 1)
        if ev(ev0, "EXIT", who=B):
            # [v3] 被抽的 B 只剩一張獎勵牌、當場退出 → 下一位從 B 的位置擲硬幣（任何情境都可能發生）
            return next_is_neighbor(B, 1)
        return next_is_neighbor(A, 1) and all(e["target"] == A for e in ev(T[1][1], "DRAW"))
    NEXT = "下一位符合接續規則"

    seq = []
    if sc == "1a":
        d = own_discards(ev0, A)
        seq.append(("抽完當下只丟一對", sum(e["n"] for e in d) == 1 and all(e["phase"] == "post" for e in d)))
        seq.append((NEXT, next_after_A()))
    elif sc == "1b":
        d = own_discards(ev0, A)
        seq.append(("抽完當下丟對子", bool(d) and all(e["phase"] == "post" for e in d)))
        seq.append((NEXT, next_after_A()))
    elif sc == "1c":
        d = own_discards(ev0, A)
        ok = bool(d) and all(e["phase"] == "post" for e in d) and (snap["endA"]["exited"] or snap["endA"]["pairs"] <= 1)
        seq.append(("抽完當下清到剩一對以下", ok))
        seq.append((NEXT, next_after_A()))
    elif sc in ("2a", "2c"):
        ex = ev(ev0, "EXIT", who=A)
        seq.append(("抽完當下退出" if sc == "2a" else "抽完當下宣告退出",
                    bool(ex) and all(e["phase"] == "post" for e in ex)))
        seq.append(("下一位是 A 的鄰座（非保底退出）", next_is_neighbor(A, 1)))
    elif sc == "2b":
        seq.append(("持兩張不宣告退出", not ev(ev0, "DECLARE", who=A) and not ev(ev0, "EXIT", who=A)))
        seq.append((NEXT, next_after_A()))
    elif sc == "3b":
        # [v6，執行前寫下] 保守型手牌不到 5 張，選擇保留對子：不清空、不保底、不退出
        #   → 坍縮後若有兩對以上，強制清到剩一對（條例）→ 下一手由 A 的鄰座來抽 A
        seq.append(("選擇保留：不保底、不退出", not ev(ev0, "REDIST", who=A) and not ev(ev0, "EXIT", who=A)))
        seq.append(("坍縮後兩對以上才強制清到一對", (not meta["collapse"]) or snap["endA"]["pairs"] <= 1))
        seq.append((NEXT, next_after_A()))
    elif sc == "3":
        red = ev(ev0, "REDIST", who=A)
        seq.append(("當下清空並保底", bool(red) and red[0]["phase"] == "post"))
        seq.append(("奪取對象正確", bool(red) and red[0]["victim"] in red[0]["expect"]))
        seq.append(("奪取後當下強制退出", bool(ev(ev0, "EXIT", who=A))))
        seq.append(("下一位是被奪取者", bool(red) and nxt == red[0]["victim"]))
    elif sc == "7a":
        # [2026/09/22 新增，執行前寫下] 被動歸零：B 的最後一張牌被 A 抽走，手牌歸零。
        #   被抽當下不處理（不保底、不退出）→ 下一位符合接續規則 → B 下一次輪到時，
        #   抽牌前依憲法 6 保底（從持獎勵牌最多者奪取，並列比分數）→ 強制退出 → 不計一輪
        #   → 下一位是被奪取者。等待期間 B 沒有牌可被抽、也不會是保底對象。
        seq.append(("被抽當下不處理", (not snap["endB"]["exited"]) and not [x for x in ev0 if x["ev"] == "REDIST" and x["who"] == B]))
        seq.append((NEXT, next_after_A()))
        for name, ok in seq:
            if ok is None:
                return None, f"{name}：局已結束"
            if not ok:
                return False, name
        k = next((i for i in range(1, len(T)) if T[i][0]["who"] == B), None)
        # [v4，執行前寫下] 等待期間，重新接續的抽牌者擲硬幣選到空手的 B：
        #   B 當場保底並強制退出 → 該抽牌者這一手不抽、不計一輪 → 下一位是被奪取者
        j = next((i for i in range(1, len(T)) if T[i][0]["who"] != B and ev(T[i][1], "REDIST", who=B)), None)
        if j is not None and (k is None or j < k):
            tj, ej, endj = T[j]
            red = ev(ej, "REDIST", who=B)
            seq.append(("被選為抽牌對象時當場保底", red[0]["victim"] in red[0]["expect"]))
            seq.append(("保底後當場強制退出", bool(ev(ej, "EXIT", who=B))))
            seq.append(("抽牌者這一手不抽、不計一輪", not ev(ej, "DRAW") and endj["tc"] == tj["tc"]))
            nxt2 = T[j + 1][0]["who"] if len(T) > j + 1 else None
            seq.append(("下一位是被奪取者", None if nxt2 is None else nxt2 == red[0]["victim"]))
            for name, ok in seq:
                if ok is None:
                    return None, f"{name}：局已結束"
                if not ok:
                    return False, name
            return True, None
        if k is None:
            return None, "等待期間局先結束"
        tB, eB, endB = T[k]
        red = ev(eB, "REDIST", who=B, phase="pre")
        seq.append(("B 輪到時手牌為零", tB["emp"]))
        seq.append(("抽牌前保底、奪取對象正確", bool(red) and red[0]["victim"] in red[0]["expect"]))
        seq.append(("保底後抽牌前強制退出", bool(ev(eB, "EXIT", who=B, phase="pre")) and not ev(eB, "DRAW")))
        seq.append(("不計一輪", endB["tc"] == tB["tc"]))
        nextB = T[k + 1][0]["who"] if len(T) > k + 1 else None
        seq.append(("下一位是被奪取者", None if nextB is None else (bool(red) and nextB == red[0]["victim"])))
    elif sc == "5":
        # [2026/09/22 v3，執行前寫下] 被動強制退出不需等待：B 被抽到只剩一張獎勵牌，當場退出；
        #   下一位從 B 的位置擲硬幣決定（B 的鄰座；坍縮後為 B 的 -方向 側）。
        #   A 同一回合也退出時，以 A 的退出為準（保底→被奪取者；非保底→A 的鄰座）。
        seq.append(("被抽當下當場退出", snap["endB"]["exited"] and bool(ev(ev0, "EXIT", who=B))))
        if end0["exited"]:
            seq.append((NEXT, next_after_A()))
        else:
            seq.append(("下一位是 B 的鄰座（從 B 的位置擲硬幣）", next_is_neighbor(B, 1)))
    elif sc in ("4", "6"):
        eb = snap["endB"]
        flag = "pc" if sc == "6" else "pe"
        seq.append(("被抽當下不處理、標記 pending", (not eb["exited"]) and eb[flag]))
        seq.append((NEXT, next_after_A()))
        for name, ok in seq:
            if ok is None:
                return None, f"{name}：局已結束"
            if not ok:
                return False, name
        k = next((i for i in range(1, len(T)) if T[i][0]["who"] == B), None)
        # [v3] 等待期間被抽到只剩一張獎勵牌 → 當場退出，下一位是 B 的鄰座（這是合法路徑）
        j = next((i for i in range(1, len(T)) if ev(T[i][1], "EXIT", who=B)), None)
        if j is not None and (k is None or j < k):
            if T[j][2]["exited"] or ev(T[j][1], "REDIST"):
                return None, "等待期間被抽到只剩獎勵牌而退出，同回合另有退出"
            ok = next_is_neighbor(B, j + 1)
            return (None, "等待期間被抽到只剩獎勵牌而退出：局已結束") if ok is None else \
                   ((True, None) if ok else (False, "等待期間當場退出後，下一位是 B 的鄰座"))
        if k is None:
            return None, "等待期間局先結束"
        drawn = any(ev(e, "DRAW", target=B) for t, e, end in T[1:k])
        if any(x["victim"] == B for t, e, end in T[1:k] for x in ev(e, "REDIST")):
            return None, "等待期間 B 被保底奪取"
        tB, eB, endB = T[k]
        valid = tB["ap"] if sc == "6" else tB["hec"]
        if drawn and tB["emp"]:                                  # 乙
            red = ev(eB, "REDIST", who=B, phase="pre")
            seq.append(("手牌歸零：抽牌前保底並強制退出", bool(red) and red[0]["victim"] in red[0]["expect"]
                        and bool(ev(eB, "EXIT", who=B, phase="pre")) and not ev(eB, "DRAW")))
            nextB = T[k + 1][0]["who"] if len(T) > k + 1 else None
            seq.append(("下一位是被奪取者", None if nextB is None else (bool(red) and nextB == red[0]["victim"])))
        elif drawn and not valid:
            other = tB["pe"] if sc == "6" else tB["pc"]
            if other or (sc != "6" and tB["ap"]) or (sc == "6" and (tB["ce"] or tB["hec"])):
                return None, "等待期間轉成另一種條件"
            seq.append(("條件已破壞：抽牌前不退出／不清空", not ev(eB, "EXIT", who=B, phase="pre")))   # 甲
            seq.append(("條件已破壞：照常抽牌", endB["tc"] == tB["tc"] + 1))
        else:
            seq.append(("B 輪到時 pending 仍在", tB[flag]))
            pre_exit = ev(eB, "EXIT", who=B, phase="pre")
            if sc == "6":
                red = ev(eB, "REDIST", who=B, phase="pre")
                ok = bool(red) and red[0]["victim"] in red[0]["expect"] and bool(pre_exit) and not ev(eB, "DRAW")
                seq.append(("抽牌前清空、保底、退出", ok))
            else:
                seq.append(("抽牌前退出", bool(pre_exit) and not ev(eB, "DRAW")))
            seq.append(("抽牌前退出不計一輪", endB["tc"] == tB["tc"]))
            if sc == "6":
                nextB = T[k + 1][0]["who"] if len(T) > k + 1 else None
                seq.append(("下一位是被奪取者", None if nextB is None else (bool(red) and nextB == red[0]["victim"])))
            else:
                seq.append(("下一位是 B 的鄰座（非保底退出）", next_is_neighbor(B, k + 1)))
    for name, ok in seq:
        if ok is None:
            return None, f"{name}：局已結束"
        if not ok:
            return False, name
    return True, None


def _neighbor_from_log(B, direction, T, idx):
    """依座位與當時已退出者，算 B 在 direction 方向上的下一位。
    已退出者：到該輪為止出現過 EXIT 的座位。"""
    exited = set()
    for t, e, end in T[:idx]:
        for x in e:
            if x["ev"] == "EXIT":
                exited.add(x["who"])
    for k in range(1, 4):
        q = (B + direction * k) % 4
        if q not in exited:
            return q
    return None


# ---------------------------------------------------------------- 主程式
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-e", "--engine", required=True)
    ap.add_argument("-n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    m = load_engine(args.engine)
    print("=" * 62)
    print(f"引擎 {os.path.basename(args.engine)}   每個情境 {args.n} 次")
    print("=" * 62)
    for idx, sc in enumerate(SPEC):
        firsts = collections.Counter()
        inv = collections.Counter()
        bad = 0
        undecided = collections.Counter()
        for i in range(args.n):
            (ok, where), iv = run_once(m, sc, args.seed + (idx + 1) * 100000 + i)
            inv.update(iv)
            if ok is None:
                undecided[where] += 1
            elif not ok:
                bad += 1
                firsts[where] += 1
        print(f"\n情境 {sc:<3}{SPEC[sc][0]}")
        print(f"   不符 {bad}／{args.n}    不變量違規 守恆 {inv['I1']}・手牌上限 {inv['I2']}・坍縮 {inv['I3']}")
        for k, v in firsts.most_common():
            print(f"      第一個不符：{k}  {v} 次")
        for k, v in undecided.most_common():
            print(f"      不判定：{k}  {v} 次")


if __name__ == "__main__":
    main()
