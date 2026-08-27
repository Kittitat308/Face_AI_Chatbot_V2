import numpy as np
import unicodedata
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.models import User
from app.models import FaceEmbedding
from app.models import Chat
from app.models import Message
from app.config import settings
from app.services.password_service import hash_password, verify_password


def embedding_to_bytes(
    embedding: np.ndarray,
) -> bytes:

    return np.asarray(
        embedding,
        dtype=np.float32,
    ).tobytes()


def bytes_to_embedding(
    data: bytes,
    dimension: int,
) -> np.ndarray:

    return np.frombuffer(
        data,
        dtype=np.float32,
        count=dimension,
    )


def create_user(
    username: str,
    email: str | None,
    password: str,
) -> User:

    username = unicodedata.normalize("NFC", username)
    username_error = validate_username(username)
    if username_error:
        raise ValueError(username_error)

    with SessionLocal() as db:

        if db.scalar(select(User.id).where(User.username == username)) is not None:
            raise ValueError("ชื่อบัญชีนี้ถูกใช้งานแล้ว")

        user = User(
            username=username,
            display_name=username,
            email=normalize_identifier(email) if email else None,
            password_hash=hash_password(password),
        )

        db.add(user)

        db.commit()

        db.refresh(user)

        return user


def validate_username(username: str) -> str | None:
    if not username:
        return "กรุณากรอกชื่อบัญชี"
    if any(
        character.isspace() or unicodedata.category(character) == "Cf"
        for character in username
    ):
        return "ชื่อบัญชีต้องเขียนติดกัน ห้ามมีช่องว่างหรืออักขระแฝง"
    return None


def normalize_identifier(value: str) -> str:
    """Normalize Unicode without changing letter case."""
    return unicodedata.normalize("NFC", value.strip())


def add_face_embedding(
    user_id: int,
    embedding: np.ndarray,
):

    embedding = np.asarray(
        embedding,
        dtype=np.float32,
    )

    with SessionLocal() as db:

        face = FaceEmbedding(
            user_id=user_id,
            embedding=embedding_to_bytes(
                embedding
            ),
            dimension=embedding.size,
        )

        db.add(face)

        db.commit()


def get_all_face_embeddings():

    with SessionLocal() as db:

        rows = db.execute(
            select(FaceEmbedding, User)
            .join(User, FaceEmbedding.user_id == User.id)
            .where(User.is_active.is_(True))
        ).all()

        result = []

        for row in rows:

            face = row.FaceEmbedding
            user = row.User

            embedding = bytes_to_embedding(
                face.embedding,
                face.dimension,
            )

            result.append(
                (
                    user,
                    embedding,
                )
            )

        return result


def get_user(
    user_id: int,
):

    with SessionLocal() as db:

        return db.get(
            User,
            user_id,
        )


def update_user(
    user_id: int,
    username: str,
    email: str | None,
):

    username = unicodedata.normalize("NFC", username)
    username_error = validate_username(username)
    if username_error:
        raise ValueError(username_error)

    with SessionLocal() as db:

        user = db.get(
            User,
            user_id,
        )

        if user is None:
            return None

        duplicate = db.scalar(
            select(User.id).where(User.username == username, User.id != user_id)
        )
        if duplicate is not None:
            raise ValueError("ชื่อบัญชีนี้ถูกใช้งานแล้ว")

        user.username = username
        user.display_name = username

        user.email = (
            normalize_identifier(email)
            if email
            else None
        )

        db.commit()

        db.refresh(user)

        return user


def update_face_password_preference(user_id: int, required: bool):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return None
        user.require_password_after_face = bool(required)
        db.commit()
        db.refresh(user)
        return user


def get_user_by_identifier(identifier: str):
    identifier = normalize_identifier(identifier)
    if not identifier:
        return None
    with SessionLocal() as db:
        return db.scalar(
            select(User)
            .where(
                User.is_active.is_(True),
                or_(
                    User.username == identifier,
                    User.email == identifier,
                ),
            )
            .order_by(User.id)
        )


def authenticate_user(user_id: int, password: str):
    """Return (user, error_message), with persistent brute-force lockout."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None, "ไม่พบบัญชีผู้ใช้"

        now = datetime.utcnow()
        if user.locked_until and user.locked_until > now:
            remaining = max(1, int((user.locked_until - now).total_seconds() / 60) + 1)
            return None, f"บัญชีถูกล็อกชั่วคราว กรุณารอประมาณ {remaining} นาที"

        if not user.password_hash:
            return None, "บัญชีเดิมยังไม่มีรหัสผ่าน กรุณากดลืมรหัสผ่านเพื่อตั้งรหัสใหม่"

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_login_attempts:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_attempts = 0
            db.commit()
            return None, "รหัสผ่านไม่ถูกต้อง"

        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        db.refresh(user)
        return user, None


def set_user_password(user_id: int, new_password: str):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return None
        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        db.refresh(user)
        return user


def verify_current_password(user_id: int, password: str) -> bool:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return bool(user and verify_password(password, user.password_hash))


def get_user_chats(
    user_id: int,
):

    with SessionLocal() as db:

        statement = (
            select(Chat)
            .where(
                Chat.user_id == user_id
            )
            .order_by(
                Chat.updated_at.desc()
            )
        )

        return list(
            db.scalars(
                statement
            ).all()
        )


def create_chat(
    user_id: int,
    title: str = "New chat",
):

    with SessionLocal() as db:

        chat = Chat(
            user_id=user_id,
            title=title,
        )

        db.add(chat)

        db.commit()

        db.refresh(chat)

        return chat


def delete_chat(chat_id: int, user_id: int) -> bool:
    with SessionLocal() as db:
        chat = db.scalar(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        if chat is None:
            return False
        db.delete(chat)
        db.commit()
        return True


def get_chat(
    chat_id: int,
    user_id: int,
):

    with SessionLocal() as db:

        statement = (
            select(Chat)
            .where(
                Chat.id == chat_id,
                Chat.user_id == user_id,
            )
        )

        return db.scalar(
            statement
        )


def get_chat_messages(
    chat_id: int,
    user_id: int,
):

    with SessionLocal() as db:

        chat = db.scalar(
            select(Chat)
            .where(
                Chat.id == chat_id,
                Chat.user_id == user_id,
            )
        )

        if chat is None:
            return []

        return list(
            chat.messages
        )


def add_message(
    chat_id: int,
    user_id: int,
    role: str,
    content: str,
):

    with SessionLocal() as db:

        chat = db.scalar(
            select(Chat)
            .where(
                Chat.id == chat_id,
                Chat.user_id == user_id,
            )
        )

        if chat is None:
            raise ValueError(
                "Chat not found."
            )

        message = Message(
            chat_id=chat_id,
            role=role,
            content=content,
        )

        db.add(message)

        if (
            role == "user"
            and chat.title == "New chat"
        ):
            title = (
                content
                .replace("\n", " ")
                .strip()
            )

            chat.title = (
                title[:60]
                if title
                else "New chat"
            )

        db.commit()

        db.refresh(message)

        return message
