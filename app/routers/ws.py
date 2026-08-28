import asyncio
import json

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal
from app.core.security import decode_access_token
from app.core.sockets import manager
from app.models.user import User
from app.models.message import ChannelMember
from app.routers.channels import is_channel_member, create_message

router = APIRouter(tags=["WebSocket"])

AUTH_TIMEOUT_SECONDS = 10


def lookup_user_sync(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def get_channel_member_ids_sync(db: Session, channel_id: int) -> list:
    rows = (
        db.query(ChannelMember.user_id)
        .filter(ChannelMember.channel_id == channel_id)
        .all()
    )
    return [r[0] for r in rows]


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Single multiplexed connection per user covering all their channels
    instead of one connection per channel. 

    NOTE: this app's SQLAlchemy session is synchronous (blocking psycopg2 i/o)
    FastAPI auto-offloads plain 'def' REST endpoints to a thread pool
    This is why sync DB calls are safe everywhere else in the app. Inside async def handler,
    nothing is offloaded automatically: Every DB call must go through run_in_threadpool()
    or it blocks the single shared event loop for the entire duration, stalling every other 
    connected users socket.

    Protocol:
    1. Client connects, then sends first message: 
    {"type": "auth", "token": "<jwt access token>"}
    Deliberately not a query parameter - URLs get logged by
    proxies/load balancer/browser history, so the token travels 
    in the first message body
    2. Server response: {"type": "auth_success", "user_id": <int>}
    OR {"type": "auth_error", "detail": "..."} and closes socket on failure
    3. Client sends: {"type": "message", "channel_id": <int>, "content": "<str>"}
    4. Server persists(identical logic to REST endpoint, via shared create_message helper)
    and broadcasts {"type": "message",...} to all members of channel
    """

    await websocket.accept()

    db = SessionLocal()
    user = None
    try:
        # Auth via first message with timeout so a connection that doesnt send anything 
        # does not hang forever
        try:
            auth_raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            await websocket.send_json(
                {
                    "type": "auth_error",
                    "detail": "Authentication timed out"
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            auth_data = json.loads(auth_raw)
        except json.JSONDecodeError:
            await websocket.send_json(
                {
                    "type": "auth_error",
                    "detail": "Malformed auth message"
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if auth_data.get("type") != "auth" or "token" not in auth_data:
            await websocket.send_json(
                {
                    "type": "auth_error",
                    "detail": "First message must be auth message"
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            payload = decode_access_token(auth_data["token"])
            user_id = payload.get("sub")
            if user_id is None:
                raise ValueError("missing sub claim")
            user_id = int(user_id)
        except (jwt.PyJWTError, ValueError, TypeError):
            await websocket.send_json(
                {
                    "type": "auth_error",
                    "detail": "Invalid or expired token"
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Offloaded blocking DB call inside async handler
        user = await run_in_threadpool(lookup_user_sync, db, user_id)
        if user is None:
            await websocket.send_json(
                {
                    "type": "auth_error",
                    "detail": "Invalid or expired token"
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        manager.connect(user.id, websocket)
        await websocket.send_json(
            {
                "type": "auth_success",
                "user_id": user.id
            }
        )

        # Main receive loop

        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "Malformed message"
                    }
                )
                continue

            if data.get("type") != "message":
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail":"Unknown message type"
                    }
                )
                continue

            channel_id = data.get("channel_id")
            content = data.get("content")

            if not isinstance(channel_id, int) or not isinstance(content, str) or not content.strip():
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "channel_id (int) and content (non-empty string) are required"
                    }
                )
                continue

            # Offloaded blocking DB call
            member = await run_in_threadpool(is_channel_member, db, channel_id, user.id)
            if not member:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "Channel not found"
                    }
                )
                continue

            message = await run_in_threadpool(create_message, db, channel_id=channel_id, sender_id=user.id, content=content)

            broadcast_payload = {
                            "type": "message",
                            "id": message.id,
                            "channel_id": message.channel_id,
                            "sender_id": message.sender_id,
                            "content": message.content,
                            "created_at": message.created_at.isoformat(),
                        }

            member_ids = await run_in_threadpool(get_channel_member_ids_sync, db, channel_id)
            await manager.broadcast_to_users(member_ids, broadcast_payload)

    except WebSocketDisconnect:
        pass
    finally:
        if user is not None:
            manager.disconnect(user.id, websocket)
        db.close()