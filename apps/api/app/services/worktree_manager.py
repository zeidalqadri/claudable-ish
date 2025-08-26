"""
Git Worktree Manager
Handles creation, management, and cleanup of git worktrees for isolated AI sessions
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from .water_names import generate_branch_name, extract_water_name_from_branch, get_water_info


logger = logging.getLogger(__name__)


class WorktreeError(Exception):
    """Custom exception for worktree operations"""
    pass


class WorktreeSession:
    """Represents an active worktree session"""
    def __init__(
        self,
        session_id: str,
        branch_name: str,
        worktree_path: str,
        water_name: str,
        project_path: str,
        status: str = "active"
    ):
        self.session_id = session_id
        self.branch_name = branch_name
        self.worktree_path = worktree_path
        self.water_name = water_name
        self.project_path = project_path
        self.status = status
        self.created_at = datetime.now()
        
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        water_info = get_water_info(self.water_name)
        return {
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "worktree_path": self.worktree_path,
            "water_name": self.water_name,
            "water_display": water_info["display_name"],
            "water_emoji": water_info["emoji"],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "exists": os.path.exists(self.worktree_path)
        }


class WorktreeManager:
    """Manages git worktrees for AI sessions"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.worktrees_dir = self.project_path / ".claudable-worktrees"
        self.sessions: Dict[str, WorktreeSession] = {}
        
        # Ensure worktrees directory exists
        self.worktrees_dir.mkdir(exist_ok=True)
        
        # Load existing worktrees
        self._load_existing_worktrees()
        
    def _run_git_command(self, args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """
        Run a git command and return (returncode, stdout, stderr)
        
        Args:
            args: Git command arguments
            cwd: Working directory for the command
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if cwd is None:
            cwd = str(self.project_path)
            
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except Exception as e:
            return -1, "", f"Error running git command: {str(e)}"
    
    def _load_existing_worktrees(self):
        """Load information about existing worktrees from git"""
        returncode, stdout, stderr = self._run_git_command(["worktree", "list", "--porcelain"])
        
        if returncode != 0:
            logger.warning(f"Failed to list worktrees: {stderr}")
            return
            
        # Parse worktree list output
        current_worktree = {}
        for line in stdout.split('\n'):
            if not line.strip():
                if current_worktree.get('worktree'):
                    self._process_existing_worktree(current_worktree)
                current_worktree = {}
                continue
                
            if line.startswith('worktree '):
                current_worktree['worktree'] = line[9:]
            elif line.startswith('branch '):
                current_worktree['branch'] = line[7:]
            elif line == 'bare':
                current_worktree['bare'] = True
            elif line == 'detached':
                current_worktree['detached'] = True
                
        # Process last worktree if exists
        if current_worktree.get('worktree'):
            self._process_existing_worktree(current_worktree)
    
    def _process_existing_worktree(self, worktree_info: dict):
        """Process a single existing worktree"""
        worktree_path = worktree_info.get('worktree')
        branch_name = worktree_info.get('branch', '')
        
        # Skip main/master worktrees
        if not branch_name.startswith('refs/heads/ai/'):
            return
            
        # Extract branch name without refs/heads/ prefix
        branch_name = branch_name.replace('refs/heads/', '')
        water_name = extract_water_name_from_branch(branch_name)
        
        if not water_name:
            return
            
        # Create session from existing worktree
        # Use branch name as session ID for now
        session_id = branch_name.replace('ai/', '').replace('-', '_')
        
        session = WorktreeSession(
            session_id=session_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            water_name=water_name,
            project_path=str(self.project_path),
            status="active"
        )
        
        self.sessions[session_id] = session
    
    def create_worktree(self, session_id: str, base_branch: str = "main") -> WorktreeSession:
        """
        Create a new worktree for an AI session
        
        Args:
            session_id: Unique session identifier
            base_branch: Base branch to branch from (default: main)
            
        Returns:
            WorktreeSession object
            
        Raises:
            WorktreeError: If worktree creation fails
        """
        # Get existing water names to avoid duplicates
        existing_names = [session.water_name for session in self.sessions.values()]
        
        # Generate branch name with water theme
        branch_name = generate_branch_name(session_id, exclude_names=existing_names)
        water_name = extract_water_name_from_branch(branch_name)
        
        # Create worktree path
        worktree_path = self.worktrees_dir / session_id
        
        # Ensure we're on a clean state
        if worktree_path.exists():
            shutil.rmtree(worktree_path)
            
        # Create the worktree
        returncode, stdout, stderr = self._run_git_command([
            "worktree", "add",
            str(worktree_path),
            "-b", branch_name,
            base_branch
        ])
        
        if returncode != 0:
            raise WorktreeError(f"Failed to create worktree: {stderr}")
            
        # Create session object
        session = WorktreeSession(
            session_id=session_id,
            branch_name=branch_name,
            worktree_path=str(worktree_path),
            water_name=water_name,
            project_path=str(self.project_path)
        )
        
        self.sessions[session_id] = session
        
        logger.info(f"Created worktree {branch_name} at {worktree_path}")
        return session
    
    def get_session(self, session_id: str) -> Optional[WorktreeSession]:
        """Get a worktree session by ID"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[WorktreeSession]:
        """List all active worktree sessions"""
        return list(self.sessions.values())
    
    def get_session_changes(self, session_id: str) -> Dict[str, List[str]]:
        """
        Get changes in a worktree session compared to main branch
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with modified, added, deleted files
            
        Raises:
            WorktreeError: If session not found or git operation fails
        """
        session = self.get_session(session_id)
        if not session:
            raise WorktreeError(f"Session {session_id} not found")
            
        # Get diff between session branch and main
        returncode, stdout, stderr = self._run_git_command([
            "diff", "--name-status", "main", session.branch_name
        ])
        
        if returncode != 0:
            raise WorktreeError(f"Failed to get diff: {stderr}")
            
        changes = {"modified": [], "added": [], "deleted": []}
        
        for line in stdout.split('\n'):
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) < 2:
                continue
                
            status = parts[0]
            filepath = parts[1]
            
            if status == 'M':
                changes["modified"].append(filepath)
            elif status == 'A':
                changes["added"].append(filepath)
            elif status == 'D':
                changes["deleted"].append(filepath)
            elif status.startswith('R'):  # Renamed
                changes["modified"].append(filepath)
                
        return changes
    
    def get_session_diff(self, session_id: str, file_path: Optional[str] = None) -> str:
        """
        Get detailed diff for a session
        
        Args:
            session_id: Session identifier
            file_path: Specific file to diff (optional)
            
        Returns:
            Diff output as string
            
        Raises:
            WorktreeError: If session not found or git operation fails
        """
        session = self.get_session(session_id)
        if not session:
            raise WorktreeError(f"Session {session_id} not found")
            
        args = ["diff", "main", session.branch_name]
        if file_path:
            args.append(file_path)
            
        returncode, stdout, stderr = self._run_git_command(args)
        
        if returncode != 0:
            raise WorktreeError(f"Failed to get diff: {stderr}")
            
        return stdout
    
    def merge_session(self, session_id: str, target_branch: str = "main") -> bool:
        """
        Merge a worktree session back to target branch
        
        Args:
            session_id: Session identifier
            target_branch: Target branch to merge into
            
        Returns:
            True if merge successful
            
        Raises:
            WorktreeError: If merge fails
        """
        session = self.get_session(session_id)
        if not session:
            raise WorktreeError(f"Session {session_id} not found")
            
        # Switch to target branch
        returncode, stdout, stderr = self._run_git_command(["checkout", target_branch])
        if returncode != 0:
            raise WorktreeError(f"Failed to checkout {target_branch}: {stderr}")
            
        # Merge the session branch
        returncode, stdout, stderr = self._run_git_command(["merge", session.branch_name])
        if returncode != 0:
            raise WorktreeError(f"Failed to merge {session.branch_name}: {stderr}")
            
        # Update session status
        session.status = "merged"
        
        logger.info(f"Merged {session.branch_name} into {target_branch}")
        return True
    
    def discard_session(self, session_id: str, cleanup_worktree: bool = True) -> bool:
        """
        Discard a worktree session
        
        Args:
            session_id: Session identifier
            cleanup_worktree: Whether to remove the worktree directory
            
        Returns:
            True if discard successful
        """
        session = self.get_session(session_id)
        if not session:
            return False
            
        # Remove worktree
        if cleanup_worktree:
            returncode, stdout, stderr = self._run_git_command([
                "worktree", "remove", session.worktree_path, "--force"
            ])
            if returncode != 0:
                logger.warning(f"Failed to remove worktree: {stderr}")
                # Try to remove directory manually
                try:
                    shutil.rmtree(session.worktree_path)
                except Exception as e:
                    logger.warning(f"Failed to manually remove worktree directory: {e}")
        
        # Delete branch
        returncode, stdout, stderr = self._run_git_command([
            "branch", "-D", session.branch_name
        ])
        if returncode != 0:
            logger.warning(f"Failed to delete branch {session.branch_name}: {stderr}")
            
        # Remove from sessions
        session.status = "discarded"
        if session_id in self.sessions:
            del self.sessions[session_id]
            
        logger.info(f"Discarded session {session_id} ({session.branch_name})")
        return True
    
    def cleanup_stale_worktrees(self) -> int:
        """
        Clean up stale/orphaned worktrees
        
        Returns:
            Number of worktrees cleaned up
        """
        cleaned_count = 0
        
        # Get list from git worktree
        returncode, stdout, stderr = self._run_git_command(["worktree", "list", "--porcelain"])
        if returncode != 0:
            logger.error(f"Failed to list worktrees: {stderr}")
            return 0
            
        # Find worktrees that should be cleaned up
        stale_sessions = []
        for session_id, session in self.sessions.items():
            if not os.path.exists(session.worktree_path):
                stale_sessions.append(session_id)
                
        # Clean up stale sessions
        for session_id in stale_sessions:
            if self.discard_session(session_id, cleanup_worktree=False):
                cleaned_count += 1
                
        return cleaned_count


def get_project_worktree_manager(project_path: str) -> WorktreeManager:
    """
    Get a WorktreeManager instance for a project
    
    Args:
        project_path: Path to the project repository
        
    Returns:
        WorktreeManager instance
    """
    return WorktreeManager(project_path)