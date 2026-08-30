from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.post import Post
from app.schemas.post import PostCreate, PostResponse, PostUpdate
from app.routers.deps import get_current_user

# Number of flags threshold once hit, post is hidden from public
FLAG_THRESHOLD = 3

router = APIRouter(
    prefix="/posts",
    tags=["Posts"]
)

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new post attached to the authenticated user.
    Check if the user belongs to a community before allowing post creation.
    """
    if current_user.community_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to a community to create posts."
        )

    new_post = Post(
        title=post.title,
        content=post.content,
        category=post.category,
        price=post.price,
        user_id=current_user.id,
        community_id=current_user.community_id
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/", response_model=List[PostResponse])
def get_posts(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch all posts in reverse chronological order (newest first).
    Requires authentication.
    Users can see non deleted + flagged posts only while staff can see all - moderation decision
    """
    if current_user.community_id is None:
        return []

    # Check role to show all posts
    is_staff = current_user.role == UserRole.STAFF

    query = (
        db.query(Post)
        .filter(
            Post.is_flagged == False,
            Post.community_id == current_user.community_id
        )
    )

    #Residents cannot see deleted posts while staff can for moderation
    if not is_staff:
        query = query.filter(Post.is_deleted == False)

    posts = (
        query.order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return posts

    # Refactored query and operation here - 
    # posts = (
    #     db.query(Post)
    #     .filter(
    #         Post.is_flagged == False,
    #         Post.community_id == current_user.community_id,
    #     )
    #     .order_by(Post.created_at.desc())
    #     .offset(skip)
    #     .limit(limit)
    #     .all()
    # )

@router.patch("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Partially upadate post. Only fields provided in the request body will be updated.
    Requires the post to be in the caller's own community and owned by the caller.
    -- two seperate checks, since being in same community is not sufficient to 
    edit someone else's post.
    """
    if current_user.community_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to a community to edit posts."
        )

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            Post.community_id == current_user.community_id,
            Post.is_deleted == False,       # cannot update deleted post
        )
        .first()
    )
    if not post:
        # same post in another community looks non existent pattern
        # as report_post: dont leak existence across community boundaries
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    if post.user_id != current_user.id:
        # Distinct from 404 above, within caller's own community
        # the post existence is already visible via the feed
        # therefore confirming ownership leaks no additional information
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own posts"
        )

    # exclude_unset=True: to update fields the client actually included in the request
    # body will be updated. PostUpdate has no report_count/is_flagged fields
    # they will not be touched here regardless of update
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)


    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soft-delete a post (mark as deleted rather than removing it from the
    database). Only the post's owner can delete it, or staff can delete
    anyone's post in their community.
    """

    if current_user.community_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a community to delete a post"
        )

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            Post.community_id == current_user.community_id,
            Post.is_deleted == False        # cannot delete already deleted post
        )
        .first()
    )
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    # Authorization: Owner can delete own posts and staff can delete all
    is_owner = post.user_id == current_user.id
    is_staff = current_user.role == UserRole.STAFF

    if not (is_owner or is_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts"
        )

    # Soft delete: marking as deleted and record the timestamp
    post.is_deleted = True
    post.deleted_at = datetime.now(timezone.utc)
    
    db.commit()
    return None


@router.post("/{post_id}/report", response_model=PostResponse)
def report_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allows authenticated residents to report an inappropriate post.
    Automatically flags and hides the post if report threshold is met.
    Cannot report a deleted post.
    """

    if current_user.community_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a community to report a post"
        )

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            Post.community_id == current_user.community_id,
            Post.is_deleted == False
        )
        .first()
    )

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    # Increment report count
    post.report_count += 1

    # Automatic flag if threshold
    if post.report_count >= FLAG_THRESHOLD:
        post.is_flagged = True

    db.commit()
    db.refresh(post)
    return post