from __future__ import annotations

import itertools
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Street = Literal["idle", "preflop", "flop", "turn", "river", "showdown"]
PlayerStatus = Literal["waiting", "active", "folded", "all_in", "out"]

STREET_LABELS_VI: dict[str, str] = {
    "idle": "Chờ ván mới",
    "preflop": "Vòng 1: Pre-Flop (2 lá tẩy)",
    "flop": "Vòng 2: Flop (3 lá chung)",
    "turn": "Vòng 3: Turn (Lá chung thứ 4)",
    "river": "Vòng 4: River (Lá chung thứ 5)",
    "showdown": "Showdown - Lật Bài & Kết Quả",
}

STREET_ORDER: list[Street] = ["preflop", "flop", "turn", "river", "showdown"]

DEFAULT_AVATARS = [
    "😎", "🤠", "🦊", "🐯", "🦁", "🐼", "🎩", "👑", "💎", "🃏"
]

BOT_NAMES = [
    "Bot Cá Mập 🦈", "Bot Thần Bài 🃏", "Bot Cao Bồi 🤠", "Bot Cáo Già 🦊",
    "Bot Sư Tử 🦁", "Bot Đại Gia 💎", "Bot Lạnh Lùng 😎", "Bot Hoàng Gia 👑"
]

MAX_SEATS = 10

# ------------------------------------------------------------------
# Playing Cards & 7-Card Texas Hold'em Evaluator
# ------------------------------------------------------------------
RANKS = "23456789TJQKA"
SUITS = "shdc"  # s=Spades(♠), h=Hearts(♥), d=Diamonds(♦), c=Clubs(♣)

RANK_VALUES: dict[str, int] = {r: idx + 2 for idx, r in enumerate(RANKS)}
VALUE_TO_RANK_DISPLAY: dict[int, str] = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9",
    10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"
}
SUIT_SYMBOLS: dict[str, str] = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

_rng = random.SystemRandom()


def create_shuffled_deck() -> list[str]:
    deck = [f"{r}{s}" for r in RANKS for s in SUITS]
    _rng.shuffle(deck)
    return deck


def serialize_card(card: str) -> dict:
    if not card or len(card) < 2 or card == "??":
        return {"code": "??", "rank": "?", "suit": "?", "suitSymbol": "🂠", "color": "back", "hidden": True}
    r = card[0].upper()
    s = card[1].lower()
    val = RANK_VALUES.get(r, 0)
    disp_rank = VALUE_TO_RANK_DISPLAY.get(val, r)
    suit_sym = SUIT_SYMBOLS.get(s, s)
    return {
        "code": f"{r}{s}",
        "rank": disp_rank,
        "suit": s,
        "suitSymbol": suit_sym,
        "color": "red" if s in ("h", "d") else "black",
        "hidden": False,
    }


def _eval_5cards(cards: tuple[str, ...]) -> tuple[tuple[int, ...], str]:
    vals = sorted((RANK_VALUES[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1

    unique_vals = sorted(set(vals), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_vals) == 5:
        if unique_vals[0] - unique_vals[4] == 4:
            is_straight = True
            straight_high = unique_vals[0]
        elif unique_vals == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    if is_flush and is_straight:
        if straight_high == 14:
            return (9, 14), "Thùng Phá Sảnh Chúa (Royal Flush)"
        return (8, straight_high), f"Thùng Phá Sảnh ({VALUE_TO_RANK_DISPLAY[straight_high]} cao)"

    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    pattern = [g[1] for g in groups]
    ordered_ranks = [g[0] for g in groups]

    if pattern == [4, 1]:
        q_rank = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
        return (7, *ordered_ranks), f"Tứ Quý {q_rank} (Four of a Kind)"

    if pattern == [3, 2]:
        r3 = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
        r2 = VALUE_TO_RANK_DISPLAY[ordered_ranks[1]]
        return (6, *ordered_ranks), f"Cù Lũ {r3} - {r2} (Full House)"

    if is_flush:
        top = VALUE_TO_RANK_DISPLAY[vals[0]]
        return (5, *vals), f"Thùng {top} cao (Flush)"

    if is_straight:
        top = VALUE_TO_RANK_DISPLAY[straight_high]
        return (4, straight_high), f"Sảnh tới {top} (Straight)"

    if pattern == [3, 1, 1]:
        r3 = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
        return (3, *ordered_ranks), f"Sám Cô {r3} (Three of a Kind)"

    if pattern == [2, 2, 1]:
        p_hi = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
        p_lo = VALUE_TO_RANK_DISPLAY[ordered_ranks[1]]
        return (2, *ordered_ranks), f"Hai Đôi {p_hi} & {p_lo} (Two Pair)"

    if pattern == [2, 1, 1, 1]:
        p_r = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
        return (1, *ordered_ranks), f"Đôi {p_r} (One Pair)"

    top = VALUE_TO_RANK_DISPLAY[ordered_ranks[0]]
    return (0, *ordered_ranks), f"Mậu Thầu {top} cao (High Card)"


def detect_draws(hole_cards: list[str], board_cards: list[str], current_category: int) -> str:
    """Detect realistic Texas Hold'em draws (Flush draw, Open-ended / Gutshot straight draw) on Flop/Turn."""
    if len(hole_cards) < 2 or len(board_cards) not in (3, 4):
        return ""
    all_cards = [c for c in (hole_cards + board_cards) if c and len(c) >= 2 and c != "??"]
    if len(all_cards) < 5:
        return ""

    hints: list[str] = []

    # 1. Flush Draw (4 cards of the same suit, at least 1 in hole cards)
    if current_category < 5:
        suit_counts: dict[str, int] = {}
        for c in all_cards:
            s = c[1].lower()
            suit_counts[s] = suit_counts.get(s, 0) + 1
        hole_suits = {c[1].lower() for c in hole_cards if len(c) >= 2}
        for s, cnt in suit_counts.items():
            if cnt == 4 and s in hole_suits:
                hints.append(f"Chờ Thùng {SUIT_SYMBOLS.get(s, s)} (9 outs)")
                break

    # 2. Straight Draw (Open-ended 8 outs or Gutshot 4 outs)
    if current_category < 4:
        present_ranks = {RANK_VALUES.get(c[0].upper(), 0) for c in all_cards}
        hole_ranks = {RANK_VALUES.get(c[0].upper(), 0) for c in hole_cards}
        completing_ranks = 0
        for test_r in range(2, 15):
            if test_r in present_ranks:
                continue
            cand = present_ranks | {test_r}
            if 14 in cand:
                cand = cand | {1}
            # Check if any 5 consecutive ranks exist containing test_r (or 1 if test_r == 14)
            makes_straight = False
            for low in range(1, 11):
                window = {low, low + 1, low + 2, low + 3, low + 4}
                if window.issubset(cand) and (test_r in window or (test_r == 14 and 1 in window)):
                    # Ensure at least one hole card contributes to this straight
                    if (hole_ranks & window) or (14 in hole_ranks and 1 in window):
                        makes_straight = True
                        break
            if makes_straight:
                completing_ranks += 1

        if completing_ranks >= 2:
            hints.append("Chờ Sảnh 2 đầu (8 outs)")
        elif completing_ranks == 1:
            hints.append("Chờ Sảnh khe (4 outs)")

    return " · ".join(hints)


def evaluate_best_hand(hole_cards: list[str], board_cards: list[str]) -> dict | None:
    all_cards = [c for c in (hole_cards + board_cards) if c and c != "??"]
    if len(all_cards) < 2:
        return None

    if len(all_cards) < 5:
        v1 = RANK_VALUES.get(all_cards[0][0], 0)
        v2 = RANK_VALUES.get(all_cards[1][0], 0)
        s1, s2 = all_cards[0][1], all_cards[1][1]
        hi, lo = max(v1, v2), min(v1, v2)
        if hi == lo:
            r_disp = VALUE_TO_RANK_DISPLAY[hi]
            return {
                "category": 1,
                "score": [1, hi],
                "name": f"Đôi tẩy {r_disp} (Pocket Pair)",
                "best5": list(all_cards),
                "drawHint": "",
            }
        suited = "đồng chất" if s1 == s2 else "khác chất"
        return {
            "category": 0,
            "score": [0, hi, lo],
            "name": f"Bài cao {VALUE_TO_RANK_DISPLAY[hi]}-{VALUE_TO_RANK_DISPLAY[lo]} ({suited})",
            "best5": list(all_cards),
            "drawHint": "",
        }

    best_score: tuple[int, ...] | None = None
    best_name: str = ""
    best_combo: tuple[str, ...] = ()

    for combo in itertools.combinations(all_cards, 5):
        score, name = _eval_5cards(combo)
        if best_score is None or score > best_score:
            best_score = score
            best_name = name
            best_combo = combo

    assert best_score is not None
    draw_hint = detect_draws(hole_cards, board_cards, best_score[0])
    return {
        "category": best_score[0],
        "score": list(best_score),
        "name": best_name,
        "best5": list(best_combo),
        "drawHint": draw_hint,
    }


def calculate_all_in_equities(active_players: list[Player], board_cards: list[str]) -> dict[str, float]:
    """Compute live win equity (%) for active players during All-in Showdown runout."""
    contenders = [p for p in active_players if len(p.hole_cards) == 2]
    if not contenders:
        return {}
    if len(contenders) == 1:
        return {contenders[0].id: 100.0}

    clean_board = [c for c in board_cards if c and c != "??"]
    needed = max(0, 5 - len(clean_board))

    if needed == 0:
        scores: dict[str, list[int]] = {}
        best_s: list[int] | None = None
        for p in contenders:
            ev = evaluate_best_hand(p.hole_cards, clean_board)
            sc = ev["score"] if ev else [-1]
            scores[p.id] = sc
            if best_s is None or sc > best_s:
                best_s = sc
        winners = [pid for pid, sc in scores.items() if sc == best_s]
        share = round(100.0 / max(1, len(winners)), 1)
        return {p.id: (share if p.id in winners else 0.0) for p in contenders}

    used_cards = set(clean_board)
    for p in contenders:
        used_cards.update(p.hole_cards)
    full_deck = [f"{r}{s}" for r in RANKS for s in SUITS if f"{r}{s}" not in used_cards]

    wins: dict[str, float] = {p.id: 0.0 for p in contenders}
    if needed == 1:
        # Exact enumeration on Turn (44-48 cards)
        trials = len(full_deck)
        for river_card in full_deck:
            sim_board = clean_board + [river_card]
            best_sc: tuple[int, ...] | None = None
            sim_winners: list[str] = []
            for p in contenders:
                all7 = p.hole_cards + sim_board
                p_best = max(_eval_5cards(c)[0] for c in itertools.combinations(all7, 5))
                if best_sc is None or p_best > best_sc:
                    best_sc = p_best
                    sim_winners = [p.id]
                elif p_best == best_sc:
                    sim_winners.append(p.id)
            w_share = 1.0 / len(sim_winners)
            for wid in sim_winners:
                wins[wid] += w_share
        return {pid: round((w / max(1, trials)) * 100.0, 1) for pid, w in wins.items()}

    # Fast Monte Carlo for Pre-flop / Flop
    trials = 140
    for _ in range(trials):
        drawn = _rng.sample(full_deck, needed)
        sim_board = clean_board + drawn
        best_sc = None
        sim_winners = []
        for p in contenders:
            all7 = p.hole_cards + sim_board
            p_best = max(_eval_5cards(c)[0] for c in itertools.combinations(all7, 5))
            if best_sc is None or p_best > best_sc:
                best_sc = p_best
                sim_winners = [p.id]
            elif p_best == best_sc:
                sim_winners.append(p.id)
        w_share = 1.0 / len(sim_winners)
        for wid in sim_winners:
            wins[wid] += w_share
    return {pid: round((w / trials) * 100.0, 1) for pid, w in wins.items()}


def now_time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def format_chips(amount: int) -> str:
    return f"{amount:,}"


@dataclass
class Player:
    id: str
    name: str
    seat: int
    avatar: str = "😎"
    stack: int = 100000
    total_buy_in: int = 100000
    current_bet: int = 0
    total_hand_bet: int = 0
    status: PlayerStatus = "waiting"
    sitting_out: bool = False
    acted_this_round: bool = False
    last_action: str = ""
    is_bot: bool = False
    connected: bool = True
    hole_cards: list[str] = field(default_factory=list)
    revealed: bool = False
    revealed_mask: list[bool] = field(default_factory=lambda: [False, False])
    last_won_amount: int = 0
    last_hand_bet: int = 0
    last_hand_delta: int = 0
    last_hand_outcome: str = ""  # "winner", "loser_showdown", "loser_folded", ""
    showdown_hand_name: str = ""
    showdown_best5: list[str] = field(default_factory=list)
    hands_played: int = 0
    hands_won: int = 0
    biggest_pot_won: int = 0
    ready_next: bool = False

    @property
    def net_profit(self) -> int:
        return (self.stack + self.total_hand_bet) - self.total_buy_in

    def to_dict(
        self,
        board_cards: list[str],
        can_see_hole_cards: bool = False,
        is_dealer: bool = False,
        is_sb: bool = False,
        is_bb: bool = False,
        is_turn: bool = False,
        equity_pct: float | None = None,
    ) -> dict:
        # STRICT PRIVACY: Only expose hole_cards and handEval if `can_see_hole_cards` or `self.revealed` (or per-card mask) is True!
        show_all = can_see_hole_cards or self.revealed
        serialized_cards = []
        hand_eval = None

        if self.hole_cards:
            if show_all:
                serialized_cards = [serialize_card(c) for c in self.hole_cards]
                hand_eval = evaluate_best_hand(self.hole_cards, board_cards)
            else:
                for idx, c in enumerate(self.hole_cards):
                    if idx < len(self.revealed_mask) and self.revealed_mask[idx]:
                        serialized_cards.append(serialize_card(c))
                    else:
                        serialized_cards.append(serialize_card("??"))

        return {
            "id": self.id,
            "name": self.name,
            "seat": self.seat,
            "avatar": self.avatar,
            "stack": self.stack,
            "totalBuyIn": self.total_buy_in,
            "currentBet": self.current_bet,
            "totalHandBet": self.total_hand_bet,
            "netProfit": self.net_profit,
            "status": self.status,
            "sittingOut": self.sitting_out,
            "actedThisRound": self.acted_this_round,
            "lastAction": self.last_action,
            "isBot": self.is_bot,
            "connected": self.connected,
            "isDealer": is_dealer,
            "isSB": is_sb,
            "isBB": is_bb,
            "isTurn": is_turn,
            "holeCards": serialized_cards,
            "hasCards": len(self.hole_cards) == 2,
            "revealed": self.revealed,
            "revealedMask": list(self.revealed_mask),
            "handEval": hand_eval,
            "lastWonAmount": self.last_won_amount,
            "lastHandBet": self.last_hand_bet,
            "lastHandDelta": self.last_hand_delta,
            "lastHandOutcome": self.last_hand_outcome,
            "showdownHandName": self.showdown_hand_name if show_all else "",
            "showdownBest5": self.showdown_best5 if show_all else [],
            "handsPlayed": self.hands_played,
            "handsWon": self.hands_won,
            "biggestPotWon": self.biggest_pot_won,
            "equityPct": equity_pct,
            "readyNext": self.ready_next,
        }


class PokerTable:
    def __init__(
        self,
        small_blind: int = 1000,
        big_blind: int = 2000,
        ante: int = 0,
        default_buy_in: int = 100000,
        currency: str = "VNĐ",
        turn_timeout: int = 20,
    ) -> None:
        self.small_blind: int = max(1, int(small_blind))
        self.big_blind: int = max(self.small_blind, int(big_blind))
        self.ante: int = max(0, int(ante))
        self.default_buy_in: int = max(self.big_blind * 5, int(default_buy_in))
        self.currency: str = currency or "VNĐ"
        self.turn_timeout: int = max(5, min(120, int(turn_timeout or 20)))

        self.players: dict[str, Player] = {}
        self._next_player_seq: int = 1

        self.hand_number: int = 0
        self.street: Street = "idle"
        self.dealer_seat: int = -1
        self.sb_seat: int = -1
        self.bb_seat: int = -1
        self.turn_seat: int = -1
        self.turn_started_at: float = 0.0
        self.turn_deadline: float = 0.0
        self.turn_seq: int = 0
        self.all_in_runout: bool = False
        self.is_bomb_pot: bool = False

        self.deck: list[str] = []
        self.board_cards: list[str] = []
        self.rabbit_cards: list[str] = []
        self.rabbit_revealed: bool = False
        self.winning_cards: list[str] = []
        self.last_showdown_summary: str = ""
        self._last_hand_meta: dict | None = None

        self.current_bet: int = 0
        self.min_raise_delta: int = self.big_blind
        self.pot: int = 0
        self.pots: list[dict] = []

        self.action_log: list[dict] = []
        self.hand_history: list[dict] = []
        self.ledger_log: list[dict] = []

    def _set_turn_seat(self, seat: int) -> None:
        self.turn_seat = seat
        self.turn_seq += 1
        if seat >= 0 and self.street not in ("idle", "showdown") and not self.all_in_runout:
            self.turn_started_at = time.time()
            self.turn_deadline = self.turn_started_at + self.turn_timeout
        else:
            self.turn_started_at = 0.0
            self.turn_deadline = 0.0

    # ------------------------------------------------------------------
    # Logging Helpers
    # ------------------------------------------------------------------
    def _log_action(self, text: str, category: str = "bet", player_id: str | None = None, amount: int = 0) -> None:
        self.action_log.append({
            "time": now_time_str(),
            "hand": self.hand_number,
            "street": self.street,
            "streetLabel": STREET_LABELS_VI.get(self.street, self.street),
            "text": text,
            "category": category,
            "playerId": player_id,
            "amount": amount,
        })
        if len(self.action_log) > 150:
            self.action_log = self.action_log[-150:]

    def _log_ledger(self, text: str, kind: str = "buy_in", player_name: str = "", amount: int = 0) -> None:
        self.ledger_log.append({
            "time": now_time_str(),
            "text": text,
            "kind": kind,
            "playerName": player_name,
            "amount": amount,
        })
        if len(self.ledger_log) > 150:
            self.ledger_log = self.ledger_log[-150:]

    # ------------------------------------------------------------------
    # Seat & Player Helpers
    # ------------------------------------------------------------------
    def sorted_players(self) -> list[Player]:
        return sorted(self.players.values(), key=lambda p: p.seat)

    def get_player_by_seat(self, seat: int) -> Player | None:
        for p in self.players.values():
            if p.seat == seat:
                return p
        return None

    def first_available_seat(self, preferred_seat: int | None = None) -> int | None:
        taken = {p.seat for p in self.players.values()}
        if preferred_seat is not None and 0 <= preferred_seat < MAX_SEATS and preferred_seat not in taken:
            return preferred_seat
        for s in range(MAX_SEATS):
            if s not in taken:
                return s
        return None

    def add_player(
        self,
        name: str,
        buy_in: int | None = None,
        seat: int | None = None,
        avatar: str | None = None,
        is_bot: bool = False,
        player_id: str | None = None,
    ) -> tuple[Player | None, str]:
        chosen_seat = self.first_available_seat(seat)
        if chosen_seat is None:
            return None, "Bàn đã đủ tối đa 10 người chơi."

        clean_name = (name or "").strip()[:24]
        if not clean_name:
            if is_bot:
                clean_name = BOT_NAMES[chosen_seat % len(BOT_NAMES)]
            else:
                clean_name = f"Người chơi {chosen_seat + 1}"

        existing_names = {p.name.lower() for p in self.players.values()}
        if clean_name.lower() in existing_names:
            clean_name = f"{clean_name} #{chosen_seat + 1}"

        initial_stack = self.default_buy_in if buy_in is None or buy_in <= 0 else int(buy_in)
        pid = player_id or f"p{self._next_player_seq}"
        self._next_player_seq += 1

        chosen_avatar = avatar or ("🤖" if is_bot else DEFAULT_AVATARS[chosen_seat % len(DEFAULT_AVATARS)])

        player = Player(
            id=pid,
            name=clean_name,
            seat=chosen_seat,
            avatar=chosen_avatar,
            stack=initial_stack,
            total_buy_in=initial_stack,
            current_bet=0,
            total_hand_bet=0,
            status="waiting",
            sitting_out=False,
            acted_this_round=False,
            last_action="Mới vào bàn",
            is_bot=is_bot,
            connected=True,
            ready_next=is_bot,
        )
        self.players[pid] = player
        self._log_ledger(
            f"{player.name} vào bàn (Ghế #{chosen_seat + 1}) với vốn {format_chips(initial_stack)} {self.currency}",
            kind="buy_in",
            player_name=player.name,
            amount=initial_stack,
        )
        self._log_action(
            f"👋 {player.name} ngồi vào Ghế #{chosen_seat + 1} (Vốn: {format_chips(initial_stack)})",
            category="system",
            player_id=pid,
            amount=initial_stack,
        )
        if self.dealer_seat == -1:
            self.dealer_seat = chosen_seat
        return player, f"Đã thêm {player.name} vào bàn."

    def rename_player(self, player_id: str, new_name: str, avatar: str | None = None) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."
        clean_name = (new_name or "").strip()[:24]
        if not clean_name:
            return False, "Tên người chơi không được để trống."
        other_names = {p.name.lower() for p in self.players.values() if p.id != player_id}
        if clean_name.lower() in other_names:
            return False, f"Tên '{clean_name}' đã có người trên bàn sử dụng."
        old_name = player.name
        player.name = clean_name
        if avatar and str(avatar).strip():
            player.avatar = str(avatar).strip()[:4]
        self._log_action(
            f"✏️ {old_name} đã đổi tên thành {player.avatar} {player.name}",
            category="system",
            player_id=player_id,
        )
        return True, f"Đã cập nhật tên thành {player.avatar} {player.name}!"

    def remove_player(self, player_id: str) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."

        was_turn = (self.turn_seat == player.seat)
        if self.street not in ("idle", "showdown") and player.status in ("active", "all_in"):
            player.status = "folded"
            player.last_action = "Rời bàn (Fold)"

        removed_name = player.name
        removed_seat = player.seat
        self.players.pop(player_id, None)

        self._log_ledger(
            f"{removed_name} rời khỏi Ghế #{removed_seat + 1} (Mang ra: {format_chips(player.stack)} {self.currency}, Lời/Lỗ: {player.net_profit:+,})",
            kind="cash_out",
            player_name=removed_name,
            amount=player.stack,
        )
        self._log_action(f"🚪 {removed_name} đã rời khỏi bàn.", category="system")

        if self.street not in ("idle", "showdown"):
            if was_turn or len(self._active_hand_players()) <= 1:
                self._check_single_survivor_or_round_end()

        return True, f"Đã xóa {removed_name} khỏi bàn."

    def toggle_sit_out(self, player_id: str) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."
        player.sitting_out = not player.sitting_out
        state_txt = "Tạm nghỉ (Sit out)" if player.sitting_out else "Sẵn sàng chơi"
        player.last_action = state_txt
        return True, f"{player.name}: {state_txt}"

    def reveal_player_cards(self, player_id: str, card_index: int | None = None) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player or len(player.hole_cards) < 2:
            return False, "Bạn chưa có bài để lật."

        if len(player.revealed_mask) < 2:
            player.revealed_mask = [player.revealed, player.revealed]

        if card_index in (0, 1):
            if player.revealed or player.revealed_mask[card_index]:
                return False, f"Lá bài thứ {card_index + 1} của bạn đã được lật rồi."
            player.revealed_mask[card_index] = True
            if all(player.revealed_mask):
                player.revealed = True
            c_obj = serialize_card(player.hole_cards[card_index])
            c_str = f"{c_obj['rank']}{c_obj['suitSymbol']}"
            self._log_action(
                f"🃏 {player.name} khoe 1 lá bài tẩy cho cả bàn xem: [{c_str}]",
                category="system",
                player_id=player_id,
            )
            return True, f"🃏 {player.name} vừa lật khoe 1 lá bài tẩy [{c_str}]!"

        if player.revealed:
            return False, "Bài của bạn đã được lật rồi."
        player.revealed = True
        player.revealed_mask = [True, True]
        cards_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in player.hole_cards)
        self._log_action(f"👀 {player.name} chủ động lật cả 2 lá bài tẩy cho bàn xem: [{cards_str}]", category="system", player_id=player_id)
        return True, f"👀 {player.name} đã lật bài tẩy [{cards_str}]!"

    def rabbit_hunt(self, actor_name: str = "Người chơi") -> tuple[bool, str]:
        """Reveal the undealt community cards after a hand ended early by fold (Rabbit Hunting)."""
        if self.street not in ("idle", "showdown"):
            return False, "Chỉ có thể Săn Thỏ (xem nốt bài chung) sau khi ván đấu đã kết thúc."
        if not self.rabbit_cards:
            return False, "Ván này đã lật đủ 5 lá bài chung rồi."
        if self.rabbit_revealed:
            return False, "Đã mở Săn Thỏ cho ván này rồi."

        self.rabbit_revealed = True
        full_board = self.board_cards + self.rabbit_cards
        board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in full_board)
        rabbit_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.rabbit_cards)
        self._log_action(
            f"🐇 [SĂN THỎ] {actor_name} lật thử các lá bài chung còn lại: [{rabbit_str}] (Đủ 5 lá: {board_str})",
            category="street",
        )
        return True, f"🐇 Săn Thỏ! Các lá bài chung tiếp theo lẽ ra là: {rabbit_str}"

    def set_dealer_seat(self, seat: int) -> tuple[bool, str]:
        if self.street not in ("idle", "showdown"):
            return False, "Chỉ có thể đổi vị trí Dealer khi chưa chia bài."
        p = self.get_player_by_seat(seat)
        if not p:
            return False, "Không có người chơi ở ghế này."
        self.dealer_seat = seat
        self._log_action(f"🔘 Chủ bàn đặt {p.name} (Ghế #{seat + 1}) làm Dealer.", category="system")
        return True, f"Đã đặt {p.name} làm Dealer."

    # ------------------------------------------------------------------
    # Table Configuration & Dealer Button
    # ------------------------------------------------------------------
    def update_settings(
        self,
        small_blind: int | None = None,
        big_blind: int | None = None,
        ante: int | None = None,
        default_buy_in: int | None = None,
        currency: str | None = None,
        turn_timeout: int | None = None,
    ) -> tuple[bool, str]:
        if small_blind is not None:
            self.small_blind = max(1, int(small_blind))
        if big_blind is not None:
            self.big_blind = max(self.small_blind, int(big_blind))
        if ante is not None:
            self.ante = max(0, int(ante))
        if default_buy_in is not None:
            self.default_buy_in = max(self.big_blind, int(default_buy_in))
        if currency is not None and currency.strip():
            self.currency = currency.strip()[:10]
        if turn_timeout is not None:
            self.turn_timeout = max(5, min(120, int(turn_timeout)))

        ante_str = f", Ante {format_chips(self.ante)}" if self.ante > 0 else ""
        self._log_action(
            f"⚙️ Chủ bàn cập nhật: Blinds {format_chips(self.small_blind)}/{format_chips(self.big_blind)}{ante_str} ({self.currency}), Đếm giờ: {self.turn_timeout}s",
            category="system",
        )
        return True, "Đã lưu cấu hình bàn chơi."

    # ------------------------------------------------------------------
    # Money / Bankroll Management (Rebuy, Adjust, Transfer)
    # ------------------------------------------------------------------
    def rebuy(self, player_id: str, amount: int) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."
        amt = int(amount)
        if amt <= 0:
            return False, "Số tiền nạp thêm phải lớn hơn 0."

        player.stack += amt
        player.total_buy_in += amt
        if player.status == "out" and self.street in ("idle", "showdown"):
            player.status = "waiting"

        self._log_ledger(
            f"{player.name} nạp thêm (Rebuy) +{format_chips(amt)} {self.currency} (Tổng nạp: {format_chips(player.total_buy_in)})",
            kind="rebuy",
            player_name=player.name,
            amount=amt,
        )
        self._log_action(
            f"💰 {player.name} nạp thêm +{format_chips(amt)} {self.currency} (Số dư: {format_chips(player.stack)})",
            category="money",
            player_id=player_id,
            amount=amt,
        )
        return True, f"Đã nạp thêm +{format_chips(amt)} {self.currency} cho {player.name}."

    def adjust_stack(self, player_id: str, new_stack: int, update_buy_in: bool = True) -> tuple[bool, str]:
        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."
        target = max(0, int(new_stack))
        diff = target - player.stack
        if diff == 0:
            return True, "Số dư không thay đổi."

        old_stack = player.stack
        player.stack = target
        if update_buy_in:
            player.total_buy_in = max(0, player.total_buy_in + diff)

        mode_note = "Có cộng/trừ vào vốn Buy-in" if update_buy_in else "Không đổi vốn gốc Buy-in"
        self._log_ledger(
            f"Điều chỉnh số dư của {player.name}: {format_chips(old_stack)} -> {format_chips(target)} ({diff:+,}) [{mode_note}]",
            kind="adjust",
            player_name=player.name,
            amount=diff,
        )
        self._log_action(
            f"🔧 Điều chỉnh tiền {player.name}: {format_chips(old_stack)} ➔ {format_chips(target)} {self.currency}",
            category="money",
            player_id=player_id,
            amount=diff,
        )
        return True, f"Đã cập nhật số dư của {player.name} thành {format_chips(target)} {self.currency}."

    def transfer_chips(self, from_id: str, to_id: str, amount: int, note: str = "") -> tuple[bool, str]:
        if from_id == to_id:
            return False, "Không thể tự chuyển tiền cho chính mình."
        sender = self.players.get(from_id)
        receiver = self.players.get(to_id)
        if not sender or not receiver:
            return False, "Không tìm thấy người gửi hoặc người nhận."
        amt = int(amount)
        if amt <= 0:
            return False, "Số tiền chuyển phải lớn hơn 0."
        if sender.stack < amt:
            return False, f"{sender.name} không đủ số dư trên bàn ({format_chips(sender.stack)})."

        sender.stack -= amt
        receiver.stack += amt

        reason = f" ({note.strip()})" if note and note.strip() else ""
        self._log_ledger(
            f"Chuyển trực tiếp: {sender.name} ➔ {receiver.name}: {format_chips(amt)} {self.currency}{reason}",
            kind="transfer",
            player_name=f"{sender.name} ➔ {receiver.name}",
            amount=amt,
        )
        self._log_action(
            f"💸 {sender.name} chuyển {format_chips(amt)} {self.currency} cho {receiver.name}{reason}",
            category="money",
            amount=amt,
        )
        return True, f"Đã chuyển {format_chips(amt)} {self.currency} từ {sender.name} sang {receiver.name}."

    # ------------------------------------------------------------------
    # Hand Lifecycle, Card Dealing & Betting Rounds
    # ------------------------------------------------------------------
    def _eligible_for_new_hand(self) -> list[Player]:
        return [p for p in self.sorted_players() if p.stack > 0 and not p.sitting_out]

    def _next_seat_in_list(self, current_seat: int, candidates: list[Player]) -> Player:
        if not candidates:
            raise ValueError("No candidate players")
        higher = [p for p in candidates if p.seat > current_seat]
        return higher[0] if higher else candidates[0]

    def _active_hand_players(self) -> list[Player]:
        return [p for p in self.sorted_players() if p.status in ("active", "all_in")]

    def _can_act_players(self) -> list[Player]:
        return [p for p in self.sorted_players() if p.status == "active" and p.stack > 0]

    def _post_forced_bet(self, player: Player, amount: int, label: str, counts_toward_street_bet: bool = True) -> int:
        actual = min(player.stack, max(0, int(amount)))
        player.stack -= actual
        player.total_hand_bet += actual
        if counts_toward_street_bet:
            player.current_bet += actual
        if player.stack == 0 and actual > 0:
            player.status = "all_in"
            player.last_action = f"{label} {format_chips(actual)} (All-in)"
        else:
            player.last_action = f"{label} {format_chips(actual)}"
        return actual

    def _deal_community_up_to(self, target_count: int) -> None:
        while len(self.board_cards) < target_count and self.deck:
            if len(self.board_cards) in (0, 3, 4) and len(self.deck) > 1:
                self.deck.pop()
            if self.deck:
                self.board_cards.append(self.deck.pop())

    def _capture_rabbit_cards(self) -> list[str]:
        """Peek at what the remaining undealt community cards would be if the hand continued to River."""
        if len(self.board_cards) >= 5 or not self.deck:
            return []
        sim_deck = list(self.deck)
        sim_board_len = len(self.board_cards)
        rabbits: list[str] = []
        while sim_board_len < 5 and sim_deck:
            if sim_board_len in (0, 3, 4) and len(sim_deck) > 1:
                sim_deck.pop()
            if sim_deck:
                rabbits.append(sim_deck.pop())
                sim_board_len += 1
        return rabbits

    def start_hand(self, bomb_pot: bool = False) -> tuple[bool, str]:
        if (self.street not in ("idle", "showdown") or self.all_in_runout) and self.pot > 0:
            return False, "Ván hiện tại đang diễn ra! Không thể chia ván mới lúc này."

        # Auto rebuy for Bots that busted out
        for p in self.players.values():
            if p.is_bot and p.stack <= 0 and not p.sitting_out:
                p.stack = self.default_buy_in
                p.total_buy_in += self.default_buy_in
                self._log_action(f"🤖 {p.name} tự động nạp lại (Rebuy) +{format_chips(self.default_buy_in)}", category="money", player_id=p.id)

        eligible = self._eligible_for_new_hand()
        if len(eligible) < 2:
            return False, "Cần ít nhất 2 người chơi còn chip (Stack > 0) tại bàn để bắt đầu chia bài!"

        self.hand_number += 1
        self.is_bomb_pot = bool(bomb_pot)
        self.street = "flop" if self.is_bomb_pot else "preflop"
        self.all_in_runout = False
        self.current_bet = 0
        self.min_raise_delta = self.big_blind
        self.pot = 0
        self.pots = []
        self.deck = create_shuffled_deck()
        self.board_cards = []
        self.rabbit_cards = []
        self.rabbit_revealed = False
        self.winning_cards = []
        self.last_showdown_summary = ""
        self._last_hand_meta = None

        # Reset all players & deal 2 private hole cards to eligible players
        for p in self.sorted_players():
            p.current_bet = 0
            p.total_hand_bet = 0
            p.acted_this_round = False
            p.revealed = False
            p.revealed_mask = [False, False]
            p.last_won_amount = 0
            p.last_hand_bet = 0
            p.last_hand_delta = 0
            p.last_hand_outcome = ""
            p.showdown_hand_name = ""
            p.showdown_best5 = []
            p.ready_next = False
            if p.stack > 0 and not p.sitting_out:
                p.status = "active"
                p.last_action = "Đã nhận 2 lá tẩy"
                p.hole_cards = [self.deck.pop(), self.deck.pop()]
                p.hands_played += 1
            else:
                p.status = "out"
                p.hole_cards = []
                p.last_action = "Tạm nghỉ" if p.sitting_out else "Hết chip (0)"

        # Rotate dealer button
        dealer_player = self._next_seat_in_list(self.dealer_seat, eligible)
        self.dealer_seat = dealer_player.seat

        if self.is_bomb_pot:
            # BOMB POT: Everyone posts 2x Big Blind straight into the Pot, skip Pre-Flop, deal Flop immediately!
            self.sb_seat = -1
            self.bb_seat = -1
            bomb_amount = self.big_blind * 2
            self._log_action(
                f"💣 === VÁN BOMB POT ĐẶC BIỆT #{self.hand_number} (Dealer: {dealer_player.name}) — Mỗi người góp {format_chips(bomb_amount)} vào thẳng FLOP! ===",
                category="street",
            )
            for p in eligible:
                posted = self._post_forced_bet(p, bomb_amount, "Bomb Pot", counts_toward_street_bet=False)
                if posted > 0:
                    self._log_action(
                        f"💣 {p.name} góp Bomb Pot {format_chips(posted)}",
                        category="blind",
                        player_id=p.id,
                        amount=posted,
                    )
            self._deal_community_up_to(3)
            board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
            self._log_action(f"🃏 [BOMB POT] Mở thẳng 3 lá FLOP: [{board_str}]", category="street")
            self.current_bet = 0
            self.min_raise_delta = self.big_blind
            self._recalculate_pots()

            can_act = self._can_act_players()
            if len(can_act) <= 1:
                self._enter_all_in_runout()
            else:
                first_actor = self._next_seat_in_list(dealer_player.seat, can_act)
                self._set_turn_seat(first_actor.seat)
            return True, f"💣 Đã chia Ván BOMB POT #{self.hand_number} — Mở thẳng 3 lá Flop!"

        if len(eligible) == 2:
            sb_player = dealer_player
            bb_player = self._next_seat_in_list(sb_player.seat, eligible)
            first_actor = sb_player
        else:
            sb_player = self._next_seat_in_list(dealer_player.seat, eligible)
            bb_player = self._next_seat_in_list(sb_player.seat, eligible)
            first_actor = self._next_seat_in_list(bb_player.seat, eligible)

        self.sb_seat = sb_player.seat
        self.bb_seat = bb_player.seat

        self._log_action(
            f"🃏 === CHIA BÀI VÁN #{self.hand_number} (Dealer: {dealer_player.name}) ===",
            category="street",
        )

        # 1. Post Antes
        if self.ante > 0:
            for p in eligible:
                posted_ante = self._post_forced_bet(p, self.ante, "Ante", counts_toward_street_bet=False)
                if posted_ante > 0:
                    self._log_action(
                        f"🪙 {p.name} đóng Ante {format_chips(posted_ante)}",
                        category="blind",
                        player_id=p.id,
                        amount=posted_ante,
                    )

        # 2. Post SB & BB
        sb_posted = self._post_forced_bet(sb_player, self.small_blind, "SB", counts_toward_street_bet=True)
        self._log_action(
            f"🔹 {sb_player.name} đóng Small Blind (SB): {format_chips(sb_posted)}",
            category="blind",
            player_id=sb_player.id,
            amount=sb_posted,
        )

        bb_posted = self._post_forced_bet(bb_player, self.big_blind, "BB", counts_toward_street_bet=True)
        self._log_action(
            f"🔷 {bb_player.name} đóng Big Blind (BB): {format_chips(bb_posted)}",
            category="blind",
            player_id=bb_player.id,
            amount=bb_posted,
        )

        self.current_bet = max(sb_player.current_bet, bb_player.current_bet, self.big_blind)
        self.min_raise_delta = self.big_blind
        self._recalculate_pots()

        can_act = self._can_act_players()
        if not can_act:
            self._enter_all_in_runout()
        else:
            if first_actor.status == "active" and first_actor.stack > 0:
                self._set_turn_seat(first_actor.seat)
            else:
                next_actor = self._next_seat_in_list(first_actor.seat, can_act)
                self._set_turn_seat(next_actor.seat)

            if len(can_act) == 1 and can_act[0].current_bet >= max(p.current_bet for p in self._active_hand_players()):
                self._enter_all_in_runout()

        return True, f"Đã chia bài Ván #{self.hand_number}!"

    # ------------------------------------------------------------------
    # Pot & Side Pot Calculation
    # ------------------------------------------------------------------
    def _recalculate_pots(self) -> None:
        self.pot = sum(p.total_hand_bet for p in self.players.values())
        if self.pot == 0:
            self.pots = []
            return

        non_folded = [p for p in self.sorted_players() if p.status in ("active", "all_in") and p.total_hand_bet > 0]
        all_contributors = [p for p in self.sorted_players() if p.total_hand_bet > 0]

        if not non_folded:
            self.pots = [{
                "index": 0,
                "name": "Main Pot",
                "amount": self.pot,
                "eligiblePlayerIds": [p.id for p in self.sorted_players()],
                "eligiblePlayerNames": [p.name for p in self.sorted_players()],
            }]
            return

        levels = sorted({p.total_hand_bet for p in non_folded if p.total_hand_bet > 0})
        max_total_bet = max(p.total_hand_bet for p in all_contributors)
        if not levels or levels[-1] < max_total_bet:
            levels.append(max_total_bet)

        raw_slices: list[dict] = []
        prev = 0
        for lvl in levels:
            if lvl <= prev:
                continue
            slice_amount = 0
            for p in all_contributors:
                if p.total_hand_bet > prev:
                    slice_amount += min(p.total_hand_bet, lvl) - prev

            eligible = [p for p in non_folded if p.total_hand_bet >= lvl]
            if not eligible:
                top_nf = max(p.total_hand_bet for p in non_folded)
                eligible = [p for p in non_folded if p.total_hand_bet == top_nf]

            if slice_amount > 0:
                raw_slices.append({
                    "amount": slice_amount,
                    "eligible_ids": [p.id for p in eligible],
                    "eligible_names": [p.name for p in eligible],
                })
            prev = lvl

        merged: list[dict] = []
        for s in raw_slices:
            if merged and merged[-1]["eligible_ids"] == s["eligible_ids"]:
                merged[-1]["amount"] += s["amount"]
            else:
                merged.append(s)

        self.pots = []
        for idx, m in enumerate(merged):
            name = "Main Pot (Pot Chính)" if idx == 0 else f"Side Pot {idx} (Pot Phụ {idx})"
            self.pots.append({
                "index": idx,
                "name": name,
                "amount": m["amount"],
                "eligiblePlayerIds": m["eligible_ids"],
                "eligiblePlayerNames": m["eligible_names"],
            })

    # ------------------------------------------------------------------
    # Player Betting Actions & Turn Timeout
    # ------------------------------------------------------------------
    def player_action(
        self,
        player_id: str,
        action: str,
        amount: int = 0,
    ) -> tuple[bool, str]:
        if self.street in ("idle", "showdown") or self.all_in_runout:
            return False, "Hiện không ở trong vòng đặt cược."

        player = self.players.get(player_id)
        if not player:
            return False, "Không tìm thấy người chơi."

        if player.seat != self.turn_seat:
            return False, f"Chưa đến lượt của {player.name}."

        if player.status != "active":
            return False, f"{player.name} không thể hành động ({player.status})."

        act = action.strip().lower()
        to_call = max(0, self.current_bet - player.current_bet)

        if act == "fold":
            player.status = "folded"
            player.acted_this_round = True
            player.last_action = "Fold (Úp bài)"
            self._log_action(f"❌ {player.name} chọn FOLD (Úp bài)", category="fold", player_id=player.id)

        elif act == "check":
            if to_call > 0:
                return False, f"Không thể Check! Cần theo (Call) {format_chips(to_call)} hoặc Fold/Raise."
            player.acted_this_round = True
            player.last_action = "Check (Xem)"
            self._log_action(f"✔️ {player.name} chọn CHECK (Xem bài)", category="check", player_id=player.id)

        elif act == "call":
            if to_call <= 0:
                player.acted_this_round = True
                player.last_action = "Check (Xem)"
                self._log_action(f"✔️ {player.name} chọn CHECK", category="check", player_id=player.id)
            else:
                paid = min(player.stack, to_call)
                player.stack -= paid
                player.current_bet += paid
                player.total_hand_bet += paid
                player.acted_this_round = True
                if player.stack == 0:
                    player.status = "all_in"
                    player.last_action = f"Call All-in ({format_chips(player.current_bet)})"
                    self._log_action(
                        f"🔥 {player.name} CALL ALL-IN +{format_chips(paid)} (Tổng vòng: {format_chips(player.current_bet)})",
                        category="all_in",
                        player_id=player.id,
                        amount=paid,
                    )
                else:
                    player.last_action = f"Call {format_chips(player.current_bet)}"
                    self._log_action(
                        f"📞 {player.name} CALL +{format_chips(paid)} (Theo mức {format_chips(player.current_bet)})",
                        category="call",
                        player_id=player.id,
                        amount=paid,
                    )

        elif act == "all_in":
            if player.stack <= 0:
                return False, f"{player.name} không còn chip để All-in."
            paid = player.stack
            player.stack = 0
            player.current_bet += paid
            player.total_hand_bet += paid
            player.status = "all_in"
            player.acted_this_round = True

            if player.current_bet > self.current_bet:
                raise_delta = player.current_bet - self.current_bet
                if raise_delta >= self.min_raise_delta:
                    self.min_raise_delta = raise_delta
                self.current_bet = player.current_bet
                for other in self.players.values():
                    if other.id != player.id and other.status == "active":
                        other.acted_this_round = False

            player.last_action = f"ALL-IN {format_chips(player.current_bet)}"
            self._log_action(
                f"🔥 {player.name} TẤT TAY (ALL-IN) +{format_chips(paid)} (Lên {format_chips(player.current_bet)})",
                category="all_in",
                player_id=player.id,
                amount=paid,
            )

        elif act in ("bet", "raise"):
            target_bet = int(amount)
            max_possible_bet = player.current_bet + player.stack

            if target_bet >= max_possible_bet:
                return self.player_action(player_id, "all_in")

            min_legal_target = self.current_bet + self.min_raise_delta if self.current_bet > 0 else self.big_blind
            if target_bet < min_legal_target:
                return (
                    False,
                    f"Mức tố tối thiểu phải đạt {format_chips(min_legal_target)} {self.currency} (hoặc All-in {format_chips(max_possible_bet)}).",
                )

            paid = target_bet - player.current_bet
            if paid <= 0:
                return False, "Số tiền tố thêm phải lớn hơn mức cược hiện tại của bạn."

            raise_delta = target_bet - self.current_bet
            if raise_delta > self.min_raise_delta:
                self.min_raise_delta = raise_delta

            was_unopened = self.current_bet == 0
            self.current_bet = target_bet
            player.stack -= paid
            player.current_bet = target_bet
            player.total_hand_bet += paid
            player.acted_this_round = True

            for other in self.players.values():
                if other.id != player.id and other.status == "active":
                    other.acted_this_round = False

            verb = "Bet" if was_unopened else "Raise"
            player.last_action = f"{verb} {format_chips(target_bet)}"
            self._log_action(
                f"🚀 {player.name} {verb.upper()} lên {format_chips(target_bet)} (+{format_chips(paid)})",
                category="raise",
                player_id=player.id,
                amount=paid,
            )
        else:
            return False, f"Hành động '{action}' không hợp lệ."

        self._recalculate_pots()
        self._check_single_survivor_or_round_end()
        return True, "OK"

    def force_timeout_fold(self, expected_seq: int | None = None) -> tuple[bool, str]:
        """Auto-fold the active turn player when their turn countdown expires."""
        if self.street in ("idle", "showdown") or self.all_in_runout or self.turn_seat < 0:
            return False, ""
        if expected_seq is not None and self.turn_seq != expected_seq:
            return False, ""
        player = self.get_player_by_seat(self.turn_seat)
        if not player or player.status != "active":
            return False, ""

        player.status = "folded"
        player.acted_this_round = True
        player.last_action = "⏰ Hết giờ (Fold)"
        self._log_action(
            f"⏰ Hết thời gian suy nghĩ ({self.turn_timeout}s)! {player.name} tự động FOLD (Bỏ bài).",
            category="fold",
            player_id=player.id,
        )
        self._recalculate_pots()
        self._check_single_survivor_or_round_end()
        return True, f"⏰ {player.name} hết giờ ({self.turn_timeout}s) nên tự động bỏ bài (Fold)!"

    def cancel_hand(self) -> tuple[bool, str]:
        if self.street in ("idle", "showdown") and self.pot <= 0:
            return False, "Hiện không có ván nào đang diễn ra để hủy."
        for p in self.players.values():
            if p.total_hand_bet > 0:
                p.stack += p.total_hand_bet
            p.current_bet = 0
            p.total_hand_bet = 0
            p.acted_this_round = False
            p.revealed = False
            p.revealed_mask = [False, False]
            p.last_won_amount = 0
            p.last_hand_bet = 0
            p.last_hand_delta = 0
            p.last_hand_outcome = ""
            if p.status != "out":
                p.status = "waiting"
                p.last_action = "Đã hoàn tiền"
        self.pot = 0
        self.pots = []
        self.current_bet = 0
        self.board_cards = []
        self.rabbit_cards = []
        self.rabbit_revealed = False
        self.winning_cards = []
        self._last_hand_meta = None
        self.all_in_runout = False
        self.street = "idle"
        self._set_turn_seat(-1)
        self._log_action("⚠️ Chủ bàn đã hủy ván hiện tại và hoàn trả toàn bộ tiền cược về từng người.", category="system")
        return True, "Đã hủy ván và hoàn trả tiền cược."

    def _check_single_survivor_or_round_end(self) -> None:
        survivors = self._active_hand_players()
        if len(survivors) == 1:
            winner = survivors[0]
            won_amount = self.pot
            winner.stack += won_amount
            winner.last_won_amount = won_amount
            winner.last_hand_bet = winner.total_hand_bet
            winner.last_hand_delta = won_amount - winner.total_hand_bet
            winner.last_hand_outcome = "winner"
            winner.hands_won += 1
            winner.biggest_pot_won = max(winner.biggest_pot_won, won_amount)
            net_gain = winner.last_hand_delta
            winner.last_action = f"🏆 Thắng +{format_chips(won_amount)} (Lời +{format_chips(net_gain)})"

            # Save undealt community cards for Rabbit Hunting
            self.rabbit_cards = self._capture_rabbit_cards()
            self.rabbit_revealed = False

            participant_ids = []
            loser_records = []
            for p in self.sorted_players():
                if p.total_hand_bet > 0 or len(p.hole_cards) == 2:
                    participant_ids.append(p.id)
                if p.id != winner.id:
                    p.last_won_amount = 0
                    p.last_hand_bet = p.total_hand_bet
                    p.last_hand_delta = -p.total_hand_bet
                    if p.total_hand_bet > 0 or len(p.hole_cards) == 2:
                        p.last_hand_outcome = "loser_folded"
                        if p.total_hand_bet > 0:
                            p.last_action = f"🏳️ Bỏ bài (-{format_chips(p.total_hand_bet)})"
                            loser_records.append({
                                "id": p.id,
                                "name": p.name,
                                "lost": p.total_hand_bet,
                                "reason": "Bỏ bài (Fold)",
                            })
                        else:
                            p.last_action = "🏳️ Bỏ bài (0)"
                    else:
                        p.last_hand_outcome = ""
                    if p.status != "out":
                        p.status = "waiting"
                p.current_bet = 0
                p.total_hand_bet = 0
                p.acted_this_round = False

            winner.status = "waiting"

            for p in self.players.values():
                p.ready_next = p.is_bot

            self.last_showdown_summary = (
                f"🏆 {winner.name} thắng Pot +{format_chips(won_amount)} {self.currency} "
                f"(Lời ròng +{format_chips(net_gain)}) do tất cả đối thủ đã Bỏ bài (Fold)!"
            )
            self._last_hand_meta = {
                "handNumber": self.hand_number,
                "endType": "fold",
                "endReason": "Tất cả đối thủ đều Bỏ bài (Fold)",
                "totalPot": won_amount,
                "isBombPot": self.is_bomb_pot,
                "winnerIds": [winner.id],
                "participantIds": participant_ids,
            }
            self.hand_history.append({
                "hand": self.hand_number,
                "time": now_time_str(),
                "totalPot": won_amount,
                "board": list(self.board_cards),
                "reason": self.last_showdown_summary,
                "winners": [{"id": winner.id, "name": winner.name, "amount": won_amount, "net": net_gain, "hand": "Đối thủ Fold"}],
                "losers": loser_records,
            })
            self._log_action(
                f"🏆 Tất cả đối thủ đã Fold! {winner.name} thắng trọn Pot +{format_chips(won_amount)} {self.currency} (Lời +{format_chips(net_gain)})!",
                category="win",
                player_id=winner.id,
                amount=won_amount,
            )
            self.pot = 0
            self.pots = []
            self.current_bet = 0
            self.all_in_runout = False
            self.street = "showdown"
            self._set_turn_seat(-1)
            return

        self._advance_turn_or_street()

    def _is_betting_round_complete(self) -> bool:
        can_act = self._can_act_players()
        if not can_act:
            return True
        for p in can_act:
            if not p.acted_this_round or p.current_bet != self.current_bet:
                return False
        return True

    def _advance_turn_or_street(self) -> None:
        if self._is_betting_round_complete():
            self._move_to_next_street()
            return

        can_act = self._can_act_players()
        if not can_act:
            self._move_to_next_street()
            return

        next_player = self._next_seat_in_list(self.turn_seat, can_act)
        self._set_turn_seat(next_player.seat)

    def _enter_all_in_runout(self) -> None:
        """Enter dramatic step-by-step All-in Runout: reveal active hole cards first, then deal streets one by one."""
        for p in self.players.values():
            p.current_bet = 0
            p.acted_this_round = False
        self.current_bet = 0
        self._set_turn_seat(-1)

        # Reveal all non-folded players' hole cards immediately so everyone can watch the runout
        for p in self._active_hand_players():
            p.revealed = True
            p.revealed_mask = [True, True]

        self.all_in_runout = True
        self._log_action(
            "🔥 ALL-IN SHOWDOWN! Tất cả người chơi lật bài tẩy — đang mở bài chung từng vòng...",
            category="all_in",
        )

    def advance_all_in_runout_step(self) -> tuple[bool, str]:
        """Advance one street during an All-in Runout (called with a smooth delay by the room task)."""
        if not self.all_in_runout or self.street in ("idle", "showdown"):
            self.all_in_runout = False
            return False, "none"

        if self.street == "preflop":
            self.street = "flop"
            self._deal_community_up_to(3)
            board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
            self._log_action(f"🃏 [ALL-IN] Mở 3 lá FLOP: [{board_str}]", category="street")
            return True, "deal"

        if self.street == "flop":
            self.street = "turn"
            self._deal_community_up_to(4)
            board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
            self._log_action(f"🃏 [ALL-IN] Mở lá thứ 4 TURN: [{board_str}]", category="street")
            return True, "deal"

        if self.street == "turn":
            self.street = "river"
            self._deal_community_up_to(5)
            board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
            self._log_action(f"🃏 [ALL-IN] Mở lá thứ 5 RIVER: [{board_str}]", category="street")
            return True, "deal"

        # From river -> resolve Showdown
        self.all_in_runout = False
        self._runout_to_showdown()
        return True, "win"

    def _runout_to_showdown(self) -> None:
        for p in self.players.values():
            p.current_bet = 0
            p.acted_this_round = False
        self.current_bet = 0
        self.all_in_runout = False
        self._set_turn_seat(-1)
        self._deal_community_up_to(5)
        self.street = "showdown"
        board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
        self._log_action(f"🃏 Lật đủ 5 lá bài chung: [{board_str}] ➔ SHOWDOWN!", category="street")
        self._resolve_showdown_automatically()

    def _move_to_next_street(self) -> None:
        for p in self.players.values():
            p.current_bet = 0
            p.acted_this_round = False
            if p.status == "active":
                p.last_action = "Chờ lượt"

        self.current_bet = 0
        self.min_raise_delta = self.big_blind

        if self.street == "river":
            self._runout_to_showdown()
            return

        can_act = self._can_act_players()
        if len(can_act) <= 1:
            self._enter_all_in_runout()
            return

        try:
            idx = STREET_ORDER.index(self.street)
            next_street: Street = STREET_ORDER[min(idx + 1, len(STREET_ORDER) - 1)]
        except ValueError:
            next_street = "showdown"

        self.street = next_street
        if self.street == "flop":
            self._deal_community_up_to(3)
        elif self.street == "turn":
            self._deal_community_up_to(4)
        elif self.street == "river":
            self._deal_community_up_to(5)
        elif self.street == "showdown":
            self._runout_to_showdown()
            return

        board_str = " ".join(f"{serialize_card(c)['rank']}{serialize_card(c)['suitSymbol']}" for c in self.board_cards)
        first_postflop = self._next_seat_in_list(self.dealer_seat, can_act)
        self._set_turn_seat(first_postflop.seat)
        self._log_action(
            f"➡️ {STREET_LABELS_VI.get(self.street, self.street)} [{board_str}] (Lượt đầu: {first_postflop.name})",
            category="street",
        )

    # ------------------------------------------------------------------
    # Automatic Showdown Evaluation & Pot Distribution
    # ------------------------------------------------------------------
    def _resolve_showdown_automatically(self) -> None:
        if self.pot <= 0:
            return

        self._recalculate_pots()
        survivors = self._active_hand_players()
        eval_map: dict[str, dict] = {}

        for p in survivors:
            p.revealed = True
            p.revealed_mask = [True, True]
            ev = evaluate_best_hand(p.hole_cards, self.board_cards)
            if ev:
                eval_map[p.id] = ev
                p.showdown_hand_name = ev["name"]
                p.showdown_best5 = ev["best5"]

        allocations: list[dict] = []
        winning_cards_set: set[str] = set()

        for pot_slice in self.pots:
            idx = pot_slice["index"]
            eligible_ids = [pid for pid in pot_slice["eligiblePlayerIds"] if pid in eval_map]
            if not eligible_ids:
                eligible_ids = list(pot_slice["eligiblePlayerIds"])

            best_score: list[int] | None = None
            winners: list[str] = []
            for pid in eligible_ids:
                ev = eval_map.get(pid)
                score = ev["score"] if ev else [-1]
                if best_score is None or score > best_score:
                    best_score = score
                    winners = [pid]
                elif score == best_score:
                    winners.append(pid)

            allocations.append({"potIndex": idx, "winnerIds": winners})
            for wid in winners:
                if wid in eval_map:
                    winning_cards_set.update(eval_map[wid]["best5"])

        self.winning_cards = list(winning_cards_set)
        self._apply_pot_allocations(allocations)

    def _apply_pot_allocations(self, allocations: list[dict]) -> tuple[bool, str]:
        alloc_map = {int(a["potIndex"]): [str(w) for w in a["winnerIds"]] for a in allocations}
        total_awarded_by_player: dict[str, int] = {}
        pot_summary_parts: list[str] = []

        for pot_slice in self.pots:
            idx = pot_slice["index"]
            slice_amount = int(pot_slice["amount"])
            winner_ids = alloc_map.get(idx, [])
            winners = [self.players[wid] for wid in winner_ids if wid in self.players]
            if not winners:
                continue

            ordered_winners = self._order_clockwise_after_dealer(winners)
            share = slice_amount // len(ordered_winners)
            remainder = slice_amount % len(ordered_winners)

            for i, w in enumerate(ordered_winners):
                gain = share + (1 if i < remainder else 0)
                w.stack += gain
                total_awarded_by_player[w.id] = total_awarded_by_player.get(w.id, 0) + gain

            w_desc = ", ".join(
                f"{w.name} ({w.showdown_hand_name})" if w.showdown_hand_name else w.name
                for w in ordered_winners
            )
            pot_summary_parts.append(f"{pot_slice['name']} ({format_chips(slice_amount)}) ➔ {w_desc}")

        hand_total_pot = self.pot
        self.rabbit_cards = []
        self.rabbit_revealed = False

        participant_ids: list[str] = []
        winner_records: list[dict] = []
        loser_records: list[dict] = []

        for p in self.sorted_players():
            p.last_hand_bet = p.total_hand_bet
            won_amt = total_awarded_by_player.get(p.id, 0)
            p.last_won_amount = won_amt
            p.last_hand_delta = won_amt - p.total_hand_bet

            if p.total_hand_bet > 0 or len(p.hole_cards) == 2:
                participant_ids.append(p.id)

            if won_amt > 0:
                p.last_hand_outcome = "winner"
                p.hands_won += 1
                p.biggest_pot_won = max(p.biggest_pot_won, won_amt)
                hand_tag = f" - {p.showdown_hand_name}" if p.showdown_hand_name else ""
                p.last_action = f"🏆 Thắng +{format_chips(won_amt)}{hand_tag}"
                winner_records.append({
                    "id": p.id,
                    "name": p.name,
                    "amount": won_amt,
                    "net": p.last_hand_delta,
                    "hand": p.showdown_hand_name or "Thắng Pot",
                })
            else:
                if p.status == "folded":
                    p.last_hand_outcome = "loser_folded" if (p.total_hand_bet > 0 or len(p.hole_cards) == 2) else ""
                    if p.total_hand_bet > 0:
                        p.last_action = f"🏳️ Bỏ bài (-{format_chips(p.total_hand_bet)})"
                        loser_records.append({
                            "id": p.id,
                            "name": p.name,
                            "lost": p.total_hand_bet,
                            "reason": "Bỏ bài (Fold)",
                        })
                elif p.total_hand_bet > 0 or len(p.hole_cards) == 2:
                    p.last_hand_outcome = "loser_showdown"
                    hand_tag = f" ({p.showdown_hand_name})" if p.showdown_hand_name else ""
                    p.last_action = f"💔 Thua -{format_chips(p.total_hand_bet)}{hand_tag}"
                    loser_records.append({
                        "id": p.id,
                        "name": p.name,
                        "lost": p.total_hand_bet,
                        "reason": p.showdown_hand_name or "Thua Showdown",
                    })
                else:
                    p.last_hand_outcome = ""

            p.current_bet = 0
            p.total_hand_bet = 0
            p.acted_this_round = False

        summary_text = " | ".join(pot_summary_parts)
        self.last_showdown_summary = f"🏆 {summary_text}"
        self._last_hand_meta = {
            "handNumber": self.hand_number,
            "endType": "showdown",
            "endReason": summary_text,
            "totalPot": hand_total_pot,
            "isBombPot": self.is_bomb_pot,
            "winnerIds": list(total_awarded_by_player.keys()),
            "participantIds": participant_ids,
        }
        self.hand_history.append({
            "hand": self.hand_number,
            "time": now_time_str(),
            "totalPot": hand_total_pot,
            "board": list(self.board_cards),
            "reason": summary_text,
            "winners": winner_records,
            "losers": loser_records,
        })
        self._log_action(
            f"🏆 KẾT QUẢ SHOWDOWN VÁN #{self.hand_number}: {summary_text}",
            category="win",
            amount=hand_total_pot,
        )

        self.pot = 0
        self.pots = []
        self.current_bet = 0
        self.all_in_runout = False
        self.street = "showdown"
        self._set_turn_seat(-1)
        for p in self.players.values():
            p.ready_next = p.is_bot
        return True, f"Kết quả ván #{self.hand_number}: {summary_text}"

    def _build_last_hand_result(self, viewer_player_id: str | None = None) -> dict | None:
        """Build detailed Winner vs Loser scoreboard for the finished hand, respecting per-player card privacy."""
        if not self._last_hand_meta or self.street not in ("idle", "showdown"):
            return None

        meta = self._last_hand_meta
        winner_set = set(meta.get("winnerIds", []))
        part_ids = meta.get("participantIds", [])

        winners_list: list[dict] = []
        losers_list: list[dict] = []

        for pid in part_ids:
            p = self.players.get(pid)
            if not p:
                continue
            is_viewer = viewer_player_id is not None and p.id == viewer_player_id
            show_all = is_viewer or p.revealed

            cards_serialized = []
            hand_eval_name = p.showdown_hand_name
            for idx, c in enumerate(p.hole_cards):
                if show_all or (idx < len(p.revealed_mask) and p.revealed_mask[idx]):
                    cards_serialized.append(serialize_card(c))
                else:
                    cards_serialized.append(serialize_card("??"))

            if show_all and p.hole_cards:
                ev = evaluate_best_hand(p.hole_cards, self.board_cards)
                if ev and not hand_eval_name:
                    hand_eval_name = ev["name"]

            entry = {
                "id": p.id,
                "name": p.name,
                "avatar": p.avatar,
                "seat": p.seat,
                "isMe": is_viewer,
                "wonAmount": p.last_won_amount,
                "betAmount": p.last_hand_bet,
                "lostAmount": abs(p.last_hand_delta) if p.last_hand_delta < 0 else p.last_hand_bet,
                "netDelta": p.last_hand_delta,
                "stackAfter": p.stack,
                "busted": p.stack <= 0,
                "isBusted": p.stack <= 0,
                "outcome": p.last_hand_outcome,
                "holeCards": cards_serialized,
                "revealed": p.revealed,
                "revealedMask": list(p.revealed_mask),
                "handName": hand_eval_name or (
                    "Thắng do đối thủ Fold" if p.id in winner_set else ("Đã Bỏ bài (Fold)" if p.last_hand_outcome == "loser_folded" else "Thua Showdown")
                ),
                "statusBadge": (
                    "🏆 THẮNG POT"
                    if p.id in winner_set
                    else ("🏳️ ĐÃ BỎ BÀI (FOLD)" if p.last_hand_outcome == "loser_folded" else "💔 THUA SHOWDOWN")
                ),
            }
            if p.id in winner_set:
                winners_list.append(entry)
            else:
                losers_list.append(entry)

        winners_list.sort(key=lambda x: (-x["wonAmount"], x["seat"]))
        losers_list.sort(key=lambda x: (x["netDelta"], x["seat"]))

        my_outcome = None
        for item in winners_list + losers_list:
            if item.get("isMe"):
                my_outcome = item
                break

        return {
            "handNumber": meta["handNumber"],
            "endType": meta["endType"],
            "endedBy": meta["endType"],
            "endReason": meta["endReason"],
            "reason": meta["endReason"],
            "totalPot": meta["totalPot"],
            "currency": self.currency,
            "isBombPot": meta.get("isBombPot", False),
            "boardCards": [serialize_card(c) for c in self.board_cards],
            "rabbitCards": [serialize_card(c) for c in self.rabbit_cards] if self.rabbit_revealed else [],
            "rabbitRevealed": self.rabbit_revealed,
            "canRabbitHunt": len(self.rabbit_cards) > 0 and not self.rabbit_revealed,
            "myOutcome": my_outcome,
            "winners": winners_list,
            "losers": losers_list,
        }

    def set_player_ready(self, player_id: str, ready: bool = True) -> tuple[bool, str, bool]:
        """Mark a seated player as ready for the next hand. Returns (success, message, all_ready)."""
        p = self.players.get(player_id)
        if not p:
            return False, "Không tìm thấy người chơi.", False
        if p.sitting_out or p.stack <= 0:
            return False, "Không thể sẵn sàng do đang tạm nghỉ hoặc hết chip.", False

        p.ready_next = ready
        eligible = [pl for pl in self.sorted_players() if pl.stack > 0 and not pl.sitting_out]
        if len(eligible) < 2:
            return True, "Cần tối thiểu 2 người có chip để bắt đầu ván mới.", False

        all_ready = all(pl.ready_next for pl in eligible)
        ready_count = sum(1 for pl in eligible if pl.ready_next)
        total_count = len(eligible)
        return True, f"{p.name} đã sẵn sàng ({ready_count}/{total_count})", all_ready

    def _order_clockwise_after_dealer(self, candidates: list[Player]) -> list[Player]:
        if len(candidates) <= 1:
            return candidates
        sorted_c = sorted(candidates, key=lambda p: p.seat)
        after = [p for p in sorted_c if p.seat > self.dealer_seat]
        before = [p for p in sorted_c if p.seat <= self.dealer_seat]
        return after + before

    # ------------------------------------------------------------------
    # Smart Poker Bot AI Decision Engine
    # ------------------------------------------------------------------
    def compute_bot_action(self, player_id: str) -> tuple[str, int]:
        p = self.players.get(player_id)
        if not p or p.status != "active":
            return "check", 0

        to_call = max(0, self.current_bet - p.current_bet)
        max_target = p.current_bet + p.stack
        min_raise_target = min(
            max_target,
            self.current_bet + self.min_raise_delta if self.current_bet > 0 else self.big_blind,
        )
        can_raise = max_target > self.current_bet

        ev = evaluate_best_hand(p.hole_cards, self.board_cards)
        cat = ev["category"] if ev else 0

        if len(self.board_cards) == 0:
            v1 = RANK_VALUES.get(p.hole_cards[0][0], 2) if len(p.hole_cards) > 0 else 2
            v2 = RANK_VALUES.get(p.hole_cards[1][0], 2) if len(p.hole_cards) > 1 else 2
            suited = (len(p.hole_cards) == 2 and p.hole_cards[0][1] == p.hole_cards[1][1])
            hi, lo = max(v1, v2), min(v1, v2)
            if hi == lo:
                strength = 0.58 + (hi / 14.0) * 0.38
            else:
                strength = (hi + lo * 0.6) / 23.0 + (0.07 if suited else 0.0) - (0.05 if hi - lo > 4 else 0.0)
            strength = max(0.1, min(0.98, strength))
        else:
            base_by_cat = {
                0: 0.25,
                1: 0.56,
                2: 0.76,
                3: 0.85,
                4: 0.90,
                5: 0.93,
                6: 0.97,
                7: 0.99,
                8: 1.00,
                9: 1.00,
            }
            strength = base_by_cat.get(cat, 0.3)

        noise = (_rng.random() - 0.5) * 0.14
        eff_strength = max(0.05, min(1.0, strength + noise))

        if to_call == 0:
            if eff_strength >= 0.68 and can_raise:
                pot_bet = self.current_bet + max(self.big_blind, (self.pot * 2) // 3)
                target = max(min_raise_target, min(max_target, pot_bet))
                return "raise", target
            return "check", 0

        pot_odds_ratio = to_call / max(1, self.pot + to_call)

        if eff_strength >= 0.80 and can_raise and to_call < p.stack // 2:
            target = max(min_raise_target, min(max_target, self.current_bet + max(self.big_blind * 2, self.pot)))
            return "raise", target

        if eff_strength >= 0.45 or to_call <= self.big_blind or eff_strength >= pot_odds_ratio + 0.12:
            return "call", 0

        return "fold", 0

    # ------------------------------------------------------------------
    # End-of-Session Settlement
    # ------------------------------------------------------------------
    def calculate_settlement(self) -> list[dict]:
        debtors: list[list] = []
        creditors: list[list] = []
        for p in self.sorted_players():
            net = p.net_profit
            if net < 0:
                debtors.append([p.name, -net])
            elif net > 0:
                creditors.append([p.name, net])

        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)

        transfers: list[dict] = []
        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            d_name, d_amt = debtors[i]
            c_name, c_amt = creditors[j]
            pay = min(d_amt, c_amt)
            if pay > 0:
                transfers.append({
                    "from": d_name,
                    "to": c_name,
                    "amount": pay,
                    "formatted": f"{d_name} chuyển trả {c_name}: {format_chips(pay)} {self.currency}",
                })
            debtors[i][1] -= pay
            creditors[j][1] -= pay
            if debtors[i][1] == 0:
                i += 1
            if creditors[j][1] == 0:
                j += 1

        return transfers

    # ------------------------------------------------------------------
    # Serialization for WebSocket Clients (STRICT PER-PLAYER PRIVACY)
    # ------------------------------------------------------------------
    def serialize(self, viewer_player_id: str | None = None) -> dict:
        self._recalculate_pots()
        turn_player = self.get_player_by_seat(self.turn_seat) if self.turn_seat >= 0 else None

        # Only provide active betting constraints if it's currently a live betting street
        turn_constraints = None
        if turn_player and self.street not in ("idle", "showdown") and not self.all_in_runout and turn_player.status == "active":
            to_call = max(0, self.current_bet - turn_player.current_bet)
            max_target_bet = turn_player.current_bet + turn_player.stack
            min_raise_target = (
                self.current_bet + self.min_raise_delta
                if self.current_bet > 0
                else self.big_blind
            )
            min_raise_target = min(min_raise_target, max_target_bet)
            pot_after_call = self.pot + min(turn_player.stack, to_call)

            turn_constraints = {
                "playerId": turn_player.id,
                "playerName": turn_player.name,
                "isBot": turn_player.is_bot,
                "seat": turn_player.seat,
                "stack": turn_player.stack,
                "currentBet": turn_player.current_bet,
                "tableCurrentBet": self.current_bet,
                "toCall": min(turn_player.stack, to_call),
                "rawToCall": to_call,
                "canCheck": to_call == 0,
                "canCall": to_call > 0,
                "canRaise": max_target_bet > self.current_bet,
                "minRaiseTarget": min_raise_target,
                "maxRaiseTarget": max_target_bet,
                "minRaiseDelta": self.min_raise_delta,
                "potAfterCall": pot_after_call,
                "presets": {
                    "minRaise": min_raise_target,
                    "halfPot": min(max_target_bet, max(min_raise_target, self.current_bet + pot_after_call // 2)),
                    "twoThirdPot": min(max_target_bet, max(min_raise_target, self.current_bet + (pot_after_call * 2) // 3)),
                    "fullPot": min(max_target_bet, max(min_raise_target, self.current_bet + pot_after_call)),
                    "twoXPot": min(max_target_bet, max(min_raise_target, self.current_bet + pot_after_call * 2)),
                    "allIn": max_target_bet,
                },
            }

        equities: dict[str, float] = {}
        if self.all_in_runout:
            equities = calculate_all_in_equities(self._active_hand_players(), self.board_cards)

        players_serialized = []
        for p in self.sorted_players():
            # STRICT PRIVACY: A client can ONLY see `p`'s hole cards if:
            # 1) `p.id == viewer_player_id` (this is the client's OWN seat!)
            # 2) `p.revealed` is True (at Showdown, All-in Runout, or when `p` voluntarily revealed their own hand)
            can_see = (viewer_player_id is not None and p.id == viewer_player_id) or p.revealed
            players_serialized.append(
                p.to_dict(
                    board_cards=self.board_cards,
                    can_see_hole_cards=can_see,
                    is_dealer=(p.seat == self.dealer_seat),
                    is_sb=(p.seat == self.sb_seat and self.street != "idle"),
                    is_bb=(p.seat == self.bb_seat and self.street != "idle"),
                    is_turn=(p.seat == self.turn_seat and self.street not in ("idle", "showdown") and not self.all_in_runout),
                    equity_pct=equities.get(p.id),
                )
            )

        total_buy_in_sum = sum(p.total_buy_in for p in self.players.values())
        total_chips_on_table = sum(p.stack + p.total_hand_bet for p in self.players.values())

        eligible_players = [p for p in self.sorted_players() if p.stack > 0 and not p.sitting_out]
        ready_count = sum(1 for p in eligible_players if p.ready_next)
        ready_total = len(eligible_players)
        all_ready = (ready_count >= ready_total and ready_total >= 2)

        has_active_timer = (
            self.turn_seat >= 0
            and self.street not in ("idle", "showdown")
            and not self.all_in_runout
            and self.turn_deadline > 0
        )
        remaining_ms = max(0, int((self.turn_deadline - time.time()) * 1000)) if has_active_timer else 0

        return {
            "handNumber": self.hand_number,
            "street": self.street,
            "streetLabel": STREET_LABELS_VI.get(self.street, self.street),
            "allInRunout": self.all_in_runout,
            "isBombPot": self.is_bomb_pot,
            "dealerSeat": self.dealer_seat,
            "sbSeat": self.sb_seat,
            "bbSeat": self.bb_seat,
            "turnSeat": self.turn_seat,
            "turnPlayerId": turn_player.id if turn_player else None,
            "turnPlayerName": turn_player.name if turn_player else None,
            "turnPlayerIsBot": turn_player.is_bot if turn_player else False,
            "isMyTurn": bool(
                turn_player
                and viewer_player_id
                and turn_player.id == viewer_player_id
                and not self.all_in_runout
                and self.street not in ("idle", "showdown")
            ),
            "turnSeq": self.turn_seq,
            "turnTimeoutSec": self.turn_timeout,
            "turnTotalMs": int(self.turn_timeout * 1000),
            "turnRemainingMs": remaining_ms,
            "turnConstraints": turn_constraints,
            "boardCards": [serialize_card(c) for c in self.board_cards],
            "rabbitCards": [serialize_card(c) for c in self.rabbit_cards] if self.rabbit_revealed else [],
            "rabbitRevealed": self.rabbit_revealed,
            "canRabbitHunt": len(self.rabbit_cards) > 0 and not self.rabbit_revealed and self.street in ("idle", "showdown"),
            "winningCards": self.winning_cards,
            "lastShowdownSummary": self.last_showdown_summary,
            "lastHandResult": self._build_last_hand_result(viewer_player_id),
            "readyCount": ready_count,
            "readyTotal": ready_total,
            "allReady": all_ready,
            "currentBet": self.current_bet,
            "minRaiseDelta": self.min_raise_delta,
            "pot": self.pot,
            "pots": self.pots,
            "settings": {
                "smallBlind": self.small_blind,
                "bigBlind": self.big_blind,
                "ante": self.ante,
                "defaultBuyIn": self.default_buy_in,
                "currency": self.currency,
                "turnTimeout": self.turn_timeout,
            },
            "players": players_serialized,
            "actionLog": self.action_log[-60:],
            "handHistory": self.hand_history[-40:],
            "ledgerLog": self.ledger_log[-60:],
            "settlement": self.calculate_settlement(),
            "summary": {
                "totalBuyIn": total_buy_in_sum,
                "totalChipsOnTable": total_chips_on_table,
                "playerCount": len(self.players),
            },
        }
