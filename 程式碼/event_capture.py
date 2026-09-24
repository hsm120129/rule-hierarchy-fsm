# ============================================================
# event_capture.py
# 反向抽鬼牌 — 事件擷取層骨架 (Event Capture Layer Skeleton)
#
# 目的：
#   在「快照層/歷史層」正式欄位設計完成之前，先把遊戲引擎的五個
#   天然事件觸發點（抽牌 / 湊對丟棄 / 保底轉化 / 退出-強制退出 /
#   環境坍縮）的原始資料攔截下來，證明「攔截點存在、資料可被擷取、
#   可以落地成檔案」——不預設任何正式欄位名稱或結構。
#
# 設計原則：
#   1. 不預設欄位：payload 一律用 **kwargs 原樣吃進來，
#      要映射成正式欄位（例如「職能角色ID」「事件語意分類」等）
#      是後續使用者自己決定、自己接的事，本骨架不代為決定。
#   2. 不動遊戲邏輯：只在既有函式「印完之後」多插一行記錄呼叫，
#      不改變任何規則判斷、隨機性或原本的 print 輸出。
#   3. 兩層分開，對應研究計畫裡的用詞：
#        - 歷史層 (history)  = 事件序列，記錄「發生了什麼」，append-only
#        - 快照層 (snapshot) = 某個時間點「完整局面長什麼樣」，可重建
#   4. 已知限制（誠實列出，不假裝完備）：
#        - Player 層級的事件（discard_pairs / discard_to_one_pair）
#          目前沒有 engine 參考，所以 turn_count 會是 None。
#          若要補上，需要讓 Player 持有 engine 反向參照，
#          這會擴大對原始碼的改動範圍，故骨架階段先不做，
#          留給欄位設計定案後再決定要不要付這個代價。
# ============================================================

import time
import json


class EventRecorder:
    def __init__(self):
        self._seq = 0
        self.history = []      # 歷史層：事件序列（append-only）
        self.snapshots = []    # 快照層：狀態快照序列

    # ---------- 歷史層 ----------
    def emit(self, event_type, engine=None, **payload):
        """
        記錄一個事件。

        event_type: 五個天然觸發點之一（字串，暫定，未來欄位設計
                     定案後可整批改名，不影響呼叫端邏輯）：
                     "DRAW" / "DISCARD_PAIRS" / "REDISTRIBUTION" /
                     "EXIT" / "COLLAPSE"
        engine:      GameEngine 實例（若有），用來自動附上 turn_count。
        **payload:   呼叫端傳入的原始資料，不做任何欄位轉換或篩選。
        """
        self._seq += 1
        record = {
            "event_id": self._seq,
            "ts": time.time(),
            "event_type": event_type,
            "turn_count": getattr(engine, "turn_count", None) if engine else None,
            "payload": payload,
        }
        self.history.append(record)
        return record

    # ---------- 快照層 ----------
    def snapshot(self, label, engine):
        """
        對 engine 目前狀態做一次完整快照（未經篩選，全欄位）。
        label 用來標記這次快照對應哪個時間點
        （例如 "after_setup" / "after_open_round" / "after_turn"）。
        """
        self._seq += 1
        active_players = [p for p in engine.players if not p.exited]
        reward_cards_in_play = sum(
            len(p.get_reward_cards()) for p in active_players
        )  # 場面獎勵牌數量：只算活躍玩家手上流通的，不含已退出者帶走的
        state = {
            "engine": {
                "turn_count": engine.turn_count,
                "round_count": getattr(engine, "round_count", None),  # [事件擷取骨架-新增]
                "direction": engine.direction,
                "disaster_triggered": engine.disaster_triggered,
                "active_player_count": len(active_players),
                "reward_cards_in_play": reward_cards_in_play,
            },
            "players": [
                {
                    "name": p.name,
                    "personality": p.personality,
                    "hand": [repr(c) for c in p.hand],
                    "hand_size": len(p.hand),
                    "exited": p.exited,
                    "score": p.score,
                    "pending_exit": p.pending_exit,
                    "pending_clear": p.pending_clear,
                }
                for p in engine.players
            ],
        }
        record = {
            "snapshot_id": self._seq,
            "ts": time.time(),
            "label": label,
            "state": state,
        }
        self.snapshots.append(record)
        return record

    # ---------- 輸出 ----------
    def dump(self, history_path, snapshot_path):
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(self.snapshots, f, ensure_ascii=False, indent=2)

    def summary(self):
        from collections import Counter
        counts = Counter(r["event_type"] for r in self.history)
        last_snapshot = self.snapshots[-1] if self.snapshots else None
        return {
            "total_events": len(self.history),
            "total_snapshots": len(self.snapshots),
            "by_event_type": dict(counts),
            "final_turn_count": last_snapshot["state"]["engine"]["turn_count"] if last_snapshot else None,
            "final_round_count": last_snapshot["state"]["engine"].get("round_count") if last_snapshot else None,
        }


# 全域唯一實例，供 instrumented 版引擎 import 使用
RECORDER = EventRecorder()
