# ============================================================
# 反向抽鬼牌 vC7 - 單局版（繼承 vC6.1）
# 對應文件：反向抽鬼牌_README_v5.md
#
# vC6.1 → vC7 修正（2026/09/16）
#   規則文件 v4 以前未寫明以下規則，vC6.1 實作成與設計不同的做法。
#   vC7 依 README v5 補寫的規則修正：
#   1. 明牌期由持有 10 分獎勵牌的玩家先抽，依方向繞一圈
#      （vC6.1：固定由座位第一位先抽）
#   2. 博弈期第一位抽牌者＝明牌期第一位；之後「被抽的人成為下一位抽牌者」
#      （vC6.1：固定照座位順序輪流，方向只影響抽誰）
#   3. 被保底奪取的玩家視同被抽，成為下一位抽牌者
#   4. 抽牌前退出：擲硬幣決定下一位抽牌者，該抽牌者再擲一次決定抽誰
#      （vC6.1：直接輪到座位下一位）
#   5. 丟對子的決定（防禦期自願丟、坍縮後清對子）：抽完牌當下處理
#      （vC6.1：下一次輪到自己時、抽牌前才處理）
#   6. 憲法 3：手牌達 5 張只強制丟到低於 5 張，當下一次決定丟幾對；
#      對子丟完仍達 5 張就停。開局清洗仍全部丟掉
#      （vC6.1：手牌達 5 張一律丟掉全部對子）
#
# ── 規則位階 ──────────────────────────────────────────────
# [憲法] 最上位、不可違逆，違反即非法狀態：
#   1. 獎勵牌守恆：全場恆 {10,8,4,2} 四張（含已退出者帶走的）
#   2. 配對規則：同點數成對、必能完整配對、無永久單張
#   3. 手牌 ≥ 5 → 當下一次決定丟幾對，至少丟到低於 5 張（對子丟完仍 ≥5 就停）
#   4. 退出唯一前提 = 手上恰好 1 張獎勵牌（0 張觸保底、≥2 張不能退）
#   5. 時序：pending 機制決定行動權的合法時機（主動當下／被動等自己回合）
#   6. 保底觸發：手牌歸零 → 必奪取一張（強制，無選擇）
#   7. 坍縮觸發：第 20 輪 → 必啟動
# [條例] 情境性、受憲法約束：
#   8. 坍縮後：方向鎖定為最後一次擲硬幣的方向、不再擲硬幣
#   9. 坍縮後清對子（只檢查當輪抽牌者）：保留一對 or 全清
#      （2 對以上先清到剩一對再選；保留後若手牌仍 ≥5，憲法 3 凌駕、照樣清）
#
# 可調參數（驗證腳本用）：
#   COLLAPSE_TURN  坍縮觸發輪數，設為極大值即為「無坍縮」對照組
#   TURN_CAP       外部安全上限，不是規則；設為極大值即為「無上限」
#   RECORDER       事件擷取層記錄器，預設 None（不記錄）
# ============================================================

import random

# ── 2026/09/19 修正（四個版本同一處改法）──
#   1. 一次抽牌為一輪：輪數只在真正抽牌時加一；抽牌前就退出不算一輪。
#      坍縮在第 COLLAPSE_TURN 次抽牌之前觸發（該次抽牌已處於坍縮下）。
#   2. 退出資格為「一對＋恰好一張獎勵牌」（原寫成至少一張）。

COLLAPSE_TURN = 20
TURN_CAP = 200
RECORDER = None


def _emit(event_type, engine=None, **payload):
    if RECORDER is not None:
        RECORDER.emit(event_type, engine=engine, **payload)


def _snapshot(label, engine):
    if RECORDER is not None:
        RECORDER.snapshot(label, engine)


class Card:
    def __init__(self, suit, rank, is_reward=False, points=0):
        self.suit = suit
        self.rank = rank
        self.is_reward = is_reward
        self.points = points

    def __repr__(self):
        if self.is_reward:
            return f"🌟[{self.points}分]"
        return f"[{self.suit}{self.rank}]"

    def pair_key(self):
        return self.rank


class Player:
    def __init__(self, name, personality="balanced"):
        self.name = name
        self.personality = personality
        self.hand = []
        self.exited = False
        self.score = 0
        self.pending_exit = False   # 被動達成退出條件，等自己回合
        self.pending_clear = False  # 被動達成清空條件，等自己回合

    def get_reward_cards(self):
        return [c for c in self.hand if c.is_reward]

    def get_normal_cards(self):
        return [c for c in self.hand if not c.is_reward]

    def get_pairs(self):
        normal = self.get_normal_cards()
        rank_map = {}
        for c in normal:
            rank_map.setdefault(c.pair_key(), []).append(c)
        pairs = []
        singles = []
        for rank, cards in rank_map.items():
            count = len(cards)
            for i in range(count // 2):
                pairs.append((cards[i * 2], cards[i * 2 + 1]))
            if count % 2 == 1:
                singles.append(cards[-1])
        return pairs, singles

    def must_discard(self):
        return len(self.hand) >= 5

    def all_pairs_no_singles(self):
        """手上普通牌全部是對子，沒有單張"""
        pairs, singles = self.get_pairs()
        return len(pairs) > 0 and len(singles) == 0

    def has_exit_condition(self):
        """退出資格：恰好 1 對 + 1 張獎勵牌（玩家可選擇是否宣告）"""
        pairs, singles = self.get_pairs()
        rewards = self.get_reward_cards()
        return len(rewards) == 1 and len(pairs) == 1 and len(singles) == 0

    def can_exit(self):
        """強制退出：無任何普通牌，且只剩一張獎勵牌"""
        return len(self.get_normal_cards()) == 0 and len(self.get_reward_cards()) == 1

    def is_hand_empty(self):
        return len(self.hand) == 0

    def discard_pairs(self, force=False):
        pairs, singles = self.get_pairs()
        if not pairs:
            return 0
        should = force or self.must_discard() or self.want_to_discard()
        if not should:
            return 0
        rewards = self.get_reward_cards()
        discarded = [c for pair in pairs for c in pair]
        self.hand = rewards + singles
        print(f"  ♻️ {self.name} 丟棄 {len(pairs)} 對對子")
        _emit("DISCARD_PAIRS", player=self.name, pairs_discarded=len(pairs),
              discarded_cards=[repr(c) for c in discarded], force=force,
              hand_after=[repr(c) for c in self.hand])
        return len(pairs)

    def discard_by_rule(self):
        """[憲法 3] 抽完牌當下的丟對子決定（開局清洗除外）。
        手牌達 5 張：當下一次決定丟幾對，至少丟到手牌低於 5 張；對子全丟完仍達 5 張就停。
        手牌 4 張以下：當下決定丟不丟。決定之後定案，不能丟完再追加。
        回傳丟掉的對子數。"""
        pairs, singles = self.get_pairs()
        if not pairs:
            return 0
        total = len(pairs)
        size = len(self.hand)
        min_k = min(total, (size - 4 + 1) // 2) if size >= 5 else 0
        k = self.choose_pairs_to_discard(min_k, total)
        if k <= 0:
            return 0
        rewards = self.get_reward_cards()
        discarded = [c for pair in pairs[:k] for c in pair]
        kept = [c for pair in pairs[k:] for c in pair]
        self.hand = rewards + singles + kept
        print(f"  ♻️ {self.name} 丟棄 {k} 對對子（手牌 {size} → {len(self.hand)}）")
        _emit("DISCARD_PAIRS", player=self.name, pairs_discarded=k,
              discarded_cards=[repr(c) for c in discarded], force=(min_k > 0),
              reason="hand_limit" if min_k > 0 else "voluntary",
              hand_after=[repr(c) for c in self.hand])
        return k

    def choose_pairs_to_discard(self, min_k, total):
        """AI 性格決定丟幾對（min_k ≤ k ≤ total）。"""
        if self.personality in ("aggressive", "balanced"):
            return total
        elif self.personality == "conservative":
            return min_k
        else:  # random
            if min_k > 0:
                return random.randint(min_k, total)
            return total if random.choice([True, False]) else 0

    def discard_to_one_pair(self):
        """[條例] 坍縮用：保留任意一對，清掉其餘所有對子。回傳清掉的對子數。"""
        pairs, singles = self.get_pairs()
        if len(pairs) <= 1:
            return 0
        keep = list(pairs[0])
        discarded = [c for pair in pairs[1:] for c in pair]
        rewards = self.get_reward_cards()
        self.hand = rewards + singles + keep
        cleared = len(pairs) - 1
        print(f"  ⚡ {self.name} 清掉 {cleared} 對，保留 1 對")
        _emit("DISCARD_PAIRS", player=self.name, pairs_discarded=cleared,
              discarded_cards=[repr(c) for c in discarded], force=True,
              reason="collapse_keep_one", hand_after=[repr(c) for c in self.hand])
        return cleared

    def want_to_discard(self):
        if self.personality == "aggressive":
            return True
        elif self.personality == "conservative":
            return len(self.hand) >= 5
        elif self.personality == "balanced":
            return True
        else:
            return random.choice([True, False])

    def want_to_exit_now(self):
        if self.personality == "aggressive":
            return True
        elif self.personality == "conservative":
            rewards = self.get_reward_cards()
            best = max(rewards, key=lambda c: c.points) if rewards else None
            return best and best.points >= 8
        elif self.personality == "balanced":
            return True
        else:
            return random.choice([True, False])


class GameEngine:
    def __init__(self):
        self.players = [
            Player("Architect_Hsu", "aggressive"),
            Player("Li_Yue", "conservative"),
            Player("Player_3", "balanced"),
            Player("Player_4", "random"),
        ]
        self.seat = {p.name: i for i, p in enumerate(self.players)}
        self.deck = []
        self.reward_pool = [
            Card('Reward', 'S10', is_reward=True, points=10),
            Card('Reward', 'S8', is_reward=True, points=8),
            Card('Reward', 'S4', is_reward=True, points=4),
            Card('Reward', 'S2', is_reward=True, points=2),
        ]
        self.turn_count = 0
        self.direction = 1
        self.disaster_triggered = False
        self._last_target = None    # 本輪「被抽／被奪取」的玩家 → 下一位抽牌者
        self._first_drawer = None   # 明牌期第一位（持 10 分者）

    # ---------------- 開局 ----------------
    def setup(self):
        print("=" * 55)
        print("🎮 反向抽鬼牌 vC7 | 單局版")
        print("=" * 55)

        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for suit in suits:
            for rank in ranks:
                self.deck.append(Card(suit, rank))

        random.shuffle(self.deck)
        random.shuffle(self.reward_pool)

        for i, player in enumerate(self.players):
            player.hand.append(self.reward_pool[i])

        for player in self.players:
            for _ in range(13):
                player.hand.append(self.deck.pop())

        print("\n📋 [開局清洗]")
        for player in self.players:
            player.discard_pairs(force=True)

        self._check_forced_exit(reason="forced_setup")
        _snapshot("after_setup", self)

    # ---------------- 共用 ----------------
    def get_active_players(self):
        return [p for p in self.players if not p.exited]

    def roll_direction(self):
        if self.disaster_triggered:
            return
        self.direction = random.choice([1, -1])
        print(f"  🪙 {'順時針' if self.direction == 1 else '逆時針'}")

    def _neighbor(self, from_player, direction):
        """依座位順序，找 from_player 在 direction 方向上的下一位未退出玩家。"""
        n = len(self.players)
        i = self.seat[from_player.name]
        for k in range(1, n):
            q = self.players[(i + direction * k) % n]
            if not q.exited and q is not from_player:
                return q
        return None

    def do_exit(self, player, reason="forced"):
        rewards = player.get_reward_cards()
        if not rewards:
            return
        player.score = rewards[0].points
        _emit("EXIT", engine=self, player=player.name, score=player.score,
              reward=repr(rewards[0]), reason=reason)
        player.hand = []
        player.exited = True
        player.pending_exit = False
        player.pending_clear = False

    def do_voluntary_exit(self, player, reason="voluntary_declared"):
        """宣告退出：丟棄對子後只剩一張獎勵牌"""
        player.discard_pairs(force=True)
        if player.can_exit():
            self.do_exit(player, reason=reason)
            return True
        return False

    def redistribution(self, player):
        """保底轉化：手牌完全清空時觸發。
        只從持有 2 張以上獎勵牌者奪取——清空者手上 0 張時，
        其餘未退出玩家人數比剩下的獎勵牌少一個，必有人持 2 張以上，
        張數最多優先的排序因此不會選到只持 1 張的人。"""
        if not player.is_hand_empty():
            return

        active = [p for p in self.players if not p.exited and p != player]
        candidates = [p for p in active if p.get_reward_cards()]
        if not candidates:
            return

        candidates.sort(key=lambda p: (
            -len(p.get_reward_cards()),
            -sum(c.points for c in p.get_reward_cards())
        ))
        target = candidates[0]

        stolen = random.choice(target.get_reward_cards())
        target.hand.remove(stolen)
        player.hand.append(stolen)
        self._last_target = target   # 被奪取者視同被抽
        print(f"  🎯 [保底轉化] {player.name} 手牌清空，強制從 {target.name}"
              f"(持有{len(target.get_reward_cards()) + 1}張) 奪取 {stolen}！")
        _emit("REDISTRIBUTION", engine=self, player=player.name,
              target=target.name, card=repr(stolen))

    def _check_forced_exit(self, reason="forced"):
        """只剩一張獎勵牌 → 強制退出"""
        changed = True
        while changed:
            changed = False
            for p in self.get_active_players():
                if p.can_exit():
                    self.do_exit(p, reason=reason)
                    print(f"\n✅ [強制退出] {p.name} 帶走 {p.score} 分登出！")
                    changed = True
                    break

    def _call_redistribution(self, player):
        """經由實例屬性呼叫，讓五局版可以替換保底判準；並記錄被奪取者。"""
        before = {p.name: len(p.get_reward_cards()) for p in self.players}
        self.redistribution(player)
        for p in self.players:
            if p is not player and len(p.get_reward_cards()) < before[p.name]:
                self._last_target = p

    def _draw(self, drawer, target, chosen):
        target.hand.remove(chosen)
        drawer.hand.append(chosen)
        _emit("DRAW", engine=self, drawer=drawer.name, target=target.name,
              card=repr(chosen))

    # ---------------- 明牌期 ----------------
    def open_round(self):
        print("\n" + "=" * 55)
        print("👁️  [明牌期] 擲硬幣，由持 10 分者先抽，所有人抽一次")
        self.roll_direction()

        start = next(p for p in self.players
                     if not p.exited and any(c.points == 10 for c in p.get_reward_cards()))
        self._first_drawer = start
        order = [start]
        cur = start
        for _ in range(len(self.get_active_players()) - 1):
            cur = self._neighbor(cur, self.direction)
            order.append(cur)

        for drawer in order:
            if drawer is None or drawer.exited:
                continue
            target = self._neighbor(drawer, self.direction)
            if target is None or not target.hand:
                continue

            target_rewards = target.get_reward_cards()
            if target_rewards and drawer.personality == "aggressive":
                chosen = max(target_rewards, key=lambda c: c.points)
            else:
                chosen = random.choice(target.hand)

            self._draw(drawer, target, chosen)
            print(f"  👁️ {drawer.name} 從 {target.name} 抽到 {chosen}")

            drawer.discard_by_rule()
            if drawer.is_hand_empty():
                self._call_redistribution(drawer)

        self._check_forced_exit(reason="forced_open_round")
        self._last_target = None
        print("\n🙈 [蓋牌] 進入心理博弈階段")
        _snapshot("after_open_round", self)

    # ---------------- 博弈期 ----------------
    def _check_passive_after_drawn(self, target):
        """被抽牌後檢查 target 狀態，設定 pending 標記，等 target 自己回合才處理。"""
        if target.exited:
            return
        if False:  # 消融 M5
            target.pending_exit = True
            print(f"  ⏳ {target.name} 被動達成強制退出條件，等待自己回合")
            return
        if target.has_exit_condition():
            target.pending_exit = True
            print(f"  ⏳ {target.name} 被動達成退出資格（1對+1獎勵牌），等待自己回合宣告")
            return
        if target.all_pairs_no_singles():
            target.pending_clear = True
            print(f"  ⏳ {target.name} 被動達成清空條件，等待自己回合宣告")

    def run_turn(self, drawer):
        # 輪數改在真正抽牌時才加一（見檔頭 2026/09/19 修正）

        if self.turn_count + 1 >= COLLAPSE_TURN and not self.disaster_triggered:
            self.disaster_triggered = True
            print(f"\n🌪️  [第{COLLAPSE_TURN}輪] 環境坍縮！方向鎖定"
                  f"{'順時針' if self.direction == 1 else '逆時針'}")
            _emit("COLLAPSE", engine=self, direction_locked=self.direction)

        print(f"\n{'─' * 55}")
        print(f"🔄 第{self.turn_count + 1}輪 | {drawer.name}({drawer.personality}) | 手牌{len(drawer.hand)}張")

        # === 輪到自己：先處理 pending（抽牌之前）===
        if drawer.pending_exit:
            drawer.pending_exit = False
            if drawer.can_exit():
                self.do_exit(drawer, reason="forced_pending_resolved")
                print(f"  ✅ {drawer.name} 強制退出！得 {drawer.score} 分")
                return
            elif drawer.has_exit_condition():
                if drawer.want_to_exit_now():
                    if self.do_voluntary_exit(drawer, reason="voluntary_pending_declared"):
                        print(f"  ✅ {drawer.name} 宣告退出！得 {drawer.score} 分")
                        return
                else:
                    print(f"  🤔 {drawer.name} 選擇不宣告退出，繼續留場")
            else:
                print(f"  ⚠️ {drawer.name} 的退出資格已失效（牌被抽走）")

        if drawer.pending_clear:
            drawer.pending_clear = False
            if drawer.all_pairs_no_singles():
                if drawer.want_to_discard():
                    print(f"  🃏 {drawer.name} 宣告被動清空！")
                    drawer.discard_pairs(force=True)
                    if drawer.is_hand_empty():
                        self._call_redistribution(drawer)
                    if drawer.can_exit():
                        self.do_exit(drawer, reason="forced_after_clear")
                        print(f"  ✅ {drawer.name} 清空後退出！得 {drawer.score} 分")
                        return
                else:
                    print(f"  🤔 {drawer.name} 選擇保留對子，繼續留場")
            else:
                print(f"  ⚠️ {drawer.name} 的清空條件已失效（牌被抽走）")

        if drawer.is_hand_empty():
            self._call_redistribution(drawer)

        # 抽牌前只處理強制收斂（手牌 ≥ 5）；其餘丟對子決定都在抽完牌當下處理
        if drawer.get_pairs()[0] and drawer.must_discard():
            drawer.discard_by_rule()

        if drawer.can_exit():
            self.do_exit(drawer, reason="forced_turn_start")
            print(f"  ✅ {drawer.name} 回合起始強制退出！得 {drawer.score} 分")
            return

        # === 抽牌 ===
        if not self.disaster_triggered:
            self.roll_direction()

        target = self._neighbor(drawer, self.direction)
        self._last_target = target
        if target is None or target.exited or not target.hand:
            print("  ⚠️ 找不到有效目標")
            self._last_target = None
            return

        self.turn_count += 1   # 一次抽牌為一輪
        chosen = random.choice(target.hand)
        self._draw(drawer, target, chosen)
        print(f"  🃏 {drawer.name} 從 {target.name} 抽到 {chosen}")

        self._check_passive_after_drawn(target)

        # === 主動達成（自己抽牌後當下）===
        if not drawer.exited and drawer.has_exit_condition():
            if drawer.want_to_exit_now():
                if self.do_voluntary_exit(drawer, reason="voluntary_declared"):
                    print(f"  ✅ {drawer.name} 主動宣告退出！得 {drawer.score} 分")
                    return

        if not drawer.exited:
            pairs, singles = drawer.get_pairs()
            rewards = drawer.get_reward_cards()
            if len(rewards) == 0 and len(pairs) > 0 and len(singles) == 0:
                print(f"  🃏 {drawer.name} 主動達成清空！")
                drawer.discard_pairs(force=True)
                if drawer.is_hand_empty():
                    self._call_redistribution(drawer)
                if drawer.can_exit():
                    self.do_exit(drawer, reason="forced_after_clear")
                    print(f"  ✅ {drawer.name} 清空後退出！得 {drawer.score} 分")
                    return

        # === 抽完牌當下：丟對子的決定 ===
        if not drawer.exited and drawer.get_pairs()[0]:
            if self.disaster_triggered and len(drawer.get_pairs()[0]) >= 2:
                # [條例] 坍縮後（只檢查當輪抽牌者）：2 對以上先強制清到剩一對
                drawer.discard_to_one_pair()
            # [憲法 3] 手牌達 5 張至少丟到低於 5 張；否則當下決定丟不丟
            drawer.discard_by_rule()
            if drawer.is_hand_empty():
                self._call_redistribution(drawer)
            if drawer.can_exit():
                self.do_exit(drawer, reason="forced_after_discard")
                print(f"  ✅ {drawer.name} 丟完只剩一張獎勵牌，強制退出！得 {drawer.score} 分")
                return
            if drawer.has_exit_condition() and drawer.want_to_exit_now():
                if self.do_voluntary_exit(drawer, reason="voluntary_declared"):
                    print(f"  ✅ {drawer.name} 主動宣告退出！得 {drawer.score} 分")
                    return

    def check_game_end(self):
        return len(self.get_active_players()) <= 1

    def final_settlement(self):
        print(f"\n{'=' * 55}")
        print("🏁 [遊戲結束] 最終結算")

        for p in self.get_active_players():
            rewards = p.get_reward_cards()
            if rewards:
                p.score = rewards[0].points
                print(f"  📌 {p.name} 帶著 {rewards[0]} 結算")

        print("\n📊 [最終積分排名]")
        results = sorted(self.players, key=lambda p: p.score, reverse=True)
        for rank, p in enumerate(results, 1):
            status = "✅" if p.exited else "🎯"
            print(f"  第{rank}名 {p.name}: {p.score}分 {status}")
        print(f"\n💀 本局最輸：{results[-1].name}（{results[-1].score}分）")
        _snapshot("final_settlement", self)

    def run_game(self):
        self.setup()
        self.open_round()

        drawer = self._first_drawer
        if drawer is None or drawer.exited:
            drawer = next((p for p in self.players if not p.exited), None)

        while not self.check_game_end():
            if drawer is None or self.turn_count > TURN_CAP:
                print("\n⚠️ [System] 輪數上限，強制結束")
                break
            if drawer.exited:
                drawer = self._neighbor(drawer, self.direction)
                continue

            self._last_target = None
            _turn_before = self.turn_count
            self.run_turn(drawer)
            if self.turn_count > _turn_before:
                _snapshot(f"after_turn_{self.turn_count}", self)
            else:
                # 這一次沒有抽牌（抽牌前退出／無有效目標），不計一輪，
                # 但局面可能已改變（保底奪取、退出），快照照做，標籤不綁輪數。
                _snapshot(f"after_turn_{self.turn_count}_no_draw", self)

            if drawer.exited and self._last_target is None:
                # 抽牌前退出：擲硬幣決定下一位抽牌者（坍縮後沿用鎖定方向）
                if not self.disaster_triggered:
                    self.direction = random.choice([1, -1])
                drawer = self._neighbor(drawer, self.direction)
            elif self._last_target is not None and not self._last_target.exited:
                drawer = self._last_target   # 被抽／被奪取的人成為下一位抽牌者
            else:
                drawer = self._neighbor(drawer, self.direction)

        self.final_settlement()


if __name__ == "__main__":
    game = GameEngine()
    game.run_game()
