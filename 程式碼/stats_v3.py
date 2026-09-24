"""[v3] 被動強制退出為當場退出，另外計數；下列分類只剩被動達成退出資格（有選擇權）的等待。
輪數分布＋逐輪不變量（用 invariant_per_turn.py 的 Checker）＋被動達成退出資格的結果分類。
分類（作者定義）：
  當下退出      被動達成後，中間沒有別人抽牌就輪到自己，條件仍在並退出
  延後退出      中間隔了至少一次抽牌才輪到自己，條件仍在並退出
  條件在、選擇不退  輪到時條件仍在，但玩家選擇不退（非積極型）
  被破壞        輪到時條件已不成立；再依最後結果細分：
                  帶同一張牌退出／帶另一張牌退出（例如手牌歸零後保底）／到局終都沒退出
  局先結束      輪到自己之前局就結束
「延後退出時分數是否改變」另外檢查：退出時的牌與被動達成時是否同一張（牌面分數唯一，以分數比對）。"""
import sys, json, random, collections
import invariant_per_turn as IV
path, coll, N = sys.argv[1], sys.argv[2] == 'on', int(sys.argv[3])
cap = len(sys.argv) > 4 and sys.argv[4] == 'cap200'
m = IV.load_engine(path); m.TURN_CAP = 200 if cap else 10**9
if not coll: m.COLLAPSE_TURN = 10**9
ck = IV.Checker(); IV.instrument(m, ck)
P = collections.Counter(); E = m.GameEngine
op, ort = E._check_passive_after_drawn, E.run_turn
def pas(self, t):
    b = t.pending_exit; op(self, t)
    if t.pending_exit and not b:
        card = t.get_reward_cards()[0].points
        self._ps[t.name] = dict(tc=self.turn_count, draws=self._draws, card=card)
def rt(self, d, *a, **k):
    info = self._ps.pop(d.name, None) if d.pending_exit else None
    if info is not None:
        valid = d.can_exit() or d.has_exit_condition()
        waited = self._draws - info['draws']
    r = ort(self, d, *a, **k)
    if info is not None:
        if valid and d.exited:
            key = '當下退出' if waited == 0 else '延後退出'
            P[key] += 1
            if d.score != info['card']: P[key + '·分數改變'] += 1
        elif valid:
            P['條件在、選擇不退'] += 1
        else:
            self._broken[d.name] = info['card']
    return r
od = E._draw
def dr(self, *a, **k):
    self._draws += 1; return od(self, *a, **k)
oex = E.do_exit
def ex(self, p, *a, **k):
    if k.get('reason') == 'forced_passive_immediate' and not p.exited:
        P['被動強制退出（當場）'] += 1
    return oex(self, p, *a, **k)
E._check_passive_after_drawn, E.run_turn, E._draw, E.do_exit = pas, rt, dr, ex
turns = []
for seed in range(N):
    ck.seed = seed; random.seed(seed)
    g = m.GameEngine(); g._ps = {}; g._broken = {}; g._draws = 0
    g.run_game(); turns.append(g.turn_count)
    P['局先結束'] += len(g._ps)
    for name, card in g._broken.items():
        p = next(x for x in g.players if x.name == name)
        P['被破壞'] += 1
        P['被破壞→' + ('到局終都沒退出' if not p.exited else '帶同一張牌退出' if p.score == card else '帶另一張牌退出')] += 1
t = sorted(turns); n = len(t)
out = dict(engine=path, collapse=coll, N=N, cap=200 if cap else None, mean=round(sum(t)/n, 1), median=t[n//2],
           p95=t[int(n*.95)], p99=t[int(n*.99)], max=t[-1], over200=sum(x > 200 for x in t),
           total_turns=sum(t), checks=ck.checks,
           inv={k: [ck.count[k], len(ck.games[k])] for k in IV.NAMES}, pending=dict(sorted(P.items())))
tag = path.replace('反向抽鬼牌', '').replace('.py', '')
json.dump(out, open(f"res_{tag}_{sys.argv[2]}_{N}.json", 'w'), ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False))
