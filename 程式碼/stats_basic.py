"""只量輪數分布與逐輪不變量（給沒有 _draw 等掛鉤的舊引擎，如 vC6.1）。"""
import sys, json, random
import invariant_per_turn as IV
path, coll, N = sys.argv[1], sys.argv[2] == 'on', int(sys.argv[3])
m = IV.load_engine(path); m.TURN_CAP = 10**9
if not coll: m.COLLAPSE_TURN = 10**9
ck = IV.Checker(); IV.instrument(m, ck)
turns = []
for seed in range(N):
    ck.seed = seed; random.seed(seed); g = m.GameEngine(); g.run_game(); turns.append(g.turn_count)
t = sorted(turns); n = len(t)
out = dict(engine=path, collapse=coll, N=N, mean=round(sum(t)/n, 1), median=t[n//2], p95=t[int(n*.95)], p99=t[int(n*.99)],
           max=t[-1], over200=sum(x > 200 for x in t), total_turns=sum(t), checks=ck.checks,
           inv={k: [ck.count[k], len(ck.games[k])] for k in IV.NAMES})
json.dump(out, open(f"res_{path.replace('反向抽鬼牌','').replace('.py','')}_{sys.argv[2]}_{N}.json", 'w'), ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False))
