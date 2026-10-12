from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


BOARD_SIZE = 8
BASE_DIR = Path(__file__).resolve().parent

PlayerColor = Literal["white", "black"]
ConnectionRole = Literal["white", "black", "viewer"]
GameStatus = Literal["waiting", "playing", "finished"]


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class Room:
    code: str
    board: chess.Board = field(default_factory=chess.Board)
    players: dict[PlayerColor, WebSocket | None] = field(
        default_factory=lambda: {"white": None, "black": None}
    )
    viewers: list[WebSocket] = field(default_factory=list)
    status: GameStatus = "waiting"
    move_history: list[dict[str, str]] = field(default_factory=list)


rooms: dict[str, Room] = {}
connections: dict[WebSocket, tuple[str, ConnectionRole]] = {}


@app.get("/")
def home():
    return {"message": "Máy chủ cờ vua đang chạy", "rooms": len(rooms)}


@app.get("/ui")
def ui():
    return FileResponse(BASE_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "create_room":
                await create_room(websocket)
            elif message_type == "join_room":
                await join_room(websocket, str(message.get("room", "")).strip())
            elif message_type == "move":
                await make_move(websocket, message)
            elif message_type == "restart":
                await restart_room(websocket)
            else:
                await send_error(websocket, "Lệnh không hợp lệ.")

    except WebSocketDisconnect:
        await disconnect(websocket)


async def create_room(websocket: WebSocket):
    if websocket in connections:
        await send_error(websocket, "Bạn đang ở trong một phòng rồi.")
        return

    code = create_room_code()
    room = Room(code=code)
    room.players["white"] = websocket
    rooms[code] = room
    connections[websocket] = (code, "white")

    await websocket.send_json({"type": "room_created", "room": code, "mark": "white"})
    await broadcast_state(room)


async def join_room(websocket: WebSocket, code: str):
    if websocket in connections:
        await send_error(websocket, "Bạn đang ở trong một phòng rồi.")
        return

    room = rooms.get(code)
    if room is None:
        await send_error(websocket, "Không tìm thấy phòng.")
        return

    if room.players["white"] is not None and room.players["black"] is not None:
        room.viewers.append(websocket)
        connections[websocket] = (room.code, "viewer")
        await websocket.send_json({"type": "joined", "room": room.code, "mark": "viewer"})
        await broadcast_state(room)
        return

    mark: PlayerColor = "black" if room.players["white"] is not None else "white"
    room.players[mark] = websocket
    room.status = "playing" if has_two_players(room) else "waiting"
    connections[websocket] = (room.code, mark)

    await websocket.send_json({"type": "joined", "room": room.code, "mark": mark})
    await broadcast_state(room)


async def make_move(websocket: WebSocket, message: dict):
    room, mark = get_connection_room(websocket)
    if room is None or mark is None:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    if mark == "viewer":
        await send_error(websocket, "Khán giả không được đi quân.")
        return

    if room.status != "playing":
        await send_error(websocket, "Ván cờ chưa sẵn sàng hoặc đã kết thúc.")
        return

    if not has_two_players(room):
        await send_error(websocket, "Cần đủ 2 người chơi mới được đánh.")
        return

    if current_turn(room.board) != mark:
        await send_error(websocket, "Chưa đến lượt của bạn.")
        return

    move = parse_move(message)
    if move is None:
        await send_error(websocket, "Nước đi không hợp lệ.")
        return

    if move not in room.board.legal_moves:
        await send_error(websocket, "Nước đi sai luật.")
        return

    move_color = current_turn(room.board)
    move_summary = serialize_move(room.board, move, move_color)
    room.board.push(move)
    room.move_history.append(move_summary)

    if room.board.is_game_over(claim_draw=True):
        room.status = "finished"

    await broadcast_state(room)


async def restart_room(websocket: WebSocket):
    room, mark = get_connection_room(websocket)
    if room is None:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    if mark == "viewer":
        await send_error(websocket, "Khán giả không được chơi lại ván.")
        return

    if room.status != "finished":
        await send_error(websocket, "Chỉ có thể chơi lại sau khi ván cờ kết thúc.")
        return

    room.board = chess.Board()
    room.move_history = []
    room.status = "playing" if has_two_players(room) else "waiting"

    await broadcast_state(room)


async def disconnect(websocket: WebSocket):
    connection = connections.pop(websocket, None)
    if connection is None:
        return

    room_code, mark = connection
    room = rooms.get(room_code)
    if room is None:
        return

    if mark == "viewer":
        if websocket in room.viewers:
            room.viewers.remove(websocket)
        await broadcast_state(room)
        return

    room.players[mark] = None
    if room.status == "playing":
        room.status = "waiting"

    for player_socket in room.players.values():
        if player_socket is not None:
            await player_socket.send_json({"type": "opponent_left", "mark": mark})
            await send_state(player_socket, room)

    for viewer_socket in room.viewers:
        await viewer_socket.send_json({"type": "opponent_left", "mark": mark})
        await send_state(viewer_socket, room)


def create_room_code() -> str:
    while True:
        code = str(random.randint(100000, 999999))
        if code not in rooms:
            return code


def get_connection_room(websocket: WebSocket) -> tuple[Room | None, ConnectionRole | None]:
    connection = connections.get(websocket)
    if connection is None:
        return None, None

    room_code, mark = connection
    return rooms.get(room_code), mark


def has_two_players(room: Room) -> bool:
    return room.players["white"] is not None and room.players["black"] is not None


async def broadcast_state(room: Room):
    for websocket in room.players.values():
        if websocket is not None:
            await send_state(websocket, room)

    for websocket in room.viewers:
        await send_state(websocket, room)


async def send_state(websocket: WebSocket, room: Room):
    _, mark = connections.get(websocket, (None, None))
    outcome = room.board.outcome(claim_draw=True)
    await websocket.send_json(
        {
            "type": "state",
            "room": room.code,
            "mark": mark,
            "boardSize": BOARD_SIZE,
            "board": serialize_board(room.board),
            "fen": room.board.fen(),
            "turn": current_turn(room.board),
            "status": room.status,
            "winner": winner_from_outcome(outcome),
            "isCheck": room.board.is_check(),
            "isCheckmate": room.board.is_checkmate(),
            "isStalemate": room.board.is_stalemate(),
            "isDraw": outcome is not None and outcome.winner is None,
            "resultReason": result_reason(outcome),
            "lastMove": room.move_history[-1] if room.move_history else None,
            "moveHistory": room.move_history,
            "fullmoveNumber": room.board.fullmove_number,
            "legalMoves": serialize_legal_moves(room.board, mark, room.status),
            "players": {
                "white": room.players["white"] is not None,
                "black": room.players["black"] is not None,
            },
            "viewerCount": len(room.viewers),
        }
    )


async def send_error(websocket: WebSocket, message: str):
    await websocket.send_json({"type": "error", "message": message})


def parse_move(message: dict) -> chess.Move | None:
    move_from = str(message.get("from", "")).strip().lower()
    move_to = str(message.get("to", "")).strip().lower()
    promotion = str(message.get("promotion", "") or "").strip().lower()

    if len(move_from) != 2 or len(move_to) != 2:
        return None

    uci = f"{move_from}{move_to}"
    if promotion:
        if promotion not in {"q", "r", "b", "n"}:
            return None
        uci += promotion

    try:
        return chess.Move.from_uci(uci)
    except ValueError:
        return None


def serialize_board(board: chess.Board) -> list[list[dict[str, str] | None]]:
    rows: list[list[dict[str, str] | None]] = []

    for rank in range(7, -1, -1):
        row: list[dict[str, str] | None] = []
        for file_index in range(8):
            square = chess.square(file_index, rank)
            piece = board.piece_at(square)
            row.append(serialize_piece(square, piece))
        rows.append(row)

    return rows


def serialize_piece(square: chess.Square, piece: chess.Piece | None) -> dict[str, str] | None:
    if piece is None:
        return None

    return {
        "square": chess.square_name(square),
        "symbol": piece.symbol(),
        "color": "white" if piece.color == chess.WHITE else "black",
        "type": chess.piece_name(piece.piece_type),
    }


def serialize_move(board: chess.Board, move: chess.Move, color: PlayerColor) -> dict[str, str]:
    return {
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
        "uci": move.uci(),
        "san": board.san(move),
        "color": color,
        "moveNumber": str(board.fullmove_number),
    }


def serialize_legal_moves(
    board: chess.Board,
    mark: ConnectionRole | None,
    status: GameStatus,
) -> list[dict[str, str | None]]:
    if status != "playing" or mark not in {"white", "black"} or mark != current_turn(board):
        return []

    return [
        {
            "from": chess.square_name(move.from_square),
            "to": chess.square_name(move.to_square),
            "promotion": chess.piece_symbol(move.promotion) if move.promotion else None,
            "uci": move.uci(),
        }
        for move in board.legal_moves
    ]


def current_turn(board: chess.Board) -> PlayerColor:
    return "white" if board.turn == chess.WHITE else "black"


def winner_from_outcome(outcome: chess.Outcome | None) -> PlayerColor | None:
    if outcome is None or outcome.winner is None:
        return None

    return "white" if outcome.winner == chess.WHITE else "black"


def result_reason(outcome: chess.Outcome | None) -> str | None:
    if outcome is None:
        return None

    return outcome.termination.name.lower()
