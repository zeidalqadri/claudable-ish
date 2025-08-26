"""
Memory Models
Database models for storing project memories and embeddings
"""
from sqlalchemy import String, DateTime, Text, JSON, Integer, Float, Boolean, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.base import Base
from typing import List, Optional, Dict, Any


class ProjectMemory(Base):
    """Store project memories for persistent knowledge management"""
    __tablename__ = "project_memories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    
    # Memory content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Brief summary for quick reference
    
    # Source information
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 'conversation', 'file', 'url', 'manual'
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Message ID, file path, URL
    
    # Categorization and metadata
    tags: Mapped[List[str] | None] = mapped_column(JSON, nullable=True)  # List of tags
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # 0-1 importance score
    
    # Usage tracking
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # How many times accessed
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Embedding for semantic search (stored as JSON array)
    embedding: Mapped[List[float] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Model used for embedding
    
    # SuperMemory integration
    supermemory_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # ID in SuperMemory service
    synced_with_supermemory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # Sync error message
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="memories")
    memory_usages = relationship("MemoryUsage", back_populates="memory", cascade="all, delete-orphan")


class MemoryUsage(Base):
    """Track when and how memories are used in conversations"""
    __tablename__ = "memory_usages"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("project_memories.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    message_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Usage context
    query: Mapped[str | None] = mapped_column(Text, nullable=True)  # The query that retrieved this memory
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Similarity score when retrieved
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Rank in search results
    
    # Usage metadata
    context: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 'context_enhancement', 'user_search', 'auto_suggestion'
    
    # Timestamps
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    memory = relationship("ProjectMemory", back_populates="memory_usages")
    session = relationship("Session")
    message = relationship("Message")


class MemoryCollection(Base):
    """Organize memories into collections/folders"""
    __tablename__ = "memory_collections"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Collection info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color code
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Icon name or emoji
    
    # Collection metadata
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Auto-created by system
    auto_rules: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # Rules for auto-adding memories
    
    # Stats
    memory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project")
    memory_assignments = relationship("MemoryCollectionAssignment", back_populates="collection", cascade="all, delete-orphan")


class MemoryCollectionAssignment(Base):
    """Many-to-many relationship between memories and collections"""
    __tablename__ = "memory_collection_assignments"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("project_memories.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id: Mapped[str] = mapped_column(String(64), ForeignKey("memory_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Assignment metadata
    assigned_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'user', 'system', 'auto'
    assignment_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Why was this memory assigned
    
    # Timestamps
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    memory = relationship("ProjectMemory")
    collection = relationship("MemoryCollection", back_populates="memory_assignments")


class MemorySearchIndex(Base):
    """Full-text search index for memories (backup for when vector search is not available)"""
    __tablename__ = "memory_search_index"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("project_memories.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Searchable content (processed for full-text search)
    searchable_content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[List[str] | None] = mapped_column(JSON, nullable=True)  # Extracted keywords
    
    # Search metadata
    language: Mapped[str | None] = mapped_column(String(10), default="en", nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Hash of content for change detection
    
    # Timestamps
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    memory = relationship("ProjectMemory")


