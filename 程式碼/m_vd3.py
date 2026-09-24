import sys, random, collections, importlib.util
path, N = sys.argv[1], int(sys.argv[2])
s = importlib.util.spec_from_file_location("vd3", path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
q = lambda *a, **k: None
m.print = q; sys.modules['vc7'].print = q
C = collections.Counter(); ties = 0
orig = m.redistribution_vD
def red(self, player, ts):
    before = {c for p in self.players for c in p.hand if c.is_reward}
    orig(self, player, ts)
    got = [c for c in player.hand if c.is_reward]
    for c in got: C[c.points] += 1
m.redistribution_vD = red
for seed in range(N):
    random.seed(seed); t = m.Tournament(); t.run()
    top = sorted(t.total_scores.values(), reverse=True)
    ties += top[0] == top[1]
tot = sum(C.values())
print(path, "保底奪取", tot, {k: f"{C[k]} ({C[k]/tot*100:.1f}%)" for k in (10, 8, 4, 2)}, "一二名同分觸發生死抽", f"{ties}/{N}")
dm = collections.Counter()
for i in range(200000):
    random.seed(10**7 + i); d = m.DeathMatch("D", "C"); dm[d.run()] += 1
print("生死抽 20 萬次：", dict(dm))
