"""
Worktree Sessions Database Model
Tracks git worktree sessions for AI development
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

from app.db.base import Base


class WorktreeSession(Base):
    """
    Tracks worktree sessions for isolated AI development
    """
    __tablename__ = "worktree_sessions"

    # Primary identifiers
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"))
    
    # Git information
    branch_name: Mapped[str] = mapped_column(String(256), nullable=False)  # e.g., "ai/pacific-a7f2"
    water_name: Mapped[str] = mapped_column(String(128), nullable=False)   # e.g., "pacific"
    worktree_path: Mapped[str] = mapped_column(String(512), nullable=False) # Absolute path to worktree
    base_branch: Mapped[str] = mapped_column(String(256), default="main")  # Branch it was created from
    
    # Session status and lifecycle
    status: Mapped[str] = mapped_column(
        String(32), 
        default="active"
    )  # active, merged, discarded, failed
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # Latest commit in worktree
    changes_count: Mapped[Optional[int]] = mapped_column(nullable=True)  # Number of files changed
    merge_commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # Merge commit if merged
    
    # Flags
    is_clean: Mapped[bool] = mapped_column(Boolean, default=True)  # Whether worktree has uncommitted changes
    auto_created: Mapped[bool] = mapped_column(Boolean, default=True)  # Created automatically vs manually
    
    # Optional notes/description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Error if failed
    
    # Relationships
    project = relationship("Project", back_populates="worktree_sessions")
    session = relationship("Session", back_populates="worktree_session")
    
    def __repr__(self) -> str:
        return f"<WorktreeSession {self.branch_name} ({self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        from app.services.water_names import get_water_info
        
        water_info = get_water_info(self.water_name)
        
        return {
            "id": self.id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "water_name": self.water_name,
            "water_display": water_info["display_name"],
            "water_emoji": water_info["emoji"],
            "worktree_path": self.worktree_path,
            "base_branch": self.base_branch,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "discarded_at": self.discarded_at.isoformat() if self.discarded_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "commit_hash": self.commit_hash,
            "changes_count": self.changes_count,
            "merge_commit_hash": self.merge_commit_hash,
            "is_clean": self.is_clean,
            "auto_created": self.auto_created,
            "description": self.description,
            "error_message": self.error_message
        }
    
    @classmethod
    def create_from_worktree(cls, worktree_session, project_id: str, session_id: str):
        """
        Create database record from WorktreeManager session
        
        Args:
            worktree_session: WorktreeSession from WorktreeManager
            project_id: Project ID
            session_id: Session ID
            
        Returns:
            WorktreeSession database instance
        """
        return cls(
            id=f"{project_id}-{session_id}",
            project_id=project_id,
            session_id=session_id,
            branch_name=worktree_session.branch_name,
            water_name=worktree_session.water_name,
            worktree_path=worktree_session.worktree_path,
            status=worktree_session.status,
            description=f"AI session worktree: {worktree_session.water_name.replace('-', ' ').title()}"
        )
    
    def update_from_git(self, worktree_manager):
        """
        Update database record with latest git information
        
        Args:
            worktree_manager: WorktreeManager instance
        """
        try:
            # Get latest commit hash
            returncode, stdout, stderr = worktree_manager._run_git_command([
                "rev-parse", "HEAD"
            ], cwd=self.worktree_path)
            
            if returncode == 0:
                self.commit_hash = stdout.strip()
                
            # Check if worktree is clean
            returncode, stdout, stderr = worktree_manager._run_git_command([
                "status", "--porcelain"
            ], cwd=self.worktree_path)
            
            if returncode == 0:
                self.is_clean = len(stdout.strip()) == 0
                
            # Get changes count
            try:
                changes = worktree_manager.get_session_changes(self.session_id)
                total_changes = len(changes.get("modified", [])) + len(changes.get("added", [])) + len(changes.get("deleted", []))
                self.changes_count = total_changes
            except Exception:
                pass
                
            # Update last activity
            self.last_activity = datetime.now()
            
        except Exception as e:
            self.error_message = str(e)