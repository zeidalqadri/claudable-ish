"""
GitHub integration API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import logging

from app.api.deps import get_db
from app.models.projects import Project
from app.models.project_services import ProjectServiceConnection
from app.services.github_service import GitHubService, GitHubAPIError, check_repo_availability
from app.services.token_service import get_token
from app.services.git_ops import (
    add_remote, 
    push_to_remote, 
    initialize_main_branch, 
    set_git_config,
    commit_all
)
from uuid import uuid4

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["github"])


class GitHubConnectRequest(BaseModel):
    repo_name: str
    description: str = ""
    private: bool = False


class GitHubConnectResponse(BaseModel):
    success: bool
    repo_url: str
    message: str


class GitPushResponse(BaseModel):
    success: bool
    message: str
    branch: Optional[str] = None


@router.get("/github/check-repo/{repo_name}")
async def check_repository_availability(repo_name: str, db: Session = Depends(get_db)):
    """Check if a GitHub repository name is available"""
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        result = await check_repo_availability(github_token, repo_name)
        
        if "error" in result:
            if "Invalid" in result["error"]:
                raise HTTPException(status_code=401, detail=result["error"])
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        if result["exists"]:
            raise HTTPException(status_code=409, detail=f"Repository '{repo_name}' already exists")
        
        return {"available": True, "username": result["username"]}
        
    except GitHubAPIError as e:
        if e.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token")
        else:
            raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking repository availability: {e}")
        raise HTTPException(status_code=500, detail="Failed to check repository availability")


@router.post("/projects/{project_id}/github/connect", response_model=GitHubConnectResponse)
async def connect_github_repository(
    project_id: str, 
    request: GitHubConnectRequest,
    db: Session = Depends(get_db)
):
    """Create GitHub repository and connect it to the project"""
    
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured. Please add your GitHub token in Global Settings.")
    
    try:
        # Initialize GitHub service
        github_service = GitHubService(github_token)
        
        # Validate token and get user info
        user_info = await github_service.check_token_validity()
        if not user_info.get("valid"):
            raise HTTPException(status_code=401, detail="Invalid GitHub token")
        
        username = user_info["username"]
        user_name = user_info.get("name") or username
        user_email = user_info.get("email") or f"{username}@users.noreply.github.com"
        
        # Create GitHub repository
        repo_result = await github_service.create_repository(
            repo_name=request.repo_name,
            description=request.description,
            private=request.private,
            auto_init=False  # We'll push our existing code
        )
        
        if not repo_result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to create GitHub repository")
        
        # Get repository info
        repo_url = repo_result["repo_url"]
        clone_url = repo_result["clone_url"]
        default_branch = repo_result.get("default_branch", "main")
        
        # Setup local Git repository
        # Try different path patterns
        if project.repo_path and os.path.exists(project.repo_path):
            # Use project repo path directly
            repo_path = project.repo_path
        elif project.repo_path and os.path.exists(os.path.join(project.repo_path, "repo")):
            # Use repo subfolder
            repo_path = os.path.join(project.repo_path, "repo")
        else:
            # Use standard project structure: ./data/projects/{project_id}/repo
            from pathlib import Path
            root_dir = Path(__file__).parent.parent.parent.parent  # Get to cc-lovable root
            repo_path = root_dir / "data" / "projects" / project.id / "repo"
            repo_path = str(repo_path.resolve())
            
            if not os.path.exists(repo_path):
                raise HTTPException(
                    status_code=500, 
                    detail=f"Project repository not found at expected path: {repo_path}"
                )
        
        if not repo_path or not os.path.exists(repo_path):
            raise HTTPException(status_code=500, detail=f"Could not create or find project repository path: {repo_path}")
        
        # Update project repo_path in database if it was changed
        if project.repo_path != repo_path:
            project.repo_path = repo_path
            db.commit()
        
        try:
            # Set Git config
            set_git_config(repo_path, user_name, user_email)
            
            # Initialize main branch and ensure we have commits
            initialize_main_branch(repo_path)
            
            # Create authenticated URL with DB token
            authenticated_url = clone_url.replace(
                "https://github.com/", 
                f"https://{username}:{github_token}@github.com/"
            )
            
            # Add remote origin with authentication
            add_remote(repo_path, "origin", authenticated_url)
            
            # Commit any pending changes
            commit_result = commit_all(repo_path, "Initial commit - connected to GitHub")
            if not commit_result.get("success") and "nothing to commit" not in str(commit_result.get("error", "")):
                logger.warning(f"Commit failed: {commit_result.get('error')}")
            
            # NOTE: Do not push on connect. Publishing will be triggered explicitly from UI.
            
        except Exception as git_error:
            logger.error(f"Git operations failed: {git_error}")
            # Repository was created but Git setup failed
            raise HTTPException(
                status_code=500, 
                detail=f"GitHub repository created successfully at {repo_url}, but local Git setup failed: {str(git_error)}. You may need to connect manually."
            )
        
        # Update project with repository information
        project.repo_url = repo_url
        project.repo_name = repo_result.get("full_name", f"{username}/{request.repo_name}")
        project.repo_default_branch = default_branch
        project.repo_cloned_at = datetime.utcnow()
        
        # Save service connection to database
        try:
            # Check if GitHub connection already exists
            existing_connection = db.query(ProjectServiceConnection).filter(
                ProjectServiceConnection.project_id == project_id,
                ProjectServiceConnection.provider == "github"
            ).first()
            
            service_data = {
                "repo_url": repo_url,
                "repo_name": request.repo_name,
                "clone_url": clone_url,
                "ssh_url": repo_result.get("ssh_url"),
                "default_branch": default_branch,
                "private": request.private,
                "username": username,
                "full_name": repo_result.get("full_name"),
                "repo_id": repo_result.get("repo_id")
            }
            
            if existing_connection:
                # Update existing connection
                existing_connection.service_data = service_data
                existing_connection.status = "connected"
                db.commit()
            else:
                # Create new connection
                connection = ProjectServiceConnection(
                    id=str(uuid4()),
                    project_id=project_id,
                    provider="github",
                    status="connected",
                    service_data=service_data
                )
                db.add(connection)
                db.commit()
                
        except Exception as db_error:
            logger.error(f"Database update failed: {db_error}")
            # Don't fail the operation for database issues
            
        return GitHubConnectResponse(
            success=True,
            repo_url=repo_url,
            message=f"GitHub repository '{request.repo_name}' created and connected successfully!"
        )
        
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e.message}")
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in GitHub connection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect GitHub repository: {str(e)}")


@router.get("/projects/{project_id}/github/status")
async def get_github_connection_status(project_id: str, db: Session = Depends(get_db)):
    """Get GitHub connection status for a project"""
    
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get GitHub connection
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    
    if not connection:
        return {"connected": False, "status": "disconnected"}
    
    return {
        "connected": True,
        "status": connection.status,
        "service_data": connection.service_data or {},
        "created_at": connection.created_at.isoformat(),
        "updated_at": connection.updated_at.isoformat() if connection.updated_at else None
    }


@router.delete("/projects/{project_id}/github/disconnect")
async def disconnect_github_repository(project_id: str, db: Session = Depends(get_db)):
    """Disconnect GitHub repository from project (does not delete the GitHub repo)"""
    
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Find GitHub connection
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    
    if not connection:
        raise HTTPException(status_code=404, detail="GitHub connection not found")
    
    # Remove the connection
    db.delete(connection)
    db.commit()
    
    return {"message": "GitHub repository disconnected successfully"}


@router.post("/projects/{project_id}/github/push", response_model=GitPushResponse)
async def push_github_repository(project_id: str, db: Session = Depends(get_db)):
    """Push current repo to remote origin. Used by Publish/Update in UI."""
    # Check project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Ensure GitHub connected
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub repository not connected")

    # Determine repo path
    repo_path = None
    if project.repo_path and os.path.exists(project.repo_path):
        repo_path = project.repo_path
    elif project.repo_path and os.path.exists(os.path.join(project.repo_path, "repo")):
        repo_path = os.path.join(project.repo_path, "repo")
    else:
        from pathlib import Path
        root_dir = Path(__file__).parent.parent.parent.parent
        candidate = root_dir / "data" / "projects" / project.id / "repo"
        if candidate.exists():
            repo_path = str(candidate.resolve())

    if not repo_path or not os.path.exists(repo_path):
        raise HTTPException(status_code=500, detail="Local repository path not found")

    # Branch
    default_branch = connection.service_data.get("default_branch", "main")

    # Commit any pending changes (optional harmless)
    commit_all(repo_path, "Publish from Lovable UI")

    # Push
    result = push_to_remote(repo_path, "origin", default_branch)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Git push failed: {result.get('error', 'unknown')}")

    # Update metadata on connections for UI (published flag)
    try:
        # Update GitHub connection record
        svc = connection
        data = svc.service_data or {}
        data.update({
            "last_push_at": datetime.utcnow().isoformat() + "Z",
            "last_pushed_branch": default_branch,
        })
        svc.service_data = data
        db.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed updating GitHub connection after push: {e}")

    # If Vercel connected, ensure we store computed deployment URL for convenience
    try:
        vercel_conn = db.query(ProjectServiceConnection).filter(
            ProjectServiceConnection.project_id == project_id,
            ProjectServiceConnection.provider == "vercel"
        ).first()
        if vercel_conn:
            vercel_data = vercel_conn.service_data or {}
            # Don't set deployment_url until actual deployment happens
            vercel_data["last_published_at"] = data.get("last_push_at")
            vercel_conn.service_data = vercel_data
            db.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed updating Vercel connection after push: {e}")

    return GitPushResponse(success=True, message="Pushed to GitHub", branch=default_branch)


@router.get("/projects/{project_id}/github/branches")
async def list_repository_branches(project_id: str, db: Session = Depends(get_db)):
    """List all branches in the connected GitHub repository"""
    
    # Check if project exists and has GitHub connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.list_branches(username, repo_name)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch branches"))
        
        return result["branches"]
        
    except Exception as e:
        logger.error(f"Error listing branches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/github/branches")
async def create_repository_branch(
    project_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """Create a new branch in the GitHub repository"""
    
    branch_name = request.get("branch_name")
    from_branch = request.get("from_branch", "main")
    
    if not branch_name:
        raise HTTPException(status_code=400, detail="Branch name is required")
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.create_branch(username, repo_name, branch_name, from_branch)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to create branch"))
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/github/branches/{branch_name}")
async def delete_repository_branch(
    project_id: str,
    branch_name: str,
    db: Session = Depends(get_db)
):
    """Delete a branch from the GitHub repository"""
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        # Prevent deletion of default branch
        default_branch = service_data.get("default_branch", "main")
        if branch_name == default_branch:
            raise HTTPException(status_code=400, detail="Cannot delete default branch")
        
        result = await github_service.delete_branch(username, repo_name, branch_name)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete branch"))
        
        return result
        
    except Exception as e:
        logger.error(f"Error deleting branch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/github/pull-requests")
async def list_pull_requests(
    project_id: str,
    state: str = "open",
    db: Session = Depends(get_db)
):
    """List pull requests for the connected GitHub repository"""
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.list_pull_requests(username, repo_name, state)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch pull requests"))
        
        return result["pull_requests"]
        
    except Exception as e:
        logger.error(f"Error listing pull requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/github/pull-requests")
async def create_pull_request(
    project_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """Create a pull request in the GitHub repository"""
    
    title = request.get("title")
    head_branch = request.get("head_branch")
    base_branch = request.get("base_branch", "main")
    body = request.get("body", "")
    draft = request.get("draft", False)
    
    if not title or not head_branch:
        raise HTTPException(status_code=400, detail="Title and head branch are required")
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.create_pull_request(
            username, repo_name, title, head_branch, base_branch, body, draft
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to create pull request"))
        
        return result["pull_request"]
        
    except Exception as e:
        logger.error(f"Error creating pull request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/github/issues")
async def list_issues(
    project_id: str,
    state: str = "open",
    db: Session = Depends(get_db)
):
    """List issues for the connected GitHub repository"""
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.list_issues(username, repo_name, state)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch issues"))
        
        return result["issues"]
        
    except Exception as e:
        logger.error(f"Error listing issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/github/issues")
async def create_issue(
    project_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """Create an issue in the GitHub repository"""
    
    title = request.get("title")
    body = request.get("body", "")
    labels = request.get("labels", [])
    
    if not title:
        raise HTTPException(status_code=400, detail="Issue title is required")
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.create_issue(username, repo_name, title, body, labels)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to create issue"))
        
        return result["issue"]
        
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/github/actions")
async def list_workflow_runs(
    project_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """List GitHub Actions workflow runs"""
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.list_workflow_runs(username, repo_name, limit)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch workflow runs"))
        
        return result["workflow_runs"]
        
    except Exception as e:
        logger.error(f"Error listing workflow runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/github/stats")
async def get_repository_stats(project_id: str, db: Session = Depends(get_db)):
    """Get repository statistics and insights"""
    
    # Check project and connection
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    connection = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id,
        ProjectServiceConnection.provider == "github"
    ).first()
    if not connection:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        service_data = connection.service_data or {}
        username = service_data.get("username")
        repo_name = service_data.get("repo_name")
        
        if not username or not repo_name:
            raise HTTPException(status_code=500, detail="GitHub repository information not found")
        
        result = await github_service.get_repository_stats(username, repo_name)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch repository stats"))
        
        return result["stats"]
        
    except Exception as e:
        logger.error(f"Error getting repository stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/search")
async def search_repositories(
    query: str,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """Search for repositories on GitHub"""
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        result = await github_service.search_repositories(query, per_page)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to search repositories"))
        
        return {
            "total_count": result["total_count"],
            "repositories": result["repositories"]
        }
        
    except Exception as e:
        logger.error(f"Error searching repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/debug/token-status")
async def debug_github_token_status(db: Session = Depends(get_db)):
    """Debug endpoint to check GitHub token status"""
    try:
        from app.models.tokens import ServiceToken
        
        token_record = db.query(ServiceToken).filter_by(provider="github").first()
        if not token_record:
            return {
                "token_exists": False,
                "message": "No GitHub token found. Please add your token in Settings."
            }
        
        # Test token with GitHub API
        github_service = GitHubService(token_record.token)
        user_info = await github_service.check_token_validity()
        
        return {
            "token_exists": True,
            "token_length": len(token_record.token),
            "token_valid": user_info.get("valid", False),
            "username": user_info.get("username") if user_info.get("valid") else None,
            "created_at": token_record.created_at.isoformat(),
            "last_used": token_record.last_used.isoformat() if token_record.last_used else None,
            "message": "Token is valid" if user_info.get("valid") else "Token is invalid or expired"
        }
    except Exception as e:
        logger.error(f"Error checking GitHub token status: {e}")
        return {
            "error": str(e)
        }

@router.get("/github/user/repos")
async def get_user_repositories(
    per_page: int = 30,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """Get authenticated user's repositories"""
    
    # Get GitHub token with enhanced error handling
    try:
        from app.models.tokens import ServiceToken
        
        # Check if token exists in database
        token_record = db.query(ServiceToken).filter_by(provider="github").first()
        if not token_record:
            logger.error("No GitHub token found in database")
            raise HTTPException(
                status_code=401, 
                detail="GitHub token not configured. Please add your GitHub token in Settings."
            )
        
        github_token = token_record.token
        if not github_token or not github_token.strip():
            logger.error("GitHub token exists but is empty")
            raise HTTPException(
                status_code=401,
                detail="GitHub token is invalid. Please reconfigure your token in Settings."
            )
            
        logger.info(f"GitHub token retrieved successfully, length: {len(github_token)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving GitHub token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve GitHub token: {str(e)}"
        )
    
    try:
        github_service = GitHubService(github_token)
        result = await github_service.get_user_repositories(per_page, page)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch user repositories"))
        
        # Format repositories for frontend
        repositories = []
        for repo in result["repositories"]:
            repositories.append({
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description", ""),
                "html_url": repo["html_url"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"],
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "language": repo.get("language"),
                "updated_at": repo["updated_at"],
                "owner": {
                    "login": repo["owner"]["login"],
                    "avatar_url": repo["owner"]["avatar_url"]
                },
                "private": repo["private"],
                "default_branch": repo.get("default_branch", "main")
            })
        
        return {
            "repositories": repositories
        }
        
    except Exception as e:
        logger.error(f"Error fetching user repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/github/clone")
async def clone_repository(
    project_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """Clone an existing GitHub repository to a project"""
    
    clone_url = request.get("clone_url")
    repo_name = request.get("repo_name")
    
    if not clone_url or not repo_name:
        raise HTTPException(status_code=400, detail="Clone URL and repository name are required")
    
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get GitHub token
    github_token = get_token(db, "github")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub token not configured")
    
    try:
        github_service = GitHubService(github_token)
        
        # Determine target path
        from pathlib import Path
        root_dir = Path(__file__).parent.parent.parent.parent  # Get to cc-lovable root
        target_path = root_dir / "data" / "projects" / project.id / "repo"
        target_path = str(target_path.resolve())
        
        # Check if directory already exists
        if os.path.exists(target_path):
            raise HTTPException(status_code=409, detail="Project repository directory already exists")
        
        # Clone the repository
        result = await github_service.clone_repository(clone_url, target_path)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to clone repository"))
        
        # Update project repo_path
        project.repo_path = target_path
        
        # Extract repository info from clone URL
        # Example: https://github.com/user/repo.git -> user/repo
        import re
        repo_match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', clone_url)
        if repo_match:
            username = repo_match.group(1)
            repo_name_extracted = repo_match.group(2)
            
            # Get repository info to populate service connection
            repo_info = await github_service.get_repository_info(username, repo_name_extracted)
            
            if repo_info:
                # Update project with repository information
                project.repo_url = repo_info["repo_url"]
                project.repo_name = repo_info["full_name"]  # owner/repo format
                project.repo_default_branch = repo_info["default_branch"]
                project.repo_cloned_at = datetime.utcnow()
                # Create service connection record
                service_data = {
                    "repo_url": repo_info["repo_url"],
                    "repo_name": repo_name_extracted,
                    "clone_url": repo_info["clone_url"],
                    "ssh_url": repo_info["ssh_url"],
                    "default_branch": repo_info["default_branch"],
                    "private": repo_info["private"],
                    "username": username,
                    "full_name": repo_info["full_name"],
                    "repo_id": repo_info["repo_id"],
                    "cloned": True
                }
                
                # Check if connection already exists
                existing_connection = db.query(ProjectServiceConnection).filter(
                    ProjectServiceConnection.project_id == project_id,
                    ProjectServiceConnection.provider == "github"
                ).first()
                
                if existing_connection:
                    existing_connection.service_data = service_data
                    existing_connection.status = "connected"
                else:
                    connection = ProjectServiceConnection(
                        id=str(uuid4()),
                        project_id=project_id,
                        provider="github",
                        status="connected",
                        service_data=service_data
                    )
                    db.add(connection)
                
                db.commit()
        
        return {
            "success": True,
            "message": "Repository cloned successfully",
            "path": target_path,
            "repo_name": repo_name
        }
        
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))