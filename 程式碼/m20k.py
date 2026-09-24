"""其他量測：宣告退出失敗、沒抽牌卻計一輪、pending 等待。"""
import sys, random, collections, importlib.util, json
path, N = sys.argv[1], int(sys.argv[2]); cap = sys.argv[3] if len(sys.argv) > 3 else 'default'
s = importlib.util.spec_from_file_location("e", path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.print = lambda *a, **k: None
if cap == 'nocap': m.TURN_CAP = 10**9
E = m.GameEngine
C = collections.Counter(); fail_games = set(); drew = {}
ov, od, ort, op = E.do_voluntary_exit, E._draw, E.run_turn, E._check_passive_after_drawn
def vol(self, p, *a, **k):
    r = ov(self, p, *a, **k)
    if not r: C['declare_fail'] += 1; fail_games.add(self._seed)
    return r
def dr(self, *a, **k):
    self._drew = True; return od(self, *a, **k)
def pas(self, t):
    b = t.pending_exit; op(self, t)
    if t.pending_exit and not b:
        C['p_set'] += 1; self._watch = t.name; self._ps[t.name] = 'pending'
def rt(self, d, *a, **k):
    if getattr(self, '_watch', None) is not None:
        if d.name != self._watch:
            C['p_next_not_self'] += 1
            if self._watch in self._ps: self._ps[self._watch] = 'delayed'
        self._watch = None
    if d.pending_exit and d.name in self._ps:
        st = self._ps.pop(d.name); C['p_resolved'] += 1
        if d.can_exit(): C['p_forced'] += 1
        elif d.has_exit_condition(): C['p_cond'] += 1
        else:
            C['p_invalid'] += 1; C['p_invalid_' + st] += 1
    self._drew = False
    tc = self.turn_count
    r = ort(self, d, *a, **k)
    C['run_turn_calls'] += 1
    if not self._drew: C['no_draw_calls'] += 1
    return r
E.do_voluntary_exit, E._draw, E.run_turn, E._check_passive_after_drawn = vol, dr, rt, pas
T = 0
for seed in range(N):
    random.seed(seed); g = E(); g._seed = seed; g._ps = {}; g.run_game(); T += g.turn_count
C['sum_turn_count'] = T; C['declare_fail_games'] = len(fail_games)
print(path, cap, json.dumps(dict(C), ensure_ascii=False))
