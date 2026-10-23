from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import poker

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Poker Texas Hold'em Online - Real Multiplayer & Chip Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class ClientSession:
    room_code: str
    player_id: str | None = None
    is_host: bool = False
    name: str = "Khách"


@dataclass
class Room:
    code: str
    table: poker.PokerTable = field(default_factory=poker.PokerTable)
    host_ws: WebSocket | None = None
    clients: dict[WebSocket, ClientSession] = field(default_factory=dict)
    room_name: str = "Bàn Poker"
    bot_task: asyncio.Task | None = None
    timer_task: asyncio.Task | None = None


rooms: dict[str, Room] = {}
connections: dict[WebSocket, ClientSession] = {}
lobby_websockets: set[WebSocket] = set()


def create_room_code() -> str:
    while True:
        code = str(random.randint(100000, 999999))
        if code not in rooms:
            return code


def serialize_room_list() -> list[dict]:
    res = []
    for code, room in rooms.items():
        player_count = len(room.table.players)
        online_count = len(room.clients)
        res.append({
            "code": code,
            "name": room.room_name,
            "street": room.table.street,
            "streetLabel": poker.STREET_LABELS_VI.get(room.table.street, room.table.street),
            "handNumber": room.table.hand_number,
            "pot": room.table.pot,
            "smallBlind": room.table.small_blind,
            "bigBlind": room.table.big_blind,
            "currency": room.table.currency,
            "playerCount": player_count,
            "onlineCount": online_count,
            "canJoin": player_count < poker.MAX_SEATS,
        })
    res.sort(key=lambda r: (-r["onlineCount"], -r["playerCount"], r["code"]))
    return res


async def broadcast_room_list() -> None:
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
    return FileResponse(
        BASE_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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


@app.get("/style.css")
def style_css():
    return FileResponse(
        BASE_DIR / "style.css",
        media_type="text/css",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/app.js")
def app_js():
    return FileResponse(
        BASE_DIR / "app.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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
            msg_type = message.get("type")

            if msg_type == "create_room":
                await handle_create_room(websocket, message, mode="online")
            elif msg_type == "create_bot_room":
                await handle_create_room(websocket, message, mode="bot")
            elif msg_type == "quick_match":
                await handle_quick_match(websocket, message)
            elif msg_type == "join_room":
                await handle_join_room(websocket, message)
            elif msg_type == "leave_room":
                await handle_leave_room(websocket)
            elif msg_type == "get_rooms":
                await websocket.send_json({"type": "room_list", "rooms": serialize_room_list()})
            elif msg_type == "sit_down":
                await handle_sit_down(websocket, message)
            elif msg_type == "add_bot":
                await handle_add_bot(websocket, message)
            elif msg_type == "remove_player":
                await handle_remove_player(websocket, message)
            elif msg_type == "rename_player":
                await handle_rename_player(websocket, message)
            elif msg_type == "toggle_sit_out":
                await handle_toggle_sit_out(websocket, message)
            elif msg_type == "reveal_cards":
                await handle_reveal_cards(websocket, message)
            elif msg_type == "rabbit_hunt":
                await handle_rabbit_hunt(websocket)
            elif msg_type == "set_dealer":
                await handle_set_dealer(websocket, message)
            elif msg_type == "update_settings":
                await handle_update_settings(websocket, message)
            elif msg_type == "start_hand":
                await handle_start_hand(websocket, message)
            elif msg_type == "ready_next":
                await handle_ready_next(websocket, message)
            elif msg_type == "player_action":
                await handle_player_action(websocket, message)
            elif msg_type == "cancel_hand":
                await handle_cancel_hand(websocket)
            elif msg_type == "rebuy":
                await handle_rebuy(websocket, message)
            elif msg_type == "adjust_stack":
                await handle_adjust_stack(websocket, message)
            elif msg_type == "transfer_chips":
                await handle_transfer_chips(websocket, message)
            elif msg_type == "chat":
                await handle_chat(websocket, message)
            elif msg_type == "throw_item":
                await handle_throw_item(websocket, message)
            else:
                await send_error(websocket, f"Lệnh không hợp lệ: {msg_type}")

    except WebSocketDisconnect:
        await handle_disconnect(websocket)


def get_room_and_session(websocket: WebSocket) -> tuple[Room | None, ClientSession | None]:
    session = connections.get(websocket)
    if session is None:
        return None, None
    return rooms.get(session.room_code), session


def cancel_room_tasks(room: Room) -> None:
    if room.bot_task and not room.bot_task.done() and room.bot_task is not asyncio.current_task():
        room.bot_task.cancel()
    if room.timer_task and not room.timer_task.done() and room.timer_task is not asyncio.current_task():
        room.timer_task.cancel()


def schedule_human_turn_timer(room: Room) -> None:
    """Start a countdown timer for the active human player's turn; auto-fold on timeout."""
    if room.timer_task and not room.timer_task.done() and room.timer_task is not asyncio.current_task():
        room.timer_task.cancel()

    if (
        room.code not in rooms
        or room.table.all_in_runout
        or room.table.street in ("idle", "showdown")
        or room.table.turn_seat < 0
    ):
        return

    turn_p = room.table.get_player_by_seat(room.table.turn_seat)
    if not turn_p or turn_p.is_bot or turn_p.status != "active":
        return

    expected_seq = room.table.turn_seq
    wait_seconds = max(0.1, room.table.turn_deadline - time.time())

    async def _timer_worker() -> None:
        try:
            await asyncio.sleep(wait_seconds)
            if room.code not in rooms or room.table.turn_seq != expected_seq:
                return
            ok, msg = room.table.force_timeout_fold(expected_seq)
            if ok:
                await broadcast_state(room, sound="fold", toast=msg)
                await broadcast_room_list()
                await schedule_room_automation(room)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    room.timer_task = asyncio.create_task(_timer_worker())


async def schedule_room_automation(room: Room) -> None:
    """
    Coordinate:
    1) Step-by-step smooth All-in Runout (Flop -> Turn -> River -> Showdown with 1.5s delay per street)
    2) Bot AI turns (with natural 0.85s thinking delay)
    3) Human turn countdown timer (auto-fold when timer expires)
    """
    if room.timer_task and not room.timer_task.done() and room.timer_task is not asyncio.current_task():
        room.timer_task.cancel()

    needs_bot_or_runout = False
    if room.table.all_in_runout:
        needs_bot_or_runout = True
    elif room.table.street not in ("idle", "showdown") and room.table.turn_seat >= 0:
        tp = room.table.get_player_by_seat(room.table.turn_seat)
        if tp and tp.is_bot and tp.status == "active":
            needs_bot_or_runout = True

    if not needs_bot_or_runout:
        schedule_human_turn_timer(room)
        return

    if room.bot_task and not room.bot_task.done() and room.bot_task is not asyncio.current_task():
        return

    async def _automation_runner() -> None:
        try:
            while room.code in rooms:
                # 1. Smooth All-in Runout (street by street)
                if room.table.all_in_runout:
                    delay = 1.35 if room.table.street == "river" else 1.55
                    await asyncio.sleep(delay)
                    if room.code not in rooms or not room.table.all_in_runout:
                        break
                    ok, sound_effect = room.table.advance_all_in_runout_step()
                    if not ok:
                        break
                    await broadcast_state(room, sound=sound_effect)
                    await broadcast_room_list()
                    continue

                # 2. Bot AI Turn
                if room.table.street in ("idle", "showdown") or room.table.turn_seat < 0:
                    break
                turn_p = room.table.get_player_by_seat(room.table.turn_seat)
                if not turn_p or not turn_p.is_bot or turn_p.status != "active":
                    break

                await asyncio.sleep(0.85)
                turn_p = room.table.get_player_by_seat(room.table.turn_seat)
                if (
                    room.code not in rooms
                    or room.table.all_in_runout
                    or room.table.street in ("idle", "showdown")
                    or not turn_p
                    or not turn_p.is_bot
                    or turn_p.status != "active"
                ):
                    if room.code in rooms and room.table.all_in_runout:
                        continue
                    break

                act, amt = room.table.compute_bot_action(turn_p.id)
                prev_street = room.table.street
                ok, _ = room.table.player_action(turn_p.id, act, amt)
                if not ok:
                    fallback = "fold" if room.table.current_bet > turn_p.current_bet else "check"
                    room.table.player_action(turn_p.id, fallback, 0)

                sound = "chip"
                if act == "fold":
                    sound = "fold"
                elif act == "check":
                    sound = "check"
                elif act == "all_in":
                    sound = "allin"
                if room.table.street in ("idle", "showdown") and prev_street not in ("idle", "showdown"):
                    sound = "win"

                await broadcast_state(room, sound=sound)
                await broadcast_room_list()

            # Once Bot turns / Runout finish, if it's now a human player's turn, start their countdown timer
            if room.code in rooms:
                schedule_human_turn_timer(room)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    room.bot_task = asyncio.create_task(_automation_runner())


async def handle_create_room(websocket: WebSocket, message: dict, mode: str = "online") -> None:
    if websocket in connections:
        await handle_leave_room(websocket, silent=True)

    code = create_room_code()
    sb = int(message.get("smallBlind", 1000) or 1000)
    bb = int(message.get("bigBlind", 2000) or 2000)
    ante = int(message.get("ante", 0) or 0)
    buy_in = int(message.get("buyIn", 100000) or 100000)
    turn_timeout = int(message.get("turnTimeout", 20) or 20)
    currency = str(message.get("currency", "VNĐ") or "VNĐ").strip()
    player_name = str(message.get("name", "")).strip() or "Người chơi 1"
    avatar = message.get("avatar")

    room_name = str(message.get("roomName", "")).strip() or (
        f"Bàn Bot AI của {player_name}" if mode == "bot" else f"Bàn của {player_name}"
    )

    table = poker.PokerTable(
        small_blind=sb,
        big_blind=bb,
        ante=ante,
        default_buy_in=buy_in,
        currency=currency,
        turn_timeout=turn_timeout,
    )

    room = Room(code=code, table=table, host_ws=websocket, room_name=room_name)

    p_human, _ = table.add_player(name=player_name, buy_in=buy_in, seat=0, avatar=avatar, is_bot=False)
    if mode == "bot":
        for b_idx in range(1, 4):
            table.add_player(
                name=poker.BOT_NAMES[(b_idx - 1) % len(poker.BOT_NAMES)],
                buy_in=buy_in,
                seat=b_idx,
                is_bot=True,
            )

    session = ClientSession(
        room_code=code,
        player_id=p_human.id if p_human else None,
        is_host=True,
        name=p_human.name if p_human else player_name,
    )

    room.clients[websocket] = session
    rooms[code] = room
    connections[websocket] = session

    await websocket.send_json({
        "type": "room_created",
        "room": code,
        "playerId": session.player_id,
        "isHost": True,
        "mode": mode,
    })
    await broadcast_state(room)
    await broadcast_room_list()


async def handle_quick_match(websocket: WebSocket, message: dict) -> None:
    if websocket in connections:
        await handle_leave_room(websocket, silent=True)

    target_room = None
    for room in rooms.values():
        if len(room.table.players) < poker.MAX_SEATS:
            target_room = room
            break

    if target_room is not None:
        message["room"] = target_room.code
        await handle_join_room(websocket, message)
    else:
        await handle_create_room(websocket, message, mode="online")


async def handle_join_room(websocket: WebSocket, message: dict) -> None:
    if websocket in connections:
        await handle_leave_room(websocket, silent=True)

    code = str(message.get("room", "")).strip()
    room = rooms.get(code)
    if room is None:
        await send_error(websocket, f"Không tìm thấy phòng #{code}.")
        return

    player_name = str(message.get("name", "")).strip() or f"Người chơi #{len(room.table.players) + 1}"
    avatar = message.get("avatar")
    as_viewer = bool(message.get("asViewer", False))
    buy_in = int(message.get("buyIn", 0) or room.table.default_buy_in)

    bound_pid: str | None = None
    if not as_viewer and len(room.table.players) < poker.MAX_SEATS:
        p, _ = room.table.add_player(name=player_name, buy_in=buy_in, avatar=avatar, is_bot=False)
        if p:
            bound_pid = p.id
            player_name = p.name

    is_host = room.host_ws is None
    if is_host:
        room.host_ws = websocket

    session = ClientSession(
        room_code=code,
        player_id=bound_pid,
        is_host=is_host,
        name=player_name,
    )
    room.clients[websocket] = session
    connections[websocket] = session

    await websocket.send_json({
        "type": "joined",
        "room": code,
        "playerId": bound_pid,
        "isHost": is_host,
    })
    await broadcast_state(room, toast=f"{player_name} đã vào bàn!")
    await broadcast_room_list()


async def handle_sit_down(websocket: WebSocket, message: dict) -> None:
    """Allow a spectator without a seat to sit down at an empty seat."""
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    if session.player_id and session.player_id in room.table.players:
        await send_error(websocket, "Bạn đã có ghế trên bàn rồi.")
        return

    name = str(message.get("name", "") or session.name).strip() or "Người chơi"
    buy_in = int(message.get("buyIn", 0) or room.table.default_buy_in)
    seat = message.get("seat")
    seat_int = int(seat) if seat is not None and str(seat).isdigit() else None
    avatar = message.get("avatar")

    p, msg = room.table.add_player(
        name=name,
        buy_in=buy_in,
        seat=seat_int,
        avatar=avatar,
        is_bot=False,
    )
    if not p:
        await send_error(websocket, msg)
        return

    session.player_id = p.id
    session.name = p.name
    await broadcast_state(room, toast=msg)
    await broadcast_room_list()


async def handle_leave_room(websocket: WebSocket, silent: bool = False) -> None:
    lobby_websockets.add(websocket)
    session = connections.pop(websocket, None)
    if session is None:
        if not silent:
            await websocket.send_json({"type": "left_room"})
        await broadcast_room_list()
        return

    room = rooms.get(session.room_code)
    if room is not None:
        room.clients.pop(websocket, None)
        if session.player_id and session.player_id in room.table.players:
            p = room.table.players[session.player_id]
            p.connected = False

        if room.host_ws == websocket:
            room.host_ws = next(iter(room.clients.keys()), None)
            if room.host_ws and room.host_ws in room.clients:
                room.clients[room.host_ws].is_host = True

        if not room.clients:
            cancel_room_tasks(room)
            rooms.pop(session.room_code, None)
        else:
            await broadcast_state(room)

    if not silent:
        await websocket.send_json({"type": "left_room"})
    await broadcast_room_list()


async def handle_disconnect(websocket: WebSocket) -> None:
    lobby_websockets.discard(websocket)
    await handle_leave_room(websocket, silent=True)


async def handle_add_bot(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return
    if not session.is_host:
        await send_error(websocket, "Chỉ Chủ bàn (Host) mới được thêm Bot AI.")
        return

    name = str(message.get("name", "")).strip()
    buy_in = int(message.get("buyIn", 0) or room.table.default_buy_in)
    seat = message.get("seat")
    seat_int = int(seat) if seat is not None and str(seat).isdigit() else None

    p, msg = room.table.add_player(
        name=name,
        buy_in=buy_in,
        seat=seat_int,
        is_bot=True,
    )
    if not p:
        await send_error(websocket, msg)
        return

    await broadcast_state(room, toast=msg)
    await broadcast_room_list()


async def handle_remove_player(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    pid = str(message.get("playerId", "")).strip()
    if not session.is_host and session.player_id != pid:
        await send_error(websocket, "Chỉ Chủ bàn hoặc chính bạn mới có thể rời ghế này.")
        return

    ok, msg = room.table.remove_player(pid)
    if not ok:
        await send_error(websocket, msg)
        return

    for client_sess in room.clients.values():
        if client_sess.player_id == pid:
            client_sess.player_id = None

    await broadcast_state(room, toast=msg)
    await broadcast_room_list()
    await schedule_room_automation(room)


async def handle_rename_player(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    pid = str(message.get("playerId", "") or session.player_id or "").strip()
    if session.player_id != pid and not session.is_host:
        await send_error(websocket, "Bạn chỉ có thể đổi tên của chính mình.")
        return
    new_name = str(message.get("name", "")).strip()
    avatar = message.get("avatar")
    ok, msg = room.table.rename_player(pid, new_name, avatar)
    if not ok:
        await send_error(websocket, msg)
        return
    if session.player_id == pid:
        session.name = new_name
    await broadcast_state(room, toast=msg)


async def handle_toggle_sit_out(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    pid = str(message.get("playerId", "") or session.player_id or "").strip()
    if session.player_id != pid and not session.is_host:
        await send_error(websocket, "Bạn chỉ có thể đổi trạng thái ngồi nghỉ của chính mình.")
        return
    ok, msg = room.table.toggle_sit_out(pid)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, toast=msg)


async def handle_reveal_cards(websocket: WebSocket, message: dict) -> None:
    """Strictly allow a player to reveal ONLY their own hole cards (1 card or both)."""
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    if not session.player_id:
        await send_error(websocket, "Bạn không có bài để lật.")
        return
    raw_idx = message.get("cardIndex")
    card_idx: int | None = int(raw_idx) if raw_idx in (0, 1, "0", "1") else None
    ok, msg = room.table.reveal_player_cards(session.player_id, card_index=card_idx)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="check", toast=msg)


async def handle_rabbit_hunt(websocket: WebSocket) -> None:
    """Allow any player at the table to reveal undealt community cards after a fold win."""
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    actor_name = session.name
    if session.player_id and session.player_id in room.table.players:
        actor_name = room.table.players[session.player_id].name
    ok, msg = room.table.rabbit_hunt(actor_name=actor_name)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="deal", toast=msg)


async def handle_set_dealer(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    if not session.is_host:
        await send_error(websocket, "Chỉ Chủ bàn mới được đổi vị trí Dealer.")
        return
    seat = int(message.get("seat", 0))
    ok, msg = room.table.set_dealer_seat(seat)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, toast=msg)


async def handle_update_settings(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    if not session.is_host:
        await send_error(websocket, "Chỉ Chủ bàn mới được thay đổi cấu hình bàn.")
        return
    ok, msg = room.table.update_settings(
        small_blind=message.get("smallBlind"),
        big_blind=message.get("bigBlind"),
        ante=message.get("ante"),
        default_buy_in=message.get("defaultBuyIn"),
        currency=message.get("currency"),
        turn_timeout=message.get("turnTimeout"),
    )
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, toast=msg)
    await broadcast_room_list()


async def handle_start_hand(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return
    bomb_pot = bool(message.get("bombPot", False))
    force = bool(message.get("force", False))

    if force:
        cancel_room_tasks(room)
        ok, msg = room.table.start_hand(bomb_pot=bomb_pot)
        if not ok:
            await send_error(websocket, msg)
            return
        await broadcast_state(room, sound="allin" if bomb_pot else "deal", toast=msg)
        await broadcast_room_list()
        await schedule_room_automation(room)
        return

    # Regular start: mark current player as ready; auto-start if all seated players ready
    if not session.player_id:
        await send_error(websocket, "Bạn chưa có ghế tại bàn.")
        return

    ok, msg, all_ready = room.table.set_player_ready(session.player_id, True)
    if not ok:
        await send_error(websocket, msg)
        return

    if all_ready and room.table.street in ("idle", "showdown"):
        cancel_room_tasks(room)
        ok_start, start_msg = room.table.start_hand(bomb_pot=bomb_pot)
        if ok_start:
            await broadcast_state(room, sound="allin" if bomb_pot else "deal", toast=start_msg)
            await broadcast_room_list()
            await schedule_room_automation(room)
            return
        else:
            await send_error(websocket, start_msg)
            return

    await broadcast_state(room, toast=msg)


async def handle_ready_next(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return
    if not session.player_id:
        await send_error(websocket, "Bạn chưa có ghế tại bàn.")
        return

    ready_val = bool(message.get("ready", True))
    ok, msg, all_ready = room.table.set_player_ready(session.player_id, ready_val)
    if not ok:
        await send_error(websocket, msg)
        return

    if all_ready and room.table.street in ("idle", "showdown"):
        cancel_room_tasks(room)
        ok_start, start_msg = room.table.start_hand(bomb_pot=False)
        if ok_start:
            await broadcast_state(room, sound="deal", toast=start_msg)
            await broadcast_room_list()
            await schedule_room_automation(room)
            return
        else:
            await send_error(websocket, start_msg)
            return

    await broadcast_state(room, toast=msg)


async def handle_player_action(websocket: WebSocket, message: dict) -> None:
    """Strictly allow ONLY the player whose turn it currently is to act."""
    room, session = get_room_and_session(websocket)
    if not room or not session:
        await send_error(websocket, "Bạn chưa vào phòng.")
        return

    turn_player = room.table.get_player_by_seat(room.table.turn_seat)
    if not turn_player:
        await send_error(websocket, "Hiện không có người chơi nào đến lượt.")
        return

    if not session.player_id or session.player_id != turn_player.id:
        await send_error(websocket, f"Chưa đến lượt của bạn! Đang chờ lượt của {turn_player.name}.")
        return

    action = str(message.get("action", "")).strip().lower()
    amount = int(message.get("amount", 0) or 0)

    prev_street = room.table.street
    ok, msg = room.table.player_action(session.player_id, action, amount)
    if not ok:
        await send_error(websocket, msg)
        return

    sound = "chip"
    if action == "fold":
        sound = "fold"
    elif action == "check":
        sound = "check"
    elif action == "all_in" or room.table.all_in_runout:
        sound = "allin"
    if room.table.street in ("idle", "showdown") and prev_street not in ("idle", "showdown"):
        sound = "win"

    await broadcast_state(room, sound=sound)
    await broadcast_room_list()
    await schedule_room_automation(room)


async def handle_cancel_hand(websocket: WebSocket) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    if not session.is_host:
        await send_error(websocket, "Chỉ Chủ bàn mới được hủy ván đang chơi.")
        return
    cancel_room_tasks(room)
    ok, msg = room.table.cancel_hand()
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="fold", toast=msg)
    await broadcast_room_list()


async def handle_rebuy(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    pid = str(message.get("playerId", "") or session.player_id or "").strip()
    if session.player_id != pid and not session.is_host:
        await send_error(websocket, "Bạn chỉ có thể nạp thêm chip cho chính mình (hoặc nhờ Chủ bàn).")
        return
    amount = int(message.get("amount", 0) or 0)
    ok, msg = room.table.rebuy(pid, amount)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="chip", toast=msg)


async def handle_adjust_stack(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    if not session.is_host:
        await send_error(websocket, "Chỉ Chủ bàn mới được chỉnh số dư trực tiếp.")
        return
    pid = str(message.get("playerId", "")).strip()
    new_stack = int(message.get("newStack", 0) or 0)
    update_buy_in = bool(message.get("updateBuyIn", True))
    ok, msg = room.table.adjust_stack(pid, new_stack, update_buy_in=update_buy_in)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="chip", toast=msg)


async def handle_transfer_chips(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    from_id = str(message.get("fromId", "") or session.player_id or "").strip()
    if session.player_id != from_id and not session.is_host:
        await send_error(websocket, "Bạn chỉ có thể chuyển chip từ ví của chính mình.")
        return
    to_id = str(message.get("toId", "")).strip()
    amount = int(message.get("amount", 0) or 0)
    note = str(message.get("note", "")).strip()
    ok, msg = room.table.transfer_chips(from_id, to_id, amount, note=note)
    if not ok:
        await send_error(websocket, msg)
        return
    await broadcast_state(room, sound="chip", toast=msg)


async def handle_chat(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    text = str(message.get("text", "")).strip()[:150]
    emoji = str(message.get("emoji", "")).strip()[:10]
    if not text and not emoji:
        return

    sender_name = session.name
    if session.player_id and session.player_id in room.table.players:
        sender_name = room.table.players[session.player_id].name

    payload = {
        "type": "chat_message",
        "sender": sender_name,
        "playerId": session.player_id,
        "text": text,
        "emoji": emoji,
    }
    for ws in list(room.clients.keys()):
        try:
            await ws.send_json(payload)
        except Exception:
            pass


async def handle_throw_item(websocket: WebSocket, message: dict) -> None:
    room, session = get_room_and_session(websocket)
    if not room or not session:
        return
    item = str(message.get("item", "🍺")).strip()[:8] or "🍺"
    target_id = str(message.get("targetId", "")).strip()
    label = str(message.get("label", "")).strip()[:60]

    sender_name = session.name
    sender_seat = 0
    if session.player_id and session.player_id in room.table.players:
        sp = room.table.players[session.player_id]
        sender_name = sp.name
        sender_seat = sp.seat

    target_name = "Cả bàn"
    target_seat = -1
    if target_id and target_id in room.table.players:
        tp = room.table.players[target_id]
        target_name = tp.name
        target_seat = tp.seat

    payload = {
        "type": "throw_item",
        "fromId": session.player_id,
        "fromName": sender_name,
        "fromSeat": sender_seat,
        "toId": target_id,
        "toName": target_name,
        "toSeat": target_seat,
        "item": item,
        "label": label,
    }
    for ws in list(room.clients.keys()):
        try:
            await ws.send_json(payload)
        except Exception:
            pass


async def broadcast_state(room: Room, sound: str | None = None, toast: str | None = None) -> None:
    """Send personalized state to each connected WebSocket client so each player ONLY sees their own hole cards."""
    for ws, sess in list(room.clients.items()):
        table_state = room.table.serialize(viewer_player_id=sess.player_id)
        payload = {
            "type": "state",
            "room": room.code,
            "roomName": room.room_name,
            "myPlayerId": sess.player_id,
            "isHost": sess.is_host,
            "onlineCount": len(room.clients),
            "sound": sound,
            "toast": toast,
            "table": table_state,
        }
        try:
            await ws.send_json(payload)
        except Exception:
            pass


async def send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_json({"type": "error", "message": message})
    except Exception:
        pass
