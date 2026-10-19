from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import xiangqi

BASE_DIR = Path(__file__).resolve().parent

PlayerColor = Literal["red", "black"]
ConnectionRole = Literal["red", "black", "both", "viewer"]
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
    board: xiangqi.Board = field(default_factory=xiangqi.Board)
    players: dict[PlayerColor, WebSocket | None] = field(
        default_factory=lambda: {"red": None, "black": None}
    )
    viewers: list[WebSocket] = field(default_factory=list)
    status: GameStatus = "waiting"
    move_history: list[dict[str, str]] = field(default_factory=list)
    is_solo: bool = False
    winner: str | None = None
    result_reason: str | None = None


rooms: dict[str, Room] = {}
connections: dict[WebSocket, tuple[str, ConnectionRole]] = {}
lobby_websockets: set[WebSocket] = set()


def serialize_room_list() -> list[dict]:
    res = []
    for code, room in rooms.items():
        if room.is_solo:
            continue
        has_red = room.players["red"] is not None
        has_black = room.players["black"] is not None
        player_count = int(has_red) + int(has_black)
        viewer_count = len(room.viewers)
        move_count = len(room.move_history)
        res.append({
            "code": code,
            "status": room.status,
            "has_red": has_red,
            "has_black": has_black,
            "playerCount": player_count,
            "viewerCount": viewer_count,
            "viewers": viewer_count,
            "moveCount": move_count,
            "moves": move_count,
            "canJoin": room.status == "waiting" and player_count < 2,
            "canSpectate": True,
        })
    res.sort(key=lambda r: (r["status"] != "waiting", -r["playerCount"], -r["viewerCount"]))
    return res


async def broadcast_room_list():
    room_list_data = serialize_room_list()
    msg = {"type": "room_list", "rooms": room_list_data}
    dead = set()
    for ws in list(lobby_websockets):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    lobby_websockets.difference_update(dead)


@app.get("/")
def home():
    return {"message": "Máy chủ cờ tướng đang chạy", "rooms": len(rooms)}


@app.get("/rooms")
def get_rooms():
    return {"rooms": serialize_room_list()}


@app.get("/ui")
def ui():
    return FileResponse(
        BASE_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/wukong.js")
def wukong_js():
    return FileResponse(BASE_DIR / "wukong.js", media_type="application/javascript")



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    lobby_websockets.add(websocket)
    try:
        await websocket.send_json({"type": "room_list", "rooms": serialize_room_list()})
    except Exception:
        pass

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "create_room":
                await create_room(websocket)
            elif message_type == "create_solo_room":
                await create_solo_room(websocket)
            elif message_type == "quick_match":
                await quick_match(websocket)
            elif message_type == "join_room":
                await join_room(websocket, str(message.get("room", "")).strip())
            elif message_type == "leave_room":
                await leave_room(websocket)
            elif message_type == "get_rooms":
                await websocket.send_json({"type": "room_list", "rooms": serialize_room_list()})
            elif message_type == "move":
                await make_move(websocket, message)
            elif message_type == "undo":
                await undo_move(websocket, int(message.get("steps", 1)))
            elif message_type == "restart":
                await restart_room(websocket)
            elif message_type == "resign":
                await resign_game(websocket)
            elif message_type == "draw_offer":
                await handle_draw_offer(websocket)
            elif message_type == "draw_response":
                await handle_draw_response(websocket, bool(message.get("accept", False)))
            elif message_type == "chat":
                await handle_chat(websocket, message)
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
    room.players["red"] = websocket
    rooms[code] = room
    connections[websocket] = (code, "red")

    await websocket.send_json({"type": "room_created", "room": code, "mark": "red"})
    await broadcast_state(room)
    await broadcast_room_list()


async def create_solo_room(websocket: WebSocket):
    if websocket in connections:
        await send_error(websocket, "Bạn đang ở trong một phòng rồi.")
        return

    code = create_room_code()
    room = Room(code=code, is_solo=True)
    room.players["red"] = websocket
    room.players["black"] = websocket
    room.status = "playing"
    rooms[code] = room
    connections[websocket] = (code, "both")

    await websocket.send_json({"type": "room_created", "room": code, "mark": "both"})
    await broadcast_state(room)
    await broadcast_room_list()


async def quick_match(websocket: WebSocket):
    if websocket in connections:
        await leave_room(websocket)

    available_room = None
    for room in rooms.values():
        if (
            not room.is_solo
            and room.status == "waiting"
            and (room.players["red"] is None or room.players["black"] is None)
        ):
            available_room = room
            break

    if available_room is not None:
        mark: PlayerColor = "black" if available_room.players["red"] is not None else "red"
        available_room.players[mark] = websocket
        available_room.status = "playing"
        connections[websocket] = (available_room.code, mark)
        await websocket.send_json({"type": "joined", "room": available_room.code, "mark": mark, "matched": True})
        await broadcast_state(available_room)
        await broadcast_room_list()
    else:
        code = create_room_code()
        room = Room(code=code)
        room.players["red"] = websocket
        room.status = "waiting"
        rooms[code] = room
        connections[websocket] = (code, "red")
        await websocket.send_json({"type": "room_created", "room": code, "mark": "red", "waiting_match": True})
        await broadcast_state(room)
        await broadcast_room_list()


async def join_room(websocket: WebSocket, code: str):
    if websocket in connections:
        await send_error(websocket, "Bạn đang ở trong một phòng rồi.")
        return

    room = rooms.get(code)
    if room is None:
        await send_error(websocket, "Không tìm thấy phòng.")
        return

    if room.players["red"] is not None and room.players["black"] is not None:
        room.viewers.append(websocket)
        connections[websocket] = (room.code, "viewer")
        await websocket.send_json({"type": "joined", "room": room.code, "mark": "viewer"})
        await broadcast_state(room)
        await broadcast_room_list()
        return

    mark: PlayerColor = "black" if room.players["red"] is not None else "red"
    room.players[mark] = websocket
    room.status = "playing" if has_two_players(room) else "waiting"
    connections[websocket] = (room.code, mark)

    await websocket.send_json({"type": "joined", "room": room.code, "mark": mark})
    await broadcast_state(room)
    await broadcast_room_list()


async def leave_room(websocket: WebSocket):
    lobby_websockets.add(websocket)
    connection = connections.pop(websocket, None)
    if connection is None:
        await websocket.send_json({"type": "left_room"})
        await broadcast_room_list()
        return

    room_code, mark = connection
    room = rooms.get(room_code)
    if room is not None:
        if mark == "both":
            rooms.pop(room_code, None)
        elif mark == "viewer":
            if websocket in room.viewers:
                room.viewers.remove(websocket)
            await broadcast_state(room)
        else:
            room.players[mark] = None
            if room.status == "playing":
                room.status = "waiting"

            if room.players["red"] is None and room.players["black"] is None:
                rooms.pop(room_code, None)
            else:
                for player_socket in room.players.values():
                    if player_socket is not None and player_socket != websocket:
                        try:
                            await player_socket.send_json({"type": "opponent_left", "mark": mark})
                            await send_state(player_socket, room)
                        except Exception:
                            pass
                for viewer_socket in room.viewers:
                    try:
                        await viewer_socket.send_json({"type": "opponent_left", "mark": mark})
                        await send_state(viewer_socket, room)
                    except Exception:
                        pass
                await broadcast_state(room)

    await websocket.send_json({"type": "left_room"})
    await broadcast_room_list()


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

    if mark != "both" and room.board.turn != mark:
        await send_error(websocket, "Chưa đến lượt của bạn.")
        return

    move_uci = parse_move(message)
    if not move_uci:
        await send_error(websocket, "Nước đi không hợp lệ.")
        return

    legal_moves = room.board.get_legal_uci_moves()
    if move_uci not in legal_moves:
        await send_error(websocket, "Nước đi sai luật cờ tướng.")
        return

    try:
        f_sq, t_sq = xiangqi.parse_move_uci(move_uci)
    except ValueError:
        await send_error(websocket, "Lỗi định dạng nước đi.")
        return

    move_color = room.board.turn
    san_notation = room.board.san(move_uci)

    room.board.push_uci(move_uci)

    move_summary = {
        "from": f_sq,
        "to": t_sq,
        "uci": move_uci,
        "san": san_notation,
        "color": move_color,
        "moveNumber": str(room.board.fullmove_number),
    }
    room.move_history.append(move_summary)

    if room.board.is_game_over():
        room.status = "finished"
        await broadcast_room_list()

    await broadcast_state(room)


async def restart_room(websocket: WebSocket):
    room, mark = get_connection_room(websocket)
    if room is None:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    if mark == "viewer":
        await send_error(websocket, "Khán giả không được chơi lại ván.")
        return

    if not room.is_solo and room.status != "finished":
        await send_error(websocket, "Chỉ có thể chơi lại sau khi ván cờ kết thúc.")
        return

    room.board = xiangqi.Board()
    room.move_history = []
    room.winner = None
    room.result_reason = None
    room.status = "playing" if has_two_players(room) else "waiting"

    await broadcast_state(room)
    await broadcast_room_list()


async def undo_move(websocket: WebSocket, steps: int = 1):
    room, mark = get_connection_room(websocket)
    if room is None:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    if mark == "viewer":
        await send_error(websocket, "Khán giả không thể đi lại nước cờ.")
        return

    if not room.is_solo:
        await send_error(websocket, "Chỉ có thể đi lại cờ trong chế độ luyện tập / đấu với máy.")
        return

    if not room.move_history:
        await send_error(websocket, "Không có nước cờ nào để đi lại.")
        return

    steps = max(1, min(steps, len(room.move_history)))
    for _ in range(steps):
        if room.move_history:
            room.move_history.pop()
            room.board.pop()

    room.status = "playing"
    room.winner = None
    room.result_reason = None
    await broadcast_state(room)
    await broadcast_room_list()


async def resign_game(websocket: WebSocket):
    room, mark = get_connection_room(websocket)
    if room is None or mark is None:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return
    if room.status != "playing":
        await send_error(websocket, "Trận đấu chưa bắt đầu hoặc đã kết thúc.")
        return
    if mark not in {"red", "black"}:
        await send_error(websocket, "Chỉ người chơi mới được đầu hàng.")
        return

    room.status = "finished"
    room.winner = "black" if mark == "red" else "red"
    room.result_reason = f"resign_{mark}"
    await broadcast_state(room)
    await broadcast_room_list()


async def handle_draw_offer(websocket: WebSocket):
    room, mark = get_connection_room(websocket)
    if room is None or mark not in {"red", "black"} or room.status != "playing":
        return
    opponent_mark = "black" if mark == "red" else "red"
    opponent_socket = room.players[opponent_mark]
    if opponent_socket is not None:
        try:
            await opponent_socket.send_json({"type": "draw_offered", "by": mark, "from": mark})
        except Exception:
            pass


async def handle_draw_response(websocket: WebSocket, accept: bool):
    room, mark = get_connection_room(websocket)
    if room is None or mark not in {"red", "black"} or room.status != "playing":
        return
    if accept:
        room.status = "finished"
        room.winner = None
        room.result_reason = "draw_agreed"
        await broadcast_state(room)
        await broadcast_room_list()
    else:
        opponent_mark = "black" if mark == "red" else "red"
        opponent_socket = room.players[opponent_mark]
        if opponent_socket is not None:
            try:
                await opponent_socket.send_json({"type": "draw_declined"})
            except Exception:
                pass


async def handle_chat(websocket: WebSocket, message: dict):
    room, mark = get_connection_room(websocket)
    if room is None:
        return
    text = str(message.get("text", "")).strip()[:150]
    emoji = str(message.get("emoji", "")).strip()[:10]
    if not text and not emoji:
        return
    payload = {
        "type": "chat_message",
        "from": mark,
        "sender": mark,
        "text": text,
        "emoji": emoji,
    }
    targets = set(ws for ws in room.players.values() if ws is not None)
    targets.update(room.viewers)
    for ws in targets:
        try:
            await ws.send_json(payload)
        except Exception:
            pass


async def disconnect(websocket: WebSocket):
    lobby_websockets.discard(websocket)
    connection = connections.pop(websocket, None)
    if connection is None:
        await broadcast_room_list()
        return

    room_code, mark = connection
    room = rooms.get(room_code)
    if room is None:
        await broadcast_room_list()
        return

    if mark == "both":
        rooms.pop(room_code, None)
        await broadcast_room_list()
        return

    if mark == "viewer":
        if websocket in room.viewers:
            room.viewers.remove(websocket)
        await broadcast_state(room)
        await broadcast_room_list()
        return

    room.players[mark] = None
    if room.status == "playing":
        room.status = "waiting"

    # If both players left, clean up the room
    if room.players["red"] is None and room.players["black"] is None:
        rooms.pop(room_code, None)
        await broadcast_room_list()
        return

    for player_socket in room.players.values():
        if player_socket is not None and player_socket != websocket:
            try:
                await player_socket.send_json({"type": "opponent_left", "mark": mark})
                await send_state(player_socket, room)
            except Exception:
                pass

    for viewer_socket in room.viewers:
        if viewer_socket != websocket:
            try:
                await viewer_socket.send_json({"type": "opponent_left", "mark": mark})
                await send_state(viewer_socket, room)
            except Exception:
                pass

    await broadcast_room_list()


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
    return room.players["red"] is not None and room.players["black"] is not None


async def broadcast_state(room: Room):
    targets = set(ws for ws in room.players.values() if ws is not None)
    targets.update(room.viewers)
    for websocket in targets:
        await send_state(websocket, room)


async def send_state(websocket: WebSocket, room: Room):
    _, mark = connections.get(websocket, (None, None))

    is_checkmate = room.board.is_checkmate()
    is_stalemate = room.board.is_stalemate()
    is_check = room.board.is_check()
    is_rep = room.board.is_repetition()
    is_insufficient = room.board.is_insufficient_material()
    winner = room.winner
    if winner is None:
        if is_checkmate or is_stalemate or room.status == "finished":
            winner = room.board.winner()

    result_reason = room.result_reason or room.board.result_reason()

    await websocket.send_json(
        {
            "type": "state",
            "room": room.code,
            "mark": mark,
            "isSolo": room.is_solo,
            "boardCols": xiangqi.BOARD_COLS,
            "boardRows": xiangqi.BOARD_ROWS,
            "board": serialize_board(room.board),
            "fen": room.board.fen(),
            "turn": room.board.turn,
            "status": room.status,
            "winner": winner,
            "isCheck": is_check,
            "isCheckmate": is_checkmate,
            "isStalemate": is_stalemate,
            "isDraw": is_rep or is_insufficient or (room.status == "finished" and winner is None),
            "resultReason": result_reason,
            "lastMove": room.move_history[-1] if room.move_history else None,
            "moveHistory": room.move_history,
            "fullmoveNumber": room.board.fullmove_number,
            "legalMoves": serialize_legal_moves(room.board, mark, room.status),
            "players": {
                "red": room.players["red"] is not None,
                "black": room.players["black"] is not None,
            },
            "viewerCount": len(room.viewers),
        }
    )


async def send_error(websocket: WebSocket, message: str):
    await websocket.send_json({"type": "error", "message": message})


def parse_move(message: dict) -> str | None:
    move_from = str(message.get("from", "")).strip().lower()
    move_to = str(message.get("to", "")).strip().lower()

    if not move_from or not move_to:
        return None

    return f"{move_from}{move_to}"


def serialize_board(board: xiangqi.Board) -> list[list[dict[str, str] | None]]:
    rows: list[list[dict[str, str] | None]] = []
    grid = board.grid_map()
    # Ranks 10 down to 1
    for rank in range(10, 0, -1):
        row: list[dict[str, str] | None] = []
        for col_idx in range(9):
            sq = f"{xiangqi.FILES[col_idx]}{rank}"
            piece = grid.get(sq)
            row.append(serialize_piece(sq, piece))
        rows.append(row)
    return rows


def serialize_piece(square: str, piece: str | None) -> dict[str, str] | None:
    if piece is None:
        return None

    color = "red" if piece.isupper() else "black"
    return {
        "square": square,
        "symbol": piece,
        "han": xiangqi.PIECE_CHARS_HAN.get(piece, piece),
        "name": xiangqi.PIECE_NAMES_VI.get(piece, piece),
        "color": color,
        "type": piece.upper(),
    }


def serialize_legal_moves(
    board: xiangqi.Board,
    mark: ConnectionRole | None,
    status: GameStatus,
) -> list[dict[str, str]]:
    if status != "playing" or mark not in {"red", "black", "both"}:
        return []
    if mark != "both" and mark != board.turn:
        return []

    res: list[dict[str, str]] = []
    for uci in board.get_legal_uci_moves():
        try:
            f_sq, t_sq = xiangqi.parse_move_uci(uci)
            res.append({"from": f_sq, "to": t_sq, "uci": uci})
        except ValueError:
            continue
    return res
