"""量測各條規則在兩萬局中實際發生的次數（報告附錄一「其他量測」那張表）。
用法：python freq.py 反向抽鬼牌vC7_0922v6.py 20000"""
import importlib.util, random, collections, sys
path = sys.argv[1] if len(sys.argv) > 1 else "反向抽鬼牌vC7_0922v6.py"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
spec = importlib.util.spec_from_file_location("eng", path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.print = lambda *a, **k: None; m.TURN_CAP = 10**9
E = m.GameEngine; C = collections.Counter()
od, ort, ored, oex, ogo = E._draw, E.run_turn, E.redistribution, E.do_exit, E.open_round
def dr(self, d, t, c):
    od(self, d, t, c)
    if not t.hand and not t.exited:
        C['被抽到歸零'] += 1
        if self._last.get(t.name) == self._n: C['歸零前一手剛自己抽完'] += 1
def rt(self, d, *a, **k):
    self._n += 1; r = ort(self, d, *a, **k); self._last[d.name] = self._n + 1
    if self._declined_clear: C['主動清空條件、選擇保留'] += 1
    return r
def red(self, p):
    cands = [q for q in self.players if not q.exited and q is not p and q.get_reward_cards()]
    if p.is_hand_empty() and cands:
        key = lambda q: (len(q.get_reward_cards()), sum(c.points for c in q.get_reward_cards()))
        top = max(key(q) for q in cands)
        if sum(key(q) == top for q in cands) > 1: C['保底時張數與總分都並列'] += 1
    before = {q.name: len(q.get_reward_cards()) for q in self.players if not q.exited}
    ored(self, p)
    for q in self.players:
        if q is not p and not q.exited and len(q.get_reward_cards()) < before.get(q.name, 0):
            C['被奪取者持 %d 張' % before[q.name]] += 1
def ex(self, p, *a, **k):
    r = k.get('reason')
    if r in ('forced_open_round_immediate', 'empty_target_early_redistribution') and not p.exited: C[r] += 1
    return oex(self, p, *a, **k)
def go(self):
    ogo(self)
    if self._first_drawer.exited: C['原點在明牌期退出'] += 1
E._draw, E.run_turn, E.redistribution, E.do_exit, E.open_round = dr, rt, red, ex, go
for seed in range(N):
    random.seed(seed); g = E(); g._n = 0; g._last = {}; g._declined_clear = False; g.run_game()
print("引擎：%s，%d 局" % (path, N))
for k, v in sorted(C.items(), key=lambda x: -x[1]): print("  %-28s %8d" % (k, v))
