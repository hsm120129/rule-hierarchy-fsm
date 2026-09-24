import construct_test_v6 as CT, collections, sys
engines = sys.argv[1:]
rows = collections.OrderedDict()
for e in engines:
    m = CT.load_engine(e)
    for idx, sc in enumerate(CT.SPEC):
        bad = und = 0; path = collections.Counter()
        for i in range(100):
            hold = {}
            orig = CT.steps
            def cap(s, meta, log, snap):
                r = orig(s, meta, log, snap); hold['r'] = r
                if s in ("4", "5", "6") and r[0] is not None:
                    T = CT.turns_of(log); B = meta["B"]
                    k = next((j for j in range(1, len(T)) if T[j][0]["who"] == B), None)
                    if k is not None:
                        drawn = any(x["ev"] == "DRAW" and x.get("target") == B for t, ev, en in T[1:k] for x in ev)
                        path['歸零保底' if drawn and T[k][0]["emp"] else '破壞後照常抽' if drawn else '照原本處理'] += 1
                return r
            CT.steps = cap; (ok, w), _ = CT.run_once(m, sc, (idx + 1) * 100000 + i); CT.steps = orig
            if ok is None: und += 1
            elif not ok: bad += 1
        rows.setdefault(sc, []).append((bad, und, dict(path)))
for sc, vals in rows.items():
    print(sc, " | ".join(f"{b}" + (f"（不判定{u}）" if u else "") for b, u, p in vals), "|", vals[-1][2] if sc in ("4","5","6","7a") else "")
