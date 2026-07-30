from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.schemas.post import PostCreate, PostResponse
from app.core.security import get_current_user

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
    """
    new_post = Post(
        title=post.title,
        content=post.content,
        category=post.category,
        price=post.price,
        user_id=current_user.id
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
    """
    posts = (
        db.query(Post)
        .filter(Post.is_flagged == False)
        .order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return posts

@router.post("/{post_id}/report", response_model=PostResponse)
def report_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allows authenticated residents to report an inappropriate post.
    Automatically flags and hides the post if report threshold is met
    """
    post = db.query(Post).filter(Post.id == post_id).first()

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