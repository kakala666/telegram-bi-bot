from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SubBot(Base):
    __tablename__ = "sub_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    bot_username: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    bot_users: Mapped[list["BotUser"]] = relationship(
        back_populates="sub_bot", cascade="all, delete-orphan"
    )
    message_maps: Mapped[list["MessageMap"]] = relationship(
        back_populates="sub_bot", cascade="all, delete-orphan"
    )
    ad_configs: Mapped[list["AdConfig"]] = relationship(
        back_populates="target_bot", cascade="all, delete-orphan"
    )
    broadcast_tasks: Mapped[list["BroadcastTask"]] = relationship(
        back_populates="sub_bot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sub_bots_owner_id", "owner_id"),
        Index("idx_sub_bots_bot_id", "bot_id", unique=True),
        Index("idx_sub_bots_status", "status"),
    )


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sub_bots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned_by_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    sub_bot: Mapped["SubBot"] = relationship(back_populates="bot_users")

    __table_args__ = (
        Index("idx_bot_users_sub_bot_user", "sub_bot_id", "user_id", unique=True),
        Index("idx_bot_users_sub_bot_blocked", "sub_bot_id", "is_blocked"),
    )


class MessageMap(Base):
    __tablename__ = "message_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sub_bots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_msg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    forwarded_msg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="in")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    sub_bot: Mapped["SubBot"] = relationship(back_populates="message_maps")

    __table_args__ = (
        Index("idx_msg_map_forwarded", "sub_bot_id", "forwarded_msg_id"),
        Index("idx_msg_map_created", "created_at"),
    )


class AdConfig(Base):
    __tablename__ = "ad_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    ad_text: Mapped[str] = mapped_column(Text, nullable=False)
    ad_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    target_bot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sub_bots.id", ondelete="CASCADE"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impression_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    target_bot: Mapped["SubBot | None"] = relationship(back_populates="ad_configs")

    __table_args__ = (
        Index("idx_ad_active_priority", "is_active", "priority"),
        Index("idx_ad_target", "target_type", "target_bot_id"),
    )


class BroadcastTask(Base):
    __tablename__ = "broadcast_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sub_bots.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(16), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sub_bot: Mapped["SubBot"] = relationship(back_populates="broadcast_tasks")

    __table_args__ = (
        Index("idx_broadcast_sub_bot", "sub_bot_id", "status"),
        Index("idx_broadcast_status", "status"),
    )
