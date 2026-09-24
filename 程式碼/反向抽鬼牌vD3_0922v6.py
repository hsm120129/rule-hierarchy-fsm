import random
import sys
import io
import os
# ============================================================
# 反向抽鬼牌 vD3 - 五局累積積分版 + 終局對決
# [2026/09/22] 單局引擎改為 反向抽鬼牌vC7_0922v6.py（作者確認的最終規則）。本檔其餘不動。
# 單局引擎：反向抽鬼牌vC7.py（依 README v5 規則）
# vD2 → vD3（2026/09/16）：底層引擎由 vC6.1 改為 vC7，
#   抽牌順序、明牌期先手、退出後接續、防禦期丟對子時機隨之修正。
#   本檔自身的保底第二順位與終局對決邏輯不變。
# 修正：並列保底觸發改用累積積分排序
# 2026/09 修正：(1) 改以 importlib 載入引擎，消除載入時偷跑一局的問題
#              (2) 保底奪取改為隨機抽一張，回復設計原意
#              (3) 生死抽手牌清空改為強制抽取權（隨機），非直接奪取最高分
# ============================================================

# ------------------------------------------------------------
# 以模組方式載入 vC6 引擎。
# 舊版用 exec + 字串替換關掉被載入檔的主程式區塊，但該檔實際寫的是
# 雙引號 if __name__ == "__main__":，替換字串用的是單引號，比對失敗，
# 導致載入當下就先跑了一局完整遊戲——不計分，卻消耗亂數，使
# random.seed() 之後的五局結果整體偏移。
# 改以 importlib 載入後，被載入檔的 __name__ 為 "vc6" 而非 "__main__"，
# 主程式區塊自然不會執行，且不依賴任何字串比對。
# ------------------------------------------------------------
import importlib.util

_engine_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '反向抽鬼牌vC7_0922v6.py')
_spec = importlib.util.spec_from_file_location('vc7', _engine_path)
_vc6 = importlib.util.module_from_spec(_spec)
sys.modules['vc7'] = _vc6
_spec.loader.exec_module(_vc6)
globals().update({k: v for k, v in vars(_vc6).items() if not k.startswith('_')})


# 覆寫 redistribution，並列時用累積積分排
def redistribution_vD(self, player, total_scores):
    if not player.is_hand_empty():
        return

    active = [p for p in self.players if not p.exited and p != player]
    candidates = [p for p in active if p.get_reward_cards()]
    if not candidates:
        return

    # 持有最多優先，並列時看累積積分最高
    candidates.sort(key=lambda p: (
        -len(p.get_reward_cards()),
        -total_scores.get(p.name, 0)
    ))
    target = candidates[0]

    target_rewards = target.get_reward_cards()
    # [修正] 隨機抽一張，非固定抽最高分那張。
    # 張數最多者不一定握著場面最高分；隨機才讓「記住牌流」有報酬。
    # 舊實作固定抽最高分，導致最低分的 2 分牌永遠不會被奪走。
    stolen = random.choice(target_rewards)
    target.hand.remove(stolen)
    player.hand.append(stolen)
    print(f"  🎯 [保底轉化] {player.name} 手牌清空，強制從 {target.name}"
          f"(持有{len(target.get_reward_cards())+1}張) 奪取 {stolen}！")


class DeathMatch:
    """
    終極生死抽：第一二名同分時觸發
    莊家（積分領先者）：雜牌A + 10分獎勵牌 + 鬼牌（3張）
    閒家（積分追平者）：雜牌B（1張）
    出對子立刻丟，手牌清空可強制抽對方獎勵牌
    勝點：對方只剩鬼牌
    """
    def __init__(self, dealer_name, challenger_name):
        self.dealer_name = dealer_name
        self.challenger_name = challenger_name

        self.ghost = Card("Ghost", "Ghost")
        self.reward_10 = Card("Reward", "S10", is_reward=True, points=10)
        self.card_a = Card("♠", "J")
        self.card_b = Card("♥", "J")

        self.dealer_hand = [self.card_a, self.reward_10, self.ghost]
        self.challenger_hand = [self.card_b]
        self.turn = 0

    def show_hands(self):
        def fmt(c):
            if c == self.ghost:
                return "👻[鬼牌]"
            elif c.is_reward:
                return f"🌟[{c.points}分]"
            else:
                return f"[{c.suit}{c.rank}]"
        print(f"  {self.dealer_name}(莊): {[fmt(c) for c in self.dealer_hand]}")
        print(f"  {self.challenger_name}(閒): {[fmt(c) for c in self.challenger_hand]}")

    def discard_pairs(self, hand, owner):
        normal = [c for c in hand if not c.is_reward and c != self.ghost]
        rank_map = {}
        for c in normal:
            rank_map.setdefault(c.rank, []).append(c)
        removed = []
        for rank, cards in rank_map.items():
            if len(cards) >= 2:
                removed.extend(cards[:2])
        for c in removed:
            hand.remove(c)
        if removed:
            print(f"  ♻️ {owner} 丟棄對子！")

    def check_win(self):
        dealer_only_ghost = (len(self.dealer_hand) == 1 and self.dealer_hand[0] == self.ghost)
        challenger_only_ghost = (len(self.challenger_hand) == 1 and self.challenger_hand[0] == self.ghost)
        if dealer_only_ghost:
            return "challenger"
        if challenger_only_ghost:
            return "dealer"
        return None

    def run(self):
        print("\n" + "=" * 55)
        print(f"⚔️  [終極生死抽] {self.dealer_name} vs {self.challenger_name}")
        print("=" * 55)
        print(f"  莊家({self.dealer_name})：雜牌A + 10分獎勵牌 + 鬼牌")
        print(f"  閒家({self.challenger_name})：雜牌B")

        for _ in range(50):
            self.turn += 1
            print(f"\n── 第{self.turn}輪 ──")

            if self.turn % 2 == 1:
                drawer_name = self.challenger_name
                drawer_hand = self.challenger_hand
                target_hand = self.dealer_hand
                target_name = self.dealer_name
            else:
                drawer_name = self.dealer_name
                drawer_hand = self.dealer_hand
                target_hand = self.challenger_hand
                target_name = self.challenger_name

            if not target_hand:
                print(f"  ⚠️ {target_name} 手牌空，跳過")
                continue

            chosen = random.choice(target_hand)
            target_hand.remove(chosen)
            drawer_hand.append(chosen)
            print(f"  {drawer_name} 從 {target_name} 抽到一張牌")

            self.discard_pairs(drawer_hand, drawer_name)

            if len(drawer_hand) == 0 and target_hand:
                # [2026/09 修正] 手牌清空取得的是「強制抽取權」，不是直接奪取
                # 對方最高分獎勵牌。抽到哪一張不一定——可能抽到鬼牌而當場落敗。
                # 舊實作只從獎勵牌中挑最高分，使清空手牌幾乎等同必勝，
                # 精確列舉下閒家勝率 75%；修正後為 50%（先抽後抽皆然）。
                stolen = random.choice(target_hand)
                target_hand.remove(stolen)
                drawer_hand.append(stolen)
                print(f"  🎯 {drawer_name} 手牌清空！強制抽取 → {stolen}")
                self.discard_pairs(drawer_hand, drawer_name)

            self.show_hands()

            result = self.check_win()
            if result == "dealer":
                print(f"\n🏆 {self.dealer_name}(莊) 勝！閒家只剩鬼牌！")
                return self.dealer_name
            elif result == "challenger":
                print(f"\n🏆 {self.challenger_name}(閒) 勝！莊家只剩鬼牌！")
                return self.challenger_name

        print("\n⚠️ 回合上限，平局")
        return None


class Tournament:
    def __init__(self):
        self.player_configs = [
            ("Architect_Hsu", "aggressive"),
            ("Li_Yue", "conservative"),
            ("Player_3", "balanced"),
            ("Player_4", "random"),
        ]
        self.total_scores = {name: 0 for name, _ in self.player_configs}
        self.round_results = []

    def run(self):
        print("=" * 55)
        print("🏆 反向抽鬼牌 vD3 | 五局累積積分版")
        print("=" * 55)

        for game_num in range(1, 6):
            print(f"\n\n{'█'*55}")
            print(f"  第 {game_num} 局")
            print(f"{'█'*55}")

            game = GameEngine()

            # 注入累積積分到redistribution
            import types
            game.redistribution = types.MethodType(
                lambda self, player, ts=self.total_scores: redistribution_vD(self, player, ts),
                game
            )

            game.run_game()

            result = {p.name: p.score for p in game.players}
            self.round_results.append(result)

            for name, _ in self.player_configs:
                self.total_scores[name] += result.get(name, 0)

            print(f"\n📊 [第{game_num}局結束] 累積積分：")
            sorted_totals = sorted(self.total_scores.items(), key=lambda x: x[1], reverse=True)
            for rank, (name, score) in enumerate(sorted_totals, 1):
                this_round = result.get(name, 0)
                print(f"  第{rank}名 {name}: 累積{score}分（本局+{this_round}）")

        self.final_ranking()

    def final_ranking(self):
        print("\n\n" + "=" * 55)
        print("🏆 [五局結束] 最終排名")
        print("=" * 55)

        print("\n📋 各局積分明細：")
        header = f"  {'玩家':<20}" + "".join([f"第{i+1}局  " for i in range(5)]) + "累積"
        print(header)
        print(f"  {'─'*60}")
        for name, _ in self.player_configs:
            row = f"  {name:<20}"
            for result in self.round_results:
                row += f"{result.get(name,0):<7}"
            row += f"{self.total_scores[name]}"
            print(row)

        print("\n🏅 最終排名：")
        sorted_totals = sorted(self.total_scores.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉", "  "]
        for rank, (name, score) in enumerate(sorted_totals):
            print(f"  {medals[rank]} 第{rank+1}名 {name}: {score}分")

        loser = sorted_totals[-1]
        print(f"\n💀 五局最輸：{loser[0]}（{loser[1]}分）")

        top_two = sorted_totals[:2]
        if top_two[0][1] == top_two[1][1]:
            print(f"\n⚠️  [同分！] {top_two[0][0]} 與 {top_two[1][0]} 積分相同")
            print("   → 啟動終極生死抽！")
            dm = DeathMatch(top_two[0][0], top_two[1][0])
            winner = dm.run()
            if winner:
                print(f"\n🏆 最終冠軍：{winner}")


if __name__ == "__main__":
    random.seed(42)
    tournament = Tournament()
    tournament.run()
