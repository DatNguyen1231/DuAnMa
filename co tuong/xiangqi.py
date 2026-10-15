from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

try:
    import pyffish
    HAS_PYFFISH = True
except ImportError:
    HAS_PYFFISH = False

Color = Literal["red", "black"]

PIECE_NAMES_VI: dict[str, str] = {
    "K": "voi",
    "A": "Sĩ",
    "B": "Tượng",
    "N": "Mã",
    "R": "Xe",
    "C": "Pháo",
    "P": "Binh",
    "k": "Tướng",
    "a": "Sĩ",
    "b": "Tượng",
    "n": "Mã",
    "r": "Xe",
    "c": "Pháo",
    "p": "Tốt",
}

PIECE_CHARS_HAN: dict[str, str] = {
    "K": "帥",
    "A": "仕",
    "B": "相",
    "N": "傌",
    "R": "俥",
    "C": "炮",
    "P": "兵",
    "k": "將",
    "a": "士",
    "b": "象",
    "n": "馬",
    "r": "車",
    "c": "砲",
    "p": "卒",
}

FILES = "abcdefghi"
BOARD_COLS = 9
BOARD_ROWS = 10  # Ranks 1 to 10


def parse_move_uci(m: str) -> tuple[str, str]:
    m = m.strip().lower()
    if len(m) == 4:
        return m[:2], m[2:]
    if len(m) == 5:
        if m[1:3] == "10":
            return m[:3], m[3:]
        return m[:2], m[2:]
    if len(m) == 6:
        return m[:3], m[3:]
    raise ValueError(f"Invalid UCI move format: {m}")


def square_to_col_rank(sq: str) -> tuple[int, int]:
    sq = sq.strip().lower()
    col = ord(sq[0]) - ord("a")
    rank = int(sq[1:])
    return col, rank


def col_rank_to_square(col: int, rank: int) -> str:
    return f"{FILES[col]}{rank}"


def opponent(color: Color) -> Color:
    return "black" if color == "red" else "red"


def piece_color(symbol: str) -> Color:
    return "red" if symbol.isupper() else "black"


@dataclass(frozen=True)
class Move:
    from_square: str
    to_square: str
    uci: str
    captured: str | None = None


class Board:
    def __init__(self, fen: str | None = None) -> None:
        if fen:
            self._fen = fen
        elif HAS_PYFFISH:
            self._fen = pyffish.start_fen("xiangqi")
        else:
            self._fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

        self.history_uci: list[str] = []
        self.fen_history: list[str] = [self._fen.split()[0]]
        self._is_check: bool = False

    @property
    def fen_str(self) -> str:
        return self._fen

    def fen(self) -> str:
        return self._fen

    @property
    def turn(self) -> Color:
        parts = self._fen.split()
        if len(parts) > 1 and parts[1].lower() in {"w", "r"}:
            return "red"
        return "black"

    @property
    def fullmove_number(self) -> int:
        parts = self._fen.split()
        if len(parts) > 5 and parts[5].isdigit():
            return int(parts[5])
        return 1

    def piece_at(self, sq: str) -> str | None:
        grid = self.grid_map()
        return grid.get(sq.lower())

    def grid_map(self) -> dict[str, str]:
        grid: dict[str, str] = {}
        board_part = self._fen.split()[0]
        rows = board_part.split("/")
        for r_idx, row_str in enumerate(rows):
            rank = 10 - r_idx
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    c += int(ch)
                else:
                    sq = f"{FILES[c]}{rank}"
                    grid[sq] = ch
                    c += 1
        return grid

    def get_legal_uci_moves(self) -> list[str]:
        if HAS_PYFFISH:
            try:
                return pyffish.legal_moves("xiangqi", self._fen, [])
            except Exception:
                pass
        return []

    @property
    def legal_moves(self) -> list[Move]:
        legal_uci = self.get_legal_uci_moves()
        grid = self.grid_map()
        res: list[Move] = []
        for uci in legal_uci:
            try:
                f_sq, t_sq = parse_move_uci(uci)
                cap = grid.get(t_sq)
                res.append(Move(from_square=f_sq, to_square=t_sq, uci=uci, captured=cap))
            except ValueError:
                continue
        return res

    def push_uci(self, uci: str) -> None:
        prev_fen = self._fen
        if HAS_PYFFISH:
            try:
                self._is_check = bool(pyffish.gives_check("xiangqi", prev_fen, [uci]))
                self._fen = pyffish.get_fen("xiangqi", prev_fen, [uci])
            except Exception:
                pass

        self.history_uci.append(uci)
        self.fen_history.append(self._fen.split()[0])

    def push(self, move: Move) -> None:
        self.push_uci(move.uci)

    def pop(self) -> str | None:
        if not self.history_uci:
            return None
        last_uci = self.history_uci.pop()
        if HAS_PYFFISH:
            self._fen = pyffish.start_fen("xiangqi")
        else:
            self._fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        self.fen_history = [self._fen.split()[0]]
        self._is_check = False
        remaining = list(self.history_uci)
        self.history_uci = []
        for uci in remaining:
            self.push_uci(uci)
        return last_uci

    def is_check(self) -> bool:
        return self._is_check

    def is_checkmate(self) -> bool:
        return self.is_check() and len(self.legal_moves) == 0

    def is_stalemate(self) -> bool:
        # In Xiangqi, having no legal moves while not in check is stalemate (bức tử), which is a loss for the side to move
        return not self.is_check() and len(self.legal_moves) == 0

    def is_repetition(self) -> bool:
        current_pos = self._fen.split()[0]
        return self.fen_history.count(current_pos) >= 3

    def is_insufficient_material(self) -> bool:
        if HAS_PYFFISH:
            try:
                im = pyffish.has_insufficient_material("xiangqi", self._fen, [])
                return bool(im[0] and im[1])
            except Exception:
                pass
        return False

    def is_game_over(self) -> bool:
        if len(self.legal_moves) == 0:
            return True
        if self.is_repetition():
            return True
        if self.is_insufficient_material():
            return True
        return False

    def winner(self) -> Color | None:
        if len(self.legal_moves) == 0:
            # Player whose turn it is cannot move -> the other player wins!
            return opponent(self.turn)
        return None

    def result_reason(self) -> str | None:
        if self.is_repetition():
            return "repetition"
        if self.is_insufficient_material():
            return "insufficient_material"
        if self.is_checkmate():
            return "checkmate"
        if self.is_stalemate():
            return "stalemate"
        if self.is_game_over():
            return "no_moves"
        return None

    def san(self, uci: str) -> str:
        f_sq, t_sq = parse_move_uci(uci)
        piece = self.piece_at(f_sq)
        pname = PIECE_NAMES_VI.get(piece, "Quân") if piece else "Quân"

        is_cap = False
        if HAS_PYFFISH:
            try:
                is_cap = bool(pyffish.is_capture("xiangqi", self._fen, [], uci))
            except Exception:
                is_cap = self.piece_at(t_sq) is not None
        else:
            is_cap = self.piece_at(t_sq) is not None

        action = "x" if is_cap else "-"
        return f"{pname} {f_sq}{action}{t_sq}"
