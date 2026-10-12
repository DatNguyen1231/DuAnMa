from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


BOARD_SIZE = 20
WIN_LENGTH = 5
BASE_DIR = Path(__file__).resolve().parent

PlayerMark = Literal["X", "O"]
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
    board: list[list[str]] = field(
        default_factory=lambda: [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    )
    players: dict[PlayerMark, WebSocket | None] = field(default_factory=lambda: {"X": None, "O": None})
    turn: PlayerMark = "X"
    status: GameStatus = "waiting"
    winner: PlayerMark | None = None
    winning_cells: list[list[int]] = field(default_factory=list)


rooms: dict[str, Room] = {}
connections: dict[WebSocket, tuple[str, PlayerMark]] = {}


@app.get("/")
def home():
    return {"message": "Caro server is running", "rooms": len(rooms)}


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
                await send_error(websocket, "Lenh khong hop le.")

    except WebSocketDisconnect:
        await disconnect(websocket)


async def create_room(websocket: WebSocket):
    if websocket in connections:
        await send_error(websocket, "Ban dang o trong mot phong roi.")
        return

    code = create_room_code()
    room = Room(code=code)
    room.players["X"] = websocket
    rooms[code] = room
    connections[websocket] = (code, "X")

    await websocket.send_json({"type": "room_created", "room": code, "mark": "X"})
    await broadcast_state(room)


async def join_room(websocket: WebSocket, code: str):
    if websocket in connections:
        await send_error(websocket, "Ban dang o trong mot phong roi.")
        return

    room = rooms.get(code)
    if room is None:
        await send_error(websocket, "Khong tim thay phong.")
        return

    if room.players["X"] is not None and room.players["O"] is not None:
        await send_error(websocket, "Phong da du 2 nguoi.")
        return

    mark: PlayerMark = "O" if room.players["X"] is not None else "X"
    room.players[mark] = websocket
    room.status = "playing" if has_two_players(room) else "waiting"
    connections[websocket] = (room.code, mark)

    await websocket.send_json({"type": "joined", "room": room.code, "mark": mark})
    await broadcast_state(room)


async def make_move(websocket: WebSocket, message: dict):
    room, mark = get_connection_room(websocket)
    if room is None or mark is None:
        await send_error(websocket, "Ban chua vao phong.")
        return

    if room.status != "playing":
        await send_error(websocket, "Van co chua san sang hoac da ket thuc.")
        return

    if not has_two_players(room):
        await send_error(websocket, "Can du 2 nguoi choi moi duoc danh.")
        return

    if room.turn != mark:
        await send_error(websocket, "Chua den luot cua ban.")
        return

    try:
        row = int(message.get("row"))
        col = int(message.get("col"))
    except (TypeError, ValueError):
        await send_error(websocket, "Nuoc di khong hop le.")
        return

    if not is_inside_board(row, col):
        await send_error(websocket, "Nuoc di nam ngoai ban co.")
        return

    if room.board[row][col]:
        await send_error(websocket, "O nay da co quan.")
        return

    room.board[row][col] = mark
    winning_cells = find_winning_cells(room.board, row, col, mark)

    if winning_cells:
        room.status = "finished"
        room.winner = mark
        room.winning_cells = winning_cells
    elif is_board_full(room.board):
        room.status = "finished"
        room.winner = None
        room.winning_cells = []
    else:
        room.turn = "O" if mark == "X" else "X"

    await broadcast_state(room)


async def restart_room(websocket: WebSocket):
    room, _ = get_connection_room(websocket)
    if room is None:
        await send_error(websocket, "Ban chua vao phong.")
        return

    if room.status != "finished":
        await send_error(websocket, "Chi co the choi lai sau khi van co ket thuc.")
        return

    room.board = [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    room.turn = "X"
    room.winner = None
    room.winning_cells = []
    room.status = "playing" if room.players["X"] and room.players["O"] else "waiting"

    await broadcast_state(room)


async def disconnect(websocket: WebSocket):
    connection = connections.pop(websocket, None)
    if connection is None:
        return

    room_code, mark = connection
    room = rooms.get(room_code)
    if room is None:
        return

    room.players[mark] = None
    if room.status == "playing":
        room.status = "waiting"

    for player_socket in room.players.values():
        if player_socket is not None:
            await player_socket.send_json({"type": "opponent_left", "mark": mark})
            await send_state(player_socket, room)


def create_room_code() -> str:
    while True:
        code = str(random.randint(100000, 999999))
        if code not in rooms:
            return code


def get_connection_room(websocket: WebSocket) -> tuple[Room | None, PlayerMark | None]:
    connection = connections.get(websocket)
    if connection is None:
        return None, None

    room_code, mark = connection
    return rooms.get(room_code), mark


def has_two_players(room: Room) -> bool:
    return room.players["X"] is not None and room.players["O"] is not None


async def broadcast_state(room: Room):
    for websocket in room.players.values():
        if websocket is not None:
            await send_state(websocket, room)


async def send_state(websocket: WebSocket, room: Room):
    _, mark = connections.get(websocket, (None, None))
    await websocket.send_json(
        {
            "type": "state",
            "room": room.code,
            "mark": mark,
            "boardSize": BOARD_SIZE,
            "board": room.board,
            "turn": room.turn,
            "status": room.status,
            "winner": room.winner,
            "winningCells": room.winning_cells,
            "players": {
                "X": room.players["X"] is not None,
                "O": room.players["O"] is not None,
            },
        }
    )


async def send_error(websocket: WebSocket, message: str):
    await websocket.send_json({"type": "error", "message": message})


def is_inside_board(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def is_board_full(board: list[list[str]]) -> bool:
    return all(cell for row in board for cell in row)


def find_winning_cells(board: list[list[str]], row: int, col: int, mark: PlayerMark) -> list[list[int]]:
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

    for row_step, col_step in directions:
        cells = collect_direction(board, row, col, mark, -row_step, -col_step)
        cells.reverse()
        cells.append([row, col])
        cells.extend(collect_direction(board, row, col, mark, row_step, col_step))

        if len(cells) >= WIN_LENGTH:
            return cells

    return []


def collect_direction(
    board: list[list[str]],
    row: int,
    col: int,
    mark: PlayerMark,
    row_step: int,
    col_step: int,
) -> list[list[int]]:
    cells = []
    current_row = row + row_step
    current_col = col + col_step

    while is_inside_board(current_row, current_col) and board[current_row][current_col] == mark:
        cells.append([current_row, current_col])
        current_row += row_step
        current_col += col_step

    return cells
