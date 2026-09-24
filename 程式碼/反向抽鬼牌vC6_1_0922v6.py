COLLAPSE_TURN = 20
# [2026/09/22 規則落實修正二] 主動清空改為由玩家決定（依檔頭：清不清空是決策點）。其餘與 0919 版相同。
TURN_CAP = 200
# ============================================================
# 反向抽鬼牌 vC6 - 單局版（繼承 vC5）
# 修正：坍縮清對子規則改為「保留一對 or 全清」（vC5 誤實作為一律強制全清）
#
# ── 規則位階 ──────────────────────────────────────────────
# [憲法] 最上位、不可違逆，違反即非法狀態：
#   1. 獎勵牌守恆：全場恆 {10,8,4,2} 四張（含已退出者帶走的）
#   2. 配對規則：同點數成對、必能完整配對、無永久單張
#   3. 手牌 ≥ 5 → 強制清對子（must_discard）
#   4. 退出唯一前提 = 手上恰好 1 張獎勵牌（0張觸保底、≥2張不能退）
#   5. 時序：pending 機制決定行動權的合法時機（主動當下／被動等自己回合）〔2026/09/22：強制退出一律當場，見檔頭〕
#   6. 保底觸發：手牌歸零 → 必奪取一張（強制，無選擇）
#   7. 坍縮觸發：第 20 輪 → 必啟動（強制，保證收斂）
# [條例] 情境性、受憲法約束：
#   8. 坍縮後：方向鎖定、不再擲硬幣
#   9. 坍縮後清對子：保留一對 or 全清（2對以上先清到剩一對再選；
#      保留後若手牌仍 ≥5，憲法3 凌駕、照樣清）
# 玩家選擇：只在憲法開的決策點上行使（清不清空、退不退、坍縮留不留那對）
# ============================================================

import random

# ── 2026/09/19 修正（四個版本同一處改法）──
#   1. 一次抽牌為一輪：輪數只在真正抽牌時加一；抽牌前就退出不算一輪。
#      坍縮在第 COLLAPSE_TURN 次抽牌之前觸發（該次抽牌已處於坍縮下）。
#   2. 退出資格為「一對＋恰好一張獎勵牌」（原寫成至少一張）。

# ============================================================
# 反向抽鬼牌 vC5 - 單局版
# 修正：
# 1. 被動達成「1對+1獎勵牌」也標記 pending_exit（vC4 漏掉此情境）
# 2. pending_exit 宣告時過 want_to_exit_now()，非強制
# 3. 強制退出唯一條件：手上只剩一張獎勵牌（無任何普通牌）
# ============================================================

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
                pairs.append((cards[i*2], cards[i*2+1]))
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
        """退出資格：恰好1對+1張獎勵牌（玩家可選擇是否宣告）"""
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
        self.hand = rewards + singles
        print(f"  ♻️ {self.name} 丟棄 {len(pairs)} 對對子")
        return len(pairs)

    def discard_to_one_pair(self):
        """[條例] 坍縮用：保留任意一對，清掉其餘所有對子。回傳清掉的對子數。"""
        pairs, singles = self.get_pairs()
        if len(pairs) <= 1:
            return 0
        keep = list(pairs[0])  # 保留第一對
        rewards = self.get_reward_cards()
        self.hand = rewards + singles + keep
        cleared = len(pairs) - 1
        print(f"  ⚡ {self.name} 清掉 {cleared} 對，保留 1 對")
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
        self.deck = []
        self.reward_pool = [
            Card('Reward', 'S10', is_reward=True, points=10),
            Card('Reward', 'S8',  is_reward=True, points=8),
            Card('Reward', 'S4',  is_reward=True, points=4),
            Card('Reward', 'S2',  is_reward=True, points=2),
        ]
        self.turn_count = 0
        self.direction = 1
        self.disaster_triggered = False

    def setup(self):
        print("=" * 55)
        print("🎮 反向抽鬼牌 vC5 | 單局版")
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

        self._check_forced_exit()

        print("\n📊 [開局手牌]")
        for p in self.players:
            print(f"  {p.name}({p.personality}): {len(p.hand)}張 | {p.hand}")

    def get_active_players(self):
        return [p for p in self.players if not p.exited]

    def roll_direction(self):
        if self.disaster_triggered:
            return
        self.direction = random.choice([1, -1])
        print(f"  🪙 {'順時針' if self.direction == 1 else '逆時針'}")

    def get_target(self, drawer_index, active):
        n = len(active)
        if n <= 1:
            return None
        return active[(drawer_index + self.direction) % n]

    def do_exit(self, player):
        """強制退出：手上只剩一張獎勵牌時觸發"""
        rewards = player.get_reward_cards()
        if not rewards:
            return
        player.score = rewards[0].points
        player.hand = []
        player.exited = True
        player.pending_exit = False
        player.pending_clear = False

    def do_voluntary_exit(self, player):
        """主動宣告退出：丟棄對子後只剩一張獎勵牌"""
        player.discard_pairs(force=True)
        if player.can_exit():
            self.do_exit(player)
            return True
        return False

    def redistribution(self, player):
        """保底轉化：手牌完全清空時觸發"""
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

        target_rewards = target.get_reward_cards()
        # [2026/09 修正] 隨機抽一張，非固定抽最高分那張。
        # 保底奪取的第一順位是「張數」而非分數，被鎖定的對象不一定握著
        # 場面最高分；隨機抽才讓「記住牌流」這件事有報酬，也才對得起
        # 明牌期→蓋牌→博弈期的資訊設計。
        # 舊實作固定抽最高分，導致最低分的 2 分牌永遠不會被奪走
        # （實測：舊實作下 2 分牌被奪取率 0.00%，修正後約 26%）。
        stolen = random.choice(target_rewards)
        target.hand.remove(stolen)
        player.hand.append(stolen)
        print(f"  🎯 [保底轉化] {player.name} 手牌清空，強制從 {target.name}"
              f"(持有{len(target.get_reward_cards())+1}張) 奪取 {stolen}！")

    def _check_forced_exit(self):
        """只剩一張獎勵牌 → 強制退出"""
        changed = True
        while changed:
            changed = False
            for p in self.get_active_players():
                if p.can_exit():
                    self.do_exit(p)
                    print(f"\n✅ [強制退出] {p.name} 帶走 {p.score} 分登出！")
                    changed = True
                    break

    def open_round(self):
        print("\n" + "=" * 55)
        print("👁️  [明牌期] 擲硬幣，所有人抽一次")
        self.roll_direction()

        active = self.get_active_players()
        for i, drawer in enumerate(active):
            target = self.get_target(i, active)
            if target is None or target == drawer or not target.hand:
                continue

            target_rewards = target.get_reward_cards()
            if target_rewards and drawer.personality == "aggressive":
                chosen = max(target_rewards, key=lambda c: c.points)
            else:
                chosen = random.choice(target.hand)

            target.hand.remove(chosen)
            drawer.hand.append(chosen)
            print(f"  👁️ {drawer.name} 從 {target.name} 抽到 {chosen}")

            drawer.discard_pairs(force=True)

            if drawer.is_hand_empty():
                self.redistribution(drawer)

        self._check_forced_exit()
        print("\n🙈 [蓋牌] 進入心理博弈階段")

    def _check_passive_after_drawn(self, target):
        """
        被抽牌後檢查 target 狀態，設定 pending 標記
        不立即執行，等 target 自己回合才處理
        """
        if target.exited:
            return

        # 強制退出條件：只剩一張獎勵牌（無普通牌）
        if target.can_exit():
            target.pending_exit = True
            print(f"  ⏳ {target.name} 被動達成強制退出條件，等待自己回合")
            return

        # 退出資格：湊成1對+1獎勵牌（可選擇是否宣告）
        if target.has_exit_condition():
            target.pending_exit = True
            print(f"  ⏳ {target.name} 被動達成退出資格（1對+1獎勵牌），等待自己回合宣告")
            return

        # 清空資格：手上普通牌全是對子（無單張）
        if target.all_pairs_no_singles():
            target.pending_clear = True
            print(f"  ⏳ {target.name} 被動達成清空條件，等待自己回合宣告")

    def run_turn(self, drawer, drawer_index, active):
        # 輪數改在真正抽牌時才加一（見檔頭 2026/09/19 修正）

        if self.turn_count + 1 >= COLLAPSE_TURN and not self.disaster_triggered:
            self.disaster_triggered = True
            print(f"\n🌪️  [第20輪] 環境坍縮！方向鎖定{'順時針' if self.direction == 1 else '逆時針'}")

        print(f"\n{'─'*55}")
        print(f"🔄 第{self.turn_count + 1}輪 | {drawer.name}({drawer.personality}) | 手牌{len(drawer.hand)}張")

        # === 回合起始：處理 pending 狀態 ===

        if drawer.pending_exit:
            drawer.pending_exit = False
            # 強制退出：只剩一張獎勵牌
            if drawer.can_exit():
                self.do_exit(drawer)
                print(f"  ✅ {drawer.name} 強制退出！得 {drawer.score} 分")
                return
            # 退出資格：1對+1獎勵牌，玩家選擇是否宣告
            elif drawer.has_exit_condition():
                if drawer.want_to_exit_now():
                    if self.do_voluntary_exit(drawer):
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
                        self.redistribution(drawer)
                        # 保底後繼續本回合抽牌（主動清空才繼續，被動清空到此結束）
                    if drawer.can_exit():
                        self.do_exit(drawer)
                        print(f"  ✅ {drawer.name} 清空後退出！得 {drawer.score} 分")
                        return
                else:
                    print(f"  🤔 {drawer.name} 選擇保留對子，繼續留場")
            else:
                print(f"  ⚠️ {drawer.name} 的清空條件已失效（牌被抽走）")

        # 回合起始手牌清空觸發保底
        if drawer.is_hand_empty():
            self.redistribution(drawer)

        # 宣告清空對子
        pairs, singles = drawer.get_pairs()
        if pairs:
            if self.disaster_triggered:
                # [條例] 坍縮後：2對以上先清到剩一對
                if len(pairs) >= 2:
                    drawer.discard_to_one_pair()
                
                # 補上2 對普通牌 + 3 張不同的單張 + 1 張獎勵牌 = 共 8 張的漏洞
                if drawer.must_discard():
                    drawer.discard_pairs(force=True)
                    print(f"  ⚡ [環境坍縮] {drawer.name} 保留 1 對後總手牌仍 ≥ 5，憲法 3 凌駕，強制全清！")
                # 如果總手牌安全（< 5），才允許玩家依照個性選擇要全清還是留一對
                elif drawer.want_to_discard():
                    drawer.discard_pairs(force=True)
                    print(f"  ⚡ [環境坍縮] {drawer.name} 選擇全清")
                else:
                    print(f"  ⚡ [環境坍縮] {drawer.name} 選擇保留 1 對")
            else:
                drawer.discard_pairs()

        # 清空後只剩一張獎勵牌 → 強制退出
        if drawer.can_exit():
            self.do_exit(drawer)
            print(f"  ✅ {drawer.name} 回合起始強制退出！得 {drawer.score} 分")
            return

        # === 抽牌階段 ===
        if not self.disaster_triggered:
            self.roll_direction()

        target = self.get_target(drawer_index, active)
        if target is None or target == drawer or target.exited or not target.hand:
            print(f"  ⚠️ 找不到有效目標")
            return

        self.turn_count += 1   # 一次抽牌為一輪
        chosen = random.choice(target.hand)
        target.hand.remove(chosen)
        drawer.hand.append(chosen)
        print(f"  🃏 {drawer.name} 從 {target.name} 抽到 {chosen}")

        # 檢查 target 被動狀態
        self._check_passive_after_drawn(target)

        # === 主動達成判斷（自己回合抽牌後）===

        # 主動達成退出：湊成1對+1獎勵牌，玩家選擇是否宣告
        if not drawer.exited and drawer.has_exit_condition():
            if drawer.want_to_exit_now():
                if self.do_voluntary_exit(drawer):
                    print(f"  ✅ {drawer.name} 主動宣告退出！得 {drawer.score} 分")
                    return

        # 主動達成清空：手上全是對子（無獎勵牌、無單張）
        if not drawer.exited:
            pairs, singles = drawer.get_pairs()
            rewards = drawer.get_reward_cards()
            # [2026/09/22 規則落實修正二] 檔頭寫明「清不清空」是玩家的決策點，原實作卻一律強制清空
            if len(rewards) == 0 and len(pairs) > 0 and len(singles) == 0 and drawer.want_to_discard():
                print(f"  🃏 {drawer.name} 主動達成清空！")
                drawer.discard_pairs(force=True)
                if drawer.is_hand_empty():
                    self.redistribution(drawer)
                    # 主動清空保底後繼續抽牌（此輪已抽完，下輪繼續）
                if drawer.can_exit():
                    self.do_exit(drawer)
                    print(f"  ✅ {drawer.name} 清空後退出！得 {drawer.score} 分")
                    return

        # 手牌 ≥ 5 強制清對子
        if not drawer.exited and drawer.must_discard():
            drawer.discard_pairs(force=True)

    def check_game_end(self):
        return len(self.get_active_players()) <= 1

    def final_settlement(self):
        print(f"\n{'='*55}")
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

        loser = results[-1]
        print(f"\n💀 本局最輸：{loser.name}（{loser.score}分）")

    def run_game(self):
        self.setup()
        self.open_round()

        current_index = 0
        while not self.check_game_end():
            active = self.get_active_players()
            if not active or self.turn_count > TURN_CAP:
                print("\n⚠️ [System] 回合上限，強制結束")
                break

            current_index = current_index % len(active)
            drawer = active[current_index]
            self.run_turn(drawer, current_index, active)

            active = self.get_active_players()
            if active:
                current_index = (current_index + 1) % len(active)

        self.final_settlement()


if __name__ == "__main__":
    game = GameEngine()
    game.run_game()
