"""
Context Management API Endpoints
Handles context usage calculation, limits, and session continuity
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.projects import Project
from app.models.sessions import Session as SessionModel
from app.models.messages import Message

router = APIRouter()

# Model token limits (tokens)
MODEL_LIMITS = {
    'claude-sonnet-4': 200000,
    'claude-opus-4': 200000,
    'claude-opus-4.1': 200000,
    'claude-haiku-4': 200000,
    'claude-3-5-sonnet': 200000,
    'default': 200000
}

class ContextUsage(BaseModel):
    current: int
    limit: int
    percentage: float
    status: str  # safe, warning, critical
    session_id: str | None = None
    model: str | None = None

class SessionContextInfo(BaseModel):
    session_id: str
    total_tokens: int
    message_count: int
    context_percentage: float
    context_status: str
    started_at: datetime
    is_active: bool

class ContextResponse(BaseModel):
    current_session: SessionContextInfo | None
    all_sessions: List[SessionContextInfo]
    can_create_new: bool
    recommendations: List[str]

def calculate_context_status(percentage: float) -> str:
    """Calculate context status based on percentage"""
    if percentage < 70:
        return 'safe'
    elif percentage < 85:
        return 'warning'
    else:
        return 'critical'

def get_context_recommendations(status: str, percentage: float) -> List[str]:
    """Get context usage recommendations"""
    recommendations = []
    
    if status == 'warning':
        recommendations.extend([
            "Consider wrapping up complex tasks",
            "Save important work before continuing",
            "Prepare to create a new session soon"
        ])
    elif status == 'critical':
        recommendations.extend([
            "Critical context usage detected",
            "Create a new session to continue development",
            "Export current chat history if needed",
            "Consider summarizing progress before switching"
        ])
    else:
        recommendations.append("Context usage is healthy")
    
    return recommendations

@router.get("/{project_id}/context", response_model=ContextResponse)
async def get_project_context(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get comprehensive context information for a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all sessions for the project
    sessions = db.query(SessionModel).filter(
        SessionModel.project_id == project_id
    ).order_by(desc(SessionModel.started_at)).all()
    
    session_infos = []
    current_session_info = None
    
    for session in sessions:
        # Calculate tokens from messages if not cached
        if session.total_tokens == 0 or session.total_tokens is None:
            total_tokens = db.query(func.sum(Message.token_count)).filter(
                Message.session_id == session.id,
                Message.token_count.isnot(None)
            ).scalar() or 0
            
            # Update session with calculated tokens
            session.total_tokens = total_tokens
            db.commit()
        else:
            total_tokens = session.total_tokens
        
        # Get model limit
        model_limit = MODEL_LIMITS.get(session.model, MODEL_LIMITS['default'])
        percentage = (total_tokens / model_limit) * 100 if model_limit > 0 else 0
        status = calculate_context_status(percentage)
        
        # Update session context info
        session.context_percentage = percentage
        session.context_status = status
        session.context_limit = model_limit
        
        session_info = SessionContextInfo(
            session_id=session.id,
            total_tokens=total_tokens,
            message_count=session.total_messages,
            context_percentage=percentage,
            context_status=status,
            started_at=session.started_at,
            is_active=session.status in ['active', 'running']
        )
        
        session_infos.append(session_info)
        
        # Mark the most recent active session as current
        if session.status in ['active', 'running'] and current_session_info is None:
            current_session_info = session_info
    
    # Commit context updates
    db.commit()
    
    # Determine if user can create new session
    can_create_new = True
    if current_session_info and current_session_info.context_percentage < 95:
        can_create_new = False
    
    # Get recommendations
    recommendations = []
    if current_session_info:
        recommendations = get_context_recommendations(
            current_session_info.context_status,
            current_session_info.context_percentage
        )
    
    return ContextResponse(
        current_session=current_session_info,
        all_sessions=session_infos,
        can_create_new=can_create_new,
        recommendations=recommendations
    )

@router.get("/{project_id}/sessions/{session_id}/context", response_model=ContextUsage)
async def get_session_context(
    project_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get context usage for a specific session"""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.project_id == project_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calculate total tokens from messages
    total_tokens = db.query(func.sum(Message.token_count)).filter(
        Message.session_id == session_id,
        Message.token_count.isnot(None)
    ).scalar() or 0
    
    # Update session if tokens changed
    if session.total_tokens != total_tokens:
        session.total_tokens = total_tokens
        db.commit()
    
    # Get model limit
    model_limit = MODEL_LIMITS.get(session.model, MODEL_LIMITS['default'])
    percentage = (total_tokens / model_limit) * 100 if model_limit > 0 else 0
    status = calculate_context_status(percentage)
    
    return ContextUsage(
        current=total_tokens,
        limit=model_limit,
        percentage=percentage,
        status=status,
        session_id=session_id,
        model=session.model
    )

@router.post("/{project_id}/sessions/new")
async def create_new_session(
    project_id: str,
    previous_session_id: Optional[str] = None,
    include_summary: bool = True,
    db: Session = Depends(get_db)
):
    """Create a new session for continued development"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get previous session if specified
    previous_session = None
    session_summary = None
    
    if previous_session_id:
        previous_session = db.query(SessionModel).filter(
            SessionModel.id == previous_session_id,
            SessionModel.project_id == project_id
        ).first()
        
        if not previous_session:
            raise HTTPException(status_code=404, detail="Previous session not found")
        
        # Mark previous session as completed
        if previous_session.status in ['active', 'running']:
            previous_session.status = 'completed'
            previous_session.completed_at = datetime.utcnow()
        
        # Generate summary if requested and not already exists
        if include_summary and not previous_session.session_summary:
            # Get recent messages for summary (last 10 messages)
            recent_messages = db.query(Message).filter(
                Message.session_id == previous_session_id
            ).order_by(desc(Message.created_at)).limit(10).all()
            
            if recent_messages:
                # Simple summary generation
                user_messages = [msg.content for msg in recent_messages if msg.role == 'user']
                if user_messages:
                    session_summary = f"Previous session involved: {'; '.join(user_messages[-3:])}"
                    previous_session.session_summary = session_summary
    
    # Create new session
    new_session_id = str(uuid.uuid4())
    new_session = SessionModel(
        id=new_session_id,
        project_id=project_id,
        status='active',
        model=previous_session.model if previous_session else 'claude-sonnet-4',
        cli_type=previous_session.cli_type if previous_session else 'claude',
        previous_session_id=previous_session_id,
        is_continuation=previous_session_id is not None,
        context_limit=MODEL_LIMITS.get(previous_session.model if previous_session else 'default', MODEL_LIMITS['default']),
        context_status='safe',
        context_percentage=0.0
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {
        "session_id": new_session.id,
        "previous_session_id": previous_session_id,
        "summary": session_summary,
        "is_continuation": new_session.is_continuation,
        "model": new_session.model
    }

@router.put("/{project_id}/sessions/{session_id}/context")
async def update_session_context(
    project_id: str,
    session_id: str,
    total_tokens: int,
    db: Session = Depends(get_db)
):
    """Update session context usage (called by chat system)"""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.project_id == project_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update context information
    model_limit = session.context_limit or MODEL_LIMITS.get(session.model, MODEL_LIMITS['default'])
    percentage = (total_tokens / model_limit) * 100 if model_limit > 0 else 0
    status = calculate_context_status(percentage)
    
    session.total_tokens = total_tokens
    session.context_percentage = percentage
    session.context_status = status
    session.context_limit = model_limit
    
    db.commit()
    
    return {
        "total_tokens": total_tokens,
        "percentage": percentage,
        "status": status,
        "recommendations": get_context_recommendations(status, percentage)
    }