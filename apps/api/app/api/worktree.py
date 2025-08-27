"""
Worktree Management API
RESTful endpoints for managing git worktrees for AI sessions
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import os
from datetime import datetime

from app.api.deps import get_db
from app.models.projects import Project
from app.models.sessions import Session as SessionModel
from app.models.worktree_sessions import WorktreeSession
from app.services.worktree_manager import get_project_worktree_manager, WorktreeError
from app.services.water_names import get_water_info


router = APIRouter()


# Pydantic Models for API
class WorktreeCreateRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to create worktree for")
    base_branch: Optional[str] = Field("main", description="Base branch to create worktree from")
    description: Optional[str] = Field(None, description="Optional description for the worktree")


class WorktreeResponse(BaseModel):
    id: str
    session_id: str
    branch_name: str
    water_name: str
    water_display: str
    water_emoji: str
    worktree_path: str
    status: str
    created_at: str
    last_activity: Optional[str] = None
    changes_count: Optional[int] = None
    is_clean: bool
    description: Optional[str] = None


class WorktreeChangesResponse(BaseModel):
    session_id: str
    branch_name: str
    changes: Dict[str, List[str]]  # {"modified": [], "added": [], "deleted": []}
    total_changes: int


class WorktreeDiffResponse(BaseModel):
    session_id: str
    branch_name: str
    diff_content: str
    file_path: Optional[str] = None


class WorktreeMergeRequest(BaseModel):
    target_branch: Optional[str] = Field("main", description="Target branch to merge into")


class WorktreeActionResponse(BaseModel):
    success: bool
    message: str
    session_id: str


@router.post("/{project_id}/worktree/create", response_model=WorktreeResponse)
async def create_worktree(
    project_id: str,
    request: WorktreeCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new worktree for an AI session"""
    
    # Verify project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify session exists
    session = db.get(SessionModel, request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured. Please ensure the project is properly initialized.")
    
    if not os.path.exists(project.repo_path):
        raise HTTPException(status_code=400, detail=f"Project repository not found at path: {project.repo_path}")
    
    # Check if it's a git repository
    git_dir = os.path.join(project.repo_path, '.git')
    if not os.path.exists(git_dir):
        raise HTTPException(status_code=400, detail="Project directory is not a git repository. Please initialize git first.")
    
    # Check if worktree already exists for this session
    existing_worktree = db.query(WorktreeSession).filter(
        WorktreeSession.session_id == request.session_id,
        WorktreeSession.status == "active"
    ).first()
    
    if existing_worktree:
        raise HTTPException(status_code=409, detail="Active worktree already exists for this session")
    
    try:
        # Create worktree using manager
        manager = get_project_worktree_manager(project.repo_path)
        worktree_session = manager.create_worktree(
            session_id=request.session_id,
            base_branch=request.base_branch
        )
        
        # Create database record
        db_worktree = WorktreeSession(
            id=f"{project_id}-{request.session_id}",
            project_id=project_id,
            session_id=request.session_id,
            branch_name=worktree_session.branch_name,
            water_name=worktree_session.water_name,
            worktree_path=worktree_session.worktree_path,
            base_branch=request.base_branch,
            description=request.description or f"AI session: {worktree_session.water_name.replace('-', ' ').title()}"
        )
        
        db.add(db_worktree)
        db.commit()
        db.refresh(db_worktree)
        
        return WorktreeResponse(**db_worktree.to_dict())
        
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create worktree: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{project_id}/worktree", response_model=List[WorktreeResponse])
async def list_worktrees(
    project_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all worktrees for a project"""
    
    # Verify project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = db.query(WorktreeSession).filter(WorktreeSession.project_id == project_id)
    
    if status:
        query = query.filter(WorktreeSession.status == status)
    
    worktrees = query.order_by(WorktreeSession.created_at.desc()).all()
    
    return [WorktreeResponse(**wt.to_dict()) for wt in worktrees]


@router.get("/{project_id}/worktree/{session_id}", response_model=WorktreeResponse)
async def get_worktree(
    project_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get details of a specific worktree"""
    
    worktree = db.query(WorktreeSession).filter(
        WorktreeSession.project_id == project_id,
        WorktreeSession.session_id == session_id
    ).first()
    
    if not worktree:
        raise HTTPException(status_code=404, detail="Worktree not found")
    
    # Update with latest git info if active
    if worktree.status == "active":
        try:
            project = db.get(Project, project_id)
            if project and project.repo_path:
                manager = get_project_worktree_manager(project.repo_path)
                worktree.update_from_git(manager)
                db.commit()
        except Exception:
            pass  # Continue even if git update fails
    
    return WorktreeResponse(**worktree.to_dict())


@router.get("/{project_id}/worktree/{session_id}/changes", response_model=WorktreeChangesResponse)
async def get_worktree_changes(
    project_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get changes in a worktree compared to main branch"""
    
    # Get project and worktree
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    worktree = db.query(WorktreeSession).filter(
        WorktreeSession.project_id == project_id,
        WorktreeSession.session_id == session_id
    ).first()
    
    if not worktree:
        raise HTTPException(status_code=404, detail="Worktree not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured")
    
    try:
        manager = get_project_worktree_manager(project.repo_path)
        changes = manager.get_session_changes(session_id)
        
        total_changes = sum(len(files) for files in changes.values())
        
        # Update changes count in database
        worktree.changes_count = total_changes
        worktree.last_activity = datetime.now()
        db.commit()
        
        return WorktreeChangesResponse(
            session_id=session_id,
            branch_name=worktree.branch_name,
            changes=changes,
            total_changes=total_changes
        )
        
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/worktree/{session_id}/diff", response_model=WorktreeDiffResponse)
async def get_worktree_diff(
    project_id: str,
    session_id: str,
    file_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get detailed diff for a worktree"""
    
    # Get project and worktree
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    worktree = db.query(WorktreeSession).filter(
        WorktreeSession.project_id == project_id,
        WorktreeSession.session_id == session_id
    ).first()
    
    if not worktree:
        raise HTTPException(status_code=404, detail="Worktree not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured")
    
    try:
        manager = get_project_worktree_manager(project.repo_path)
        diff_content = manager.get_session_diff(session_id, file_path)
        
        return WorktreeDiffResponse(
            session_id=session_id,
            branch_name=worktree.branch_name,
            diff_content=diff_content,
            file_path=file_path
        )
        
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/worktree/{session_id}/merge", response_model=WorktreeActionResponse)
async def merge_worktree(
    project_id: str,
    session_id: str,
    request: WorktreeMergeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Merge a worktree back to main branch"""
    
    # Get project and worktree
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    worktree = db.query(WorktreeSession).filter(
        WorktreeSession.project_id == project_id,
        WorktreeSession.session_id == session_id,
        WorktreeSession.status == "active"
    ).first()
    
    if not worktree:
        raise HTTPException(status_code=404, detail="Active worktree not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured")
    
    try:
        manager = get_project_worktree_manager(project.repo_path)
        success = manager.merge_session(session_id, request.target_branch)
        
        if success:
            # Update database record
            worktree.status = "merged"
            worktree.merged_at = datetime.now()
            
            # Get merge commit hash
            returncode, stdout, stderr = manager._run_git_command(["rev-parse", "HEAD"])
            if returncode == 0:
                worktree.merge_commit_hash = stdout.strip()
            
            db.commit()
            
            # Schedule cleanup in background
            background_tasks.add_task(_cleanup_merged_worktree, project.repo_path, session_id)
            
            return WorktreeActionResponse(
                success=True,
                message=f"Successfully merged {worktree.branch_name} into {request.target_branch}",
                session_id=session_id
            )
        else:
            raise HTTPException(status_code=500, detail="Merge failed")
            
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/worktree/{session_id}/discard", response_model=WorktreeActionResponse)
async def discard_worktree(
    project_id: str,
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Discard a worktree (delete without merging)"""
    
    # Get worktree
    worktree = db.query(WorktreeSession).filter(
        WorktreeSession.project_id == project_id,
        WorktreeSession.session_id == session_id,
        WorktreeSession.status == "active"
    ).first()
    
    if not worktree:
        raise HTTPException(status_code=404, detail="Active worktree not found")
    
    # Get project for repo path
    project = db.get(Project, project_id)
    if not project or not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured")
    
    try:
        manager = get_project_worktree_manager(project.repo_path)
        success = manager.discard_session(session_id)
        
        if success:
            # Update database record
            worktree.status = "discarded"
            worktree.discarded_at = datetime.now()
            db.commit()
            
            return WorktreeActionResponse(
                success=True,
                message=f"Successfully discarded worktree {worktree.branch_name}",
                session_id=session_id
            )
        else:
            raise HTTPException(status_code=500, detail="Discard failed")
            
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/worktree/cleanup")
async def cleanup_stale_worktrees(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Clean up stale/orphaned worktrees"""
    
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not configured")
    
    try:
        manager = get_project_worktree_manager(project.repo_path)
        cleaned_count = manager.cleanup_stale_worktrees()
        
        # Update database records for cleaned worktrees
        stale_worktrees = db.query(WorktreeSession).filter(
            WorktreeSession.project_id == project_id,
            WorktreeSession.status == "active"
        ).all()
        
        db_cleaned_count = 0
        for worktree in stale_worktrees:
            if not os.path.exists(worktree.worktree_path):
                worktree.status = "discarded"
                worktree.discarded_at = datetime.now()
                worktree.error_message = "Cleaned up stale worktree"
                db_cleaned_count += 1
        
        db.commit()
        
        return {
            "cleaned_count": cleaned_count,
            "db_updated_count": db_cleaned_count,
            "message": f"Cleaned up {cleaned_count} stale worktrees"
        }
        
    except WorktreeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def _cleanup_merged_worktree(project_path: str, session_id: str):
    """Background task to clean up a merged worktree after some delay"""
    import asyncio
    
    # Wait a bit before cleanup to allow user to see the merge
    await asyncio.sleep(30)
    
    try:
        manager = get_project_worktree_manager(project_path)
        manager.discard_session(session_id, cleanup_worktree=True)
    except Exception as e:
        # Log error but don't fail
        print(f"Failed to cleanup merged worktree {session_id}: {e}")