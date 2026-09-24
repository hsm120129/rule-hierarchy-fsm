"""三人殘局：用最終版引擎逐手展開成狀態圖，再以值迭代求 C 的最佳策略（拿到 10 分機率最大）。
每一手之內的隨機分岔與 C 的決定都照引擎本身走；狀態在每一手結束時合併，所以循環也能處理。"""
import sys, copy, random, importlib.util, collections
_spec = importlib.util.spec_from_file_location("eng", "反向抽鬼牌vC7_0922v6.py")
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)
m.print = lambda *a, **k: None; m._emit = lambda *a, **k: None; m._snapshot = lambda *a, **k: None
class Branch(Exception):
    def __init__(self, kind, n): self.kind, self.n = kind, n
S = {"script": [], "pos": 0}
def nxt(kind, n):
    if n == 1: return 0
    if S["pos"] < len(S["script"]):
        i = S["script"][S["pos"]]; S["pos"] += 1; return i
    raise Branch(kind, n)
random.choice = lambda seq: list(seq)[nxt("chance", len(list(seq)))]
random.randint = lambda a, b: a + nxt("chance", b - a + 1)
P = m.Player
o_wd, o_we, o_cp = P.want_to_discard, P.want_to_exit_now, P.choose_pairs_to_discard
P.want_to_discard = lambda s: [True, False][nxt("decision", 2)] if s.name == "C" else o_wd(s)
P.want_to_exit_now = lambda s: [True, False][nxt("decision", 2)] if s.name == "C" else o_we(s)
P.choose_pairs_to_discard = lambda s, lo, hi: (lo + nxt("decision", hi - lo + 1)) if s.name == "C" else o_cp(s, lo, hi)
def card(r): return m.Card("♠", r)
def R(p): return m.Card("★", f"R{p}", True, p)

def initial(variant, d):
    g = m.GameEngine.__new__(m.GameEngine); m.GameEngine.__init__(g)
    g.players = [P(n, "aggressive") for n in "ABCD"]
    g.seat = {p.name: i for i, p in enumerate(g.players)}
    A, B, C, D = g.players
    D.exited, D.score = True, 4
    if variant == "甲":
        A.hand = [card("5"), card("5"), R(10)]; A.pending_exit = True
        B.hand = [R(2), R(8)]
    else:
        A.hand = [card("7"), R(10)]; B.hand = [card("7"), R(2), R(8)]
    C.hand = [card("9"), card("9")]; C.pending_clear = True
    g.direction, g.turn_count, g.disaster_triggered = d, m.COLLAPSE_TURN - 1, False
    g._cur, g._anchor = C, None
    return g

def step(g):
    """照 run_game 的迴圈本體走一手（含接續規則）。"""
    drawer, anchor = g._cur, g._anchor
    while drawer.exited: drawer = g._neighbor(drawer, g.direction)
    g._last_target = None; g._drew = False; g._passive_exit = None
    g._early_redist = False; g._declined_clear = False; g._redist = False
    g.run_turn(drawer, fixed_target=anchor); anchor = None
    if drawer.exited and g._redist and g._last_target is not None and not g._last_target.exited:
        drawer = g._last_target
    elif drawer.exited:
        if not g.disaster_triggered: g.direction = random.choice([1, -1])
        drawer = g._neighbor(drawer, -g.direction)
    elif g._early_redist and g._last_target is not None and not g._last_target.exited:
        drawer = g._last_target
    elif g._passive_exit is not None:
        if not g.disaster_triggered: g.direction = random.choice([1, -1])
        drawer = g._neighbor(g._passive_exit, -g.direction)
    elif g._drew:
        if not g.disaster_triggered: g.roll_direction()
        anchor = drawer; drawer = g._neighbor(anchor, -g.direction)
    else:
        drawer = g._neighbor(drawer, g.direction)
    g._cur, g._anchor = drawer, anchor

def key(g):
    ps = tuple((p.name, tuple(sorted(repr(c) for c in p.hand)), p.exited, p.score, p.pending_exit, p.pending_clear) for p in g.players)
    return (ps, g._cur.name if g._cur else None, g._anchor.name if g._anchor else None, g.direction, g.disaster_triggered)
def terminal(g):
    if g.check_game_end():
        h = copy.deepcopy(g); h.final_settlement()
        return next(p for p in h.players if p.name == "C").score
    return None

def expand(g):
    """一手之內的分岔樹。葉子是 ('end', 分數) 或 ('state', key, 引擎)。"""
    def rec(prefix):
        h = copy.deepcopy(g); S["script"], S["pos"] = prefix, 0
        try:
            step(h)
        except Branch as b:
            return (b.kind, [rec(prefix + [i]) for i in range(b.n)])
        t = terminal(h)
        return ("end", t) if t is not None else ("state", key(h), h)
    return rec([])

def solve(variant, d):
    g0 = initial(variant, d)
    trees, q, k0 = {}, collections.deque([g0]), key(g0)
    seen = {k0}
    while q:
        g = q.popleft(); tr = expand(g); trees[key(g)] = tr
        stack = [tr]
        while stack:
            n = stack.pop()
            if n[0] == "state":
                if n[1] not in seen: seen.add(n[1]); q.append(n[2])
            elif n[0] in ("chance", "decision"): stack.extend(n[1])
    V = {k: (0.0, 0.0, 0.0) for k in trees}
    idx = {10: 0, 8: 1, 2: 2}
    def ev(n):
        if n[0] == "end":
            v = [0.0, 0.0, 0.0]
            if n[1] in idx: v[idx[n[1]]] = 1.0
            return tuple(v)
        if n[0] == "state": return V[n[1]]
        kids = [ev(c) for c in n[1]]
        if n[0] == "chance": return tuple(sum(k[i] for k in kids) / len(kids) for i in range(3))
        return max(kids, key=lambda k: k[0])
    for it in range(20000):
        diff = 0.0
        for k, tr in trees.items():
            new = ev(tr); diff = max(diff, max(abs(a - b) for a, b in zip(new, V[k]))); V[k] = new
        if diff < 1e-15: break
    root = trees[k0]            # 根節點：C 的清空決定（decision，兩個子樹）
    assert root[0] == "decision", root[0]
    clear, keep = ev(root[1][0]), ev(root[1][1])
    return clear, keep, len(trees), it
sys.setrecursionlimit(100000)
for variant in ["甲", "乙"]:
    for d, dn in [(1, "C 抽 A"), (-1, "C 抽 B")]:
        clear, keep, n, it = solve(variant, d)
        fmt = lambda v: f"10分 {v[0]:.4f}、8分 {v[1]:.4f}、2分 {v[2]:.4f}、其他 {1-sum(v):.4f}"
        print(f"【{variant}｜{dn}】狀態數 {n}（迭代 {it} 次）")
        print(f"   清空：{fmt(clear)}")
        print(f"   不清空、以 10 分為目標：{fmt(keep)}", flush=True)
