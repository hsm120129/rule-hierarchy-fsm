"""獨立檢查博弈期接續規則（作者確認版），逐回合比對：
  一、抽完沒退出 → 下一回合的抽牌者是他的鄰座（坍縮後固定為 -方向 側），且若有抽牌，抽的是他
  二、非保底退出 → 下一回合的抽牌者是退出者的鄰座（坍縮後固定為 -方向 側）
  三、保底退出 → 下一回合的抽牌者是被奪取者"""
import importlib.util, random, sys, collections
def load(p):
    s = importlib.util.spec_from_file_location("e", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    m.print = lambda *a, **k: None; m.TURN_CAP = 10**9; return m
for path in sys.argv[1:]:
    m = load(path); C = collections.Counter()
    for seed in range(3000):
        random.seed(seed); g = m.GameEngine(); recs = []
        ort, od, ored, oex = g.run_turn, g._draw, g._call_redistribution, g.do_exit
        cur = {}
        def dr(d, t, c): cur['target'] = t; od(d, t, c)
        def red(p):
            before = {q.name: len(q.get_reward_cards()) for q in g.players}
            ored(p)
            for q in g.players:
                if q is not p and len(q.get_reward_cards()) < before[q.name]: cur['victim'] = q
        def ex(p, *a, **k):
            r = oex(p, *a, **k)
            if k.get('reason') == 'forced_passive_immediate': cur['passive'] = p
            return r
        def rt(d, *a, **k):
            cur.clear()
            r = ort(d, *a, **k)
            pv = cur.get('passive')
            recs.append(dict(drawer=d, target=cur.get('target'), victim=cur.get('victim'), exited=d.exited, passive=pv,
                             pnb=(g._neighbor(pv, 1), g._neighbor(pv, -1)) if pv else None,
                             nb=(g._neighbor(d, 1), g._neighbor(d, -1)), dir=g.direction, coll=g.disaster_triggered))
            return r
        g._draw, g._call_redistribution, g.run_turn, g.do_exit = dr, red, rt, ex
        g.run_game()
        for r1, r2 in zip(recs, recs[1:]):
            side = r1['nb'][1 if r1['dir'] == 1 else 0]      # nb＝(+1 側, -1 側)，這裡取 -方向 側
            if r1['exited'] and r1['victim'] is not None:
                k = '三、保底→被奪取者'; ok = r2['drawer'] is r1['victim']
            elif r1['exited']:
                k = '二、非保底退出→退出者鄰座'; ok = r2['drawer'] in r1['nb'] and (not r1['coll'] or r2['drawer'] is side)
            elif r1['victim'] is not None and r1['target'] is None:
                k = '五、空手者被選中→當場保底→被奪取者'; ok = r2['drawer'] is r1['victim']
            elif r1['passive'] is not None:
                k = '四、被動強制退出（當場）→退出者鄰座'
                pside = r1['pnb'][1 if r1['dir'] == 1 else 0]
                ok = r2['drawer'] in r1['pnb'] and (not r1['coll'] or r2['drawer'] is pside)
            elif r1['target'] is not None:
                k = '一、先抽後被抽'
                ok = r2['drawer'] in r1['nb'] and (r2['target'] is None or r2['target'] is r1['drawer']) \
                     and (not r1['coll'] or r2['drawer'] is side)
            else:
                k = '其他'; ok = True
            C[(k, '符合' if ok else '不符')] += 1
    print(path); [print('  ', k, v) for k, v in sorted(C.items())]
