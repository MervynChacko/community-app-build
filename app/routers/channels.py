from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload, joinedload

from app.database import get_db
from app.models.user import User
from app.models.message import Channel, ChannelMember, Message, ChannelType
from app.schemas.message import (
    DirectChatCreate,
    GroupChatCreate,
    MessageCreate,
    MessageResponse,
    ChannelResponse,
)
from app.routers.deps import get_current_user

router = APIRouter(prefix="/channels", tags=["Channels"])


def require_community(current_user: User) -> None:
    if current_user.community_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a community to use messaging",
        )


def load_channel_with_members(db: Session, channel_id: int) -> Channel:
    return (
        db.query(Channel)
        .options(selectinload(Channel.members).selectinload(ChannelMember.user))
        .filter(Channel.id == channel_id)
        .first()
    )


def require_membership(db: Session, channel_id: int, user_id: int) -> None:
    is_member = (
        db.query(ChannelMember)
        .filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
        .first()
    )
    if not is_member:
        # A channel you're not part of must look exactly like a channel
        # that doesn't exist -- don't confirm its existence, or that of
        # its members' conversation, to non-members.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )


@router.post("/direct", response_model=ChannelResponse)
def create_or_get_direct_channel(
    payload: DirectChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get-or-create semantics: returns the existing 1-1 direct channel
    between the caller and the recipient if one already exists, or
    creates a new one. Always 200 -- from the client's perspective
    there's no meaningful difference between "here is your existing DM"
    and "here is your new DM".
    """
    require_community(current_user)

    if payload.recipient_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start a direct message with yourself",
        )

    recipient = (
        db.query(User)
        .filter(
            User.id == payload.recipient_id,
            User.community_id == current_user.community_id,
        )
        .first()
    )
    if not recipient:
        # Same existence-hiding pattern used everywhere else: a
        # recipient who doesn't exist and one who exists in another
        # community are indistinguishable to the caller.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )

    # Look for an existing DIRECT channel containing exactly these two
    # users. Direct channels are always created with exactly 2 members
    # and (with no add/remove-member endpoint yet) membership never
    # changes afterward, so finding a DIRECT channel where both user ids
    # appear among its members is sufficient to identify it uniquely.
    existing_channel_row = (
        db.query(ChannelMember.channel_id)
        .join(Channel, Channel.id == ChannelMember.channel_id)
        .filter(
            Channel.type == ChannelType.DIRECT,
            Channel.community_id == current_user.community_id,
            ChannelMember.user_id.in_([current_user.id, payload.recipient_id]),
        )
        .group_by(ChannelMember.channel_id)
        # check if there are only 2 distinct users in channel
        .having(func.count(func.distinct(ChannelMember.user_id)) == 2)
        .first()
    )

    if existing_channel_row:
        return load_channel_with_members(db, existing_channel_row[0])

    new_channel = Channel(
        community_id=current_user.community_id,
        name=None,
        type=ChannelType.DIRECT,
    )
    db.add(new_channel)
    db.flush()  # populate new_channel.id

    db.add_all([
        ChannelMember(channel_id=new_channel.id, user_id=current_user.id),
        ChannelMember(channel_id=new_channel.id, user_id=payload.recipient_id),
    ])
    db.commit()

    return load_channel_with_members(db, new_channel.id)


@router.post("/group", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_group_channel(
    payload: GroupChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new group channel containing the caller plus every
    requested member. All requested members must belong to the caller's
    own community. Member add/remove after creation is not implemented
    yet (deliberately out of scope for this pass).
    """
    require_community(current_user)

    # Dedupe and drop the creator's own id if accidentally included --
    # they're added separately below, and letting a duplicate through
    # here would violate the (channel_id, user_id) uniqueness constraint.
    requested_member_ids = {mid for mid in payload.member_ids if mid != current_user.id}

    if not requested_member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A group chat needs at least one other member",
        )

    valid_members = (
        db.query(User.id)
        .filter(
            User.id.in_(requested_member_ids),
            User.community_id == current_user.community_id,
        )
        .all()
    )
    valid_member_ids = {row[0] for row in valid_members}

    if valid_member_ids != requested_member_ids:
        # Deliberately not identifying which ids were invalid -- same
        # no-partial-leak principle as elsewhere.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more members are invalid or not in your community",
        )

    new_channel = Channel(
        community_id=current_user.community_id,
        name=payload.name,
        type=ChannelType.GROUP,
    )
    db.add(new_channel)
    db.flush()

    member_rows = [ChannelMember(channel_id=new_channel.id, user_id=current_user.id)]
    member_rows += [
        ChannelMember(channel_id=new_channel.id, user_id=member_id)
        for member_id in valid_member_ids
    ]
    db.add_all(member_rows)
    db.commit()

    return load_channel_with_members(db, new_channel.id)


@router.get("/", response_model=List[ChannelResponse])
def list_my_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List every channel (direct or group) the caller is a member of.
    Membership -- not community_id -- is the actual authorization
    boundary here, though in practice they always coincide today since
    every channel is created within one community.
    """
    channels = (
        db.query(Channel)
        .join(ChannelMember, ChannelMember.channel_id == Channel.id)
        .filter(ChannelMember.user_id == current_user.id)
        .options(selectinload(Channel.members).selectinload(ChannelMember.user))
        .order_by(Channel.created_at.desc())
        .all()
    )
    return channels


@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
def get_channel_messages(
    channel_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_membership(db, channel_id, current_user.id)

    messages = (
        db.query(Message)
        .options(joinedload(Message.sender))
        .filter(Message.channel_id == channel_id)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return messages


@router.post("/{channel_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    channel_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_membership(db, channel_id, current_user.id)

    new_message = Message(
        channel_id=channel_id,
        sender_id=current_user.id,
        content=payload.content,
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message