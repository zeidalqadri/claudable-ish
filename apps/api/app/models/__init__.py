# Import all models to ensure they are registered with the metadata
from app.models.projects import Project
from app.models.messages import Message
from app.models.sessions import Session
from app.models.tools import ToolUsage
from app.models.commits import Commit
from app.models.env_vars import EnvVar
from app.models.tokens import ServiceToken
from app.models.project_services import ProjectServiceConnection
from app.models.user_requests import UserRequest
from app.models.worktree_sessions import WorktreeSession
# from app.models.file_metadata import FileMetadata  # Removed - using simple context passing instead


__all__ = [
    "Project",
    "Message",
    "Session",
    "ToolUsage",
    "Commit",
    "EnvVar",
    "ServiceToken",
    "ProjectServiceConnection",
    "UserRequest",
    "WorktreeSession",
    # "FileMetadata",  # Removed - using simple context passing instead
]
