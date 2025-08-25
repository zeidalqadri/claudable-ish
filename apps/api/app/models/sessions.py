"""
Claude Code SDK session management
"""
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.base import Base


class Session(Base):
    """Claude Code SDK session tracking"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Our internal session ID
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # Claude Code Session Management
    claude_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)  # Actual Claude Code session ID
    
    # Session Info
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, completed, failed
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cli_type: Mapped[str] = mapped_column(String(32), default="claude", nullable=False)  # claude, cursor
    
    # Transcript Management
    transcript_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    transcript_format: Mapped[str] = mapped_column(String(32), default="json")
    
    # Summary
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Performance Metrics
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_tools_used: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Context Management
    context_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Model's token limit
    context_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # Usage percentage
    context_status: Mapped[str] = mapped_column(String(16), default="safe")  # safe, warning, critical
    
    # Session Continuity
    previous_session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    session_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # Summary for context transfer
    is_continuation: Mapped[bool] = mapped_column(default=False)  # Is this a continuation session
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    tools_usage = relationship("ToolUsage", back_populates="session", cascade="all, delete-orphan")
    user_requests = relationship("UserRequest", back_populates="session")
    
    # Session Continuity Relationships
    previous_session = relationship("Session", remote_side=[id], backref="continuation_sessions")