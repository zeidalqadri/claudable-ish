"""
GitHub API service for repository management
"""
import httpx
import json
from typing import Dict, Any, Optional, List
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GitHubService:
    """GitHub API service for repository operations"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Clovable/1.0"
        }
    
    async def check_token_validity(self) -> Dict[str, Any]:
        """Check if the GitHub token is valid and get user info"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/user",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "valid": True,
                        "username": user_data.get("login"),
                        "name": user_data.get("name"),
                        "email": user_data.get("email"),
                        "avatar_url": user_data.get("avatar_url")
                    }
                elif response.status_code == 401:
                    return {"valid": False, "error": "Invalid or expired token"}
                else:
                    return {"valid": False, "error": f"GitHub API error: {response.status_code}"}
                    
            except Exception as e:
                logger.error(f"Error validating GitHub token: {e}")
                return {"valid": False, "error": str(e)}
    
    async def check_repository_exists(self, repo_name: str, username: str) -> bool:
        """Check if a repository exists for the authenticated user"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}",
                    headers=self.headers
                )
                
                return response.status_code == 200
                
            except Exception as e:
                logger.error(f"Error checking repository existence: {e}")
                return False
    
    async def create_repository(
        self, 
        repo_name: str, 
        description: str = "", 
        private: bool = False,
        auto_init: bool = False
    ) -> Dict[str, Any]:
        """Create a new GitHub repository"""
        
        # Get user info first
        user_info = await self.check_token_validity()
        if not user_info.get("valid"):
            raise GitHubAPIError("Invalid GitHub token", 401)
        
        username = user_info["username"]
        
        # Check if repository already exists
        if await self.check_repository_exists(repo_name, username):
            raise GitHubAPIError(f"Repository '{repo_name}' already exists", 409)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "name": repo_name,
                    "description": description,
                    "private": private,
                    "auto_init": auto_init,
                    "homepage": "",
                    "has_issues": True,
                    "has_projects": True,
                    "has_wiki": False,
                    "has_downloads": True
                }
                
                response = await client.post(
                    f"{self.BASE_URL}/user/repos",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    repo_data = response.json()
                    return {
                        "success": True,
                        "repo_url": repo_data["html_url"],
                        "clone_url": repo_data["clone_url"],
                        "ssh_url": repo_data["ssh_url"],
                        "git_url": repo_data["git_url"],
                        "name": repo_data["name"],
                        "full_name": repo_data["full_name"],
                        "repo_id": repo_data["id"],
                        "private": repo_data["private"],
                        "default_branch": repo_data["default_branch"] or "main"
                    }
                elif response.status_code == 422:
                    error_data = response.json()
                    if "errors" in error_data:
                        error_msg = "; ".join([err.get("message", "Unknown error") for err in error_data["errors"]])
                    else:
                        error_msg = error_data.get("message", "Repository creation failed")
                    raise GitHubAPIError(f"Repository creation failed: {error_msg}", 422)
                elif response.status_code == 401:
                    raise GitHubAPIError("GitHub authentication failed", 401)
                elif response.status_code == 403:
                    raise GitHubAPIError("GitHub access denied. Check token permissions", 403)
                else:
                    error_text = response.text
                    raise GitHubAPIError(f"GitHub API error: {response.status_code} - {error_text}", response.status_code)
                    
            except GitHubAPIError:
                raise
            except Exception as e:
                logger.error(f"Error creating GitHub repository: {e}")
                raise GitHubAPIError(f"Failed to create repository: {str(e)}")
    
    async def get_repository_info(self, username: str, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get repository information including repository ID"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    repo_data = response.json()
                    return {
                        "repo_url": repo_data["html_url"],
                        "clone_url": repo_data["clone_url"],
                        "ssh_url": repo_data["ssh_url"],
                        "git_url": repo_data["git_url"],
                        "name": repo_data["name"],
                        "full_name": repo_data["full_name"],
                        "repo_id": repo_data["id"],
                        "private": repo_data["private"],
                        "default_branch": repo_data["default_branch"] or "main"
                    }
                else:
                    return None
                    
            except Exception as e:
                logger.error(f"Error getting repository info: {e}")
                return None
    
    async def clone_repository(self, clone_url: str, target_path: str) -> Dict[str, Any]:
        """Clone a repository from GitHub"""
        import subprocess
        import os
        
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(target_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # Clone the repository
            result = subprocess.run(
                ["git", "clone", clone_url, target_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Repository cloned successfully",
                    "path": target_path
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "Failed to clone repository"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Clone operation timed out"
            }
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_repositories(self, query: str, per_page: int = 20) -> Dict[str, Any]:
        """Search for repositories on GitHub"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/search/repositories",
                    headers=self.headers,
                    params={
                        "q": query,
                        "per_page": per_page,
                        "sort": "stars",
                        "order": "desc"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "total_count": data.get("total_count", 0),
                        "repositories": [
                            {
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
                            }
                            for repo in data.get("items", [])
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"GitHub search failed: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error searching repositories: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_user_repositories(self, per_page: int = 30, page: int = 1) -> Dict[str, Any]:
        """Get user's repositories"""
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Making GitHub API request to {self.BASE_URL}/user/repos")
                logger.info(f"Token present: {bool(self.token)}, Token length: {len(self.token) if self.token else 0}")
                
                response = await client.get(
                    f"{self.BASE_URL}/user/repos",
                    headers=self.headers,
                    params={
                        "per_page": per_page,
                        "page": page,
                        "sort": "updated",
                        "direction": "desc"
                    }
                )
                
                logger.info(f"GitHub API response status: {response.status_code}")
                
                if response.status_code == 200:
                    repos = response.json()
                    logger.info(f"Successfully retrieved {len(repos)} repositories")
                    return {
                        "success": True,
                        "repositories": repos
                    }
                elif response.status_code == 401:
                    logger.error("GitHub API returned 401 Unauthorized - token is invalid")
                    return {
                        "success": False,
                        "error": "GitHub token is invalid or expired. Please reconfigure your token."
                    }
                elif response.status_code == 403:
                    logger.error("GitHub API returned 403 Forbidden - rate limit or scope issue")
                    try:
                        error_details = response.json()
                        return {
                            "success": False,
                            "error": f"GitHub API access forbidden: {error_details.get('message', 'Unknown error')}"
                        }
                    except:
                        return {
                            "success": False,
                            "error": "GitHub API access forbidden. Check token permissions."
                        }
                else:
                    logger.error(f"GitHub API returned unexpected status: {response.status_code}")
                    try:
                        error_details = response.json()
                        return {
                            "success": False,
                            "error": f"GitHub API error {response.status_code}: {error_details.get('message', 'Unknown error')}"
                        }
                    except:
                        return {
                            "success": False,
                            "error": f"GitHub API error: {response.status_code}"
                        }
                    
            except Exception as e:
                logger.error(f"Error getting user repositories: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def list_branches(self, username: str, repo_name: str) -> Dict[str, Any]:
        """List all branches in a repository"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/branches",
                    headers=self.headers,
                    params={"per_page": 100}
                )
                
                if response.status_code == 200:
                    branches = response.json()
                    return {
                        "success": True,
                        "branches": [
                            {
                                "name": branch["name"],
                                "commit_sha": branch["commit"]["sha"],
                                "protected": branch.get("protected", False)
                            }
                            for branch in branches
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch branches: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error listing branches: {e}")
                return {"success": False, "error": str(e)}
    
    async def create_branch(self, username: str, repo_name: str, branch_name: str, from_branch: str = "main") -> Dict[str, Any]:
        """Create a new branch from an existing branch"""
        async with httpx.AsyncClient() as client:
            try:
                # First get the SHA of the source branch
                ref_response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/git/refs/heads/{from_branch}",
                    headers=self.headers
                )
                
                if ref_response.status_code != 200:
                    return {"success": False, "error": f"Source branch '{from_branch}' not found"}
                
                source_sha = ref_response.json()["object"]["sha"]
                
                # Create the new branch
                response = await client.post(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/git/refs",
                    headers=self.headers,
                    json={
                        "ref": f"refs/heads/{branch_name}",
                        "sha": source_sha
                    }
                )
                
                if response.status_code == 201:
                    return {
                        "success": True,
                        "branch_name": branch_name,
                        "sha": source_sha,
                        "message": f"Branch '{branch_name}' created from '{from_branch}'"
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "Failed to create branch")
                    }
            except Exception as e:
                logger.error(f"Error creating branch: {e}")
                return {"success": False, "error": str(e)}
    
    async def delete_branch(self, username: str, repo_name: str, branch_name: str) -> Dict[str, Any]:
        """Delete a branch"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/git/refs/heads/{branch_name}",
                    headers=self.headers
                )
                
                if response.status_code == 204:
                    return {
                        "success": True,
                        "message": f"Branch '{branch_name}' deleted successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to delete branch: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error deleting branch: {e}")
                return {"success": False, "error": str(e)}
    
    async def list_pull_requests(self, username: str, repo_name: str, state: str = "open") -> Dict[str, Any]:
        """List pull requests for a repository"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/pulls",
                    headers=self.headers,
                    params={
                        "state": state,
                        "per_page": 50,
                        "sort": "updated",
                        "direction": "desc"
                    }
                )
                
                if response.status_code == 200:
                    prs = response.json()
                    return {
                        "success": True,
                        "pull_requests": [
                            {
                                "number": pr["number"],
                                "title": pr["title"],
                                "body": pr["body"],
                                "state": pr["state"],
                                "draft": pr.get("draft", False),
                                "head_branch": pr["head"]["ref"],
                                "base_branch": pr["base"]["ref"],
                                "author": pr["user"]["login"],
                                "avatar_url": pr["user"]["avatar_url"],
                                "created_at": pr["created_at"],
                                "updated_at": pr["updated_at"],
                                "merged_at": pr.get("merged_at"),
                                "mergeable": pr.get("mergeable"),
                                "html_url": pr["html_url"],
                                "additions": pr.get("additions", 0),
                                "deletions": pr.get("deletions", 0),
                                "changed_files": pr.get("changed_files", 0),
                                "review_comments": pr.get("review_comments", 0),
                                "comments": pr.get("comments", 0)
                            }
                            for pr in prs
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch pull requests: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error listing pull requests: {e}")
                return {"success": False, "error": str(e)}
    
    async def create_pull_request(
        self, 
        username: str, 
        repo_name: str, 
        title: str, 
        head_branch: str, 
        base_branch: str = "main", 
        body: str = "", 
        draft: bool = False
    ) -> Dict[str, Any]:
        """Create a pull request"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/pulls",
                    headers=self.headers,
                    json={
                        "title": title,
                        "body": body,
                        "head": head_branch,
                        "base": base_branch,
                        "draft": draft
                    }
                )
                
                if response.status_code == 201:
                    pr = response.json()
                    return {
                        "success": True,
                        "pull_request": {
                            "number": pr["number"],
                            "title": pr["title"],
                            "html_url": pr["html_url"],
                            "head_branch": pr["head"]["ref"],
                            "base_branch": pr["base"]["ref"]
                        }
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "Failed to create pull request")
                    }
            except Exception as e:
                logger.error(f"Error creating pull request: {e}")
                return {"success": False, "error": str(e)}
    
    async def list_issues(self, username: str, repo_name: str, state: str = "open") -> Dict[str, Any]:
        """List issues for a repository"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/issues",
                    headers=self.headers,
                    params={
                        "state": state,
                        "per_page": 50,
                        "sort": "updated",
                        "direction": "desc"
                    }
                )
                
                if response.status_code == 200:
                    issues = response.json()
                    # Filter out pull requests (GitHub treats PRs as issues)
                    filtered_issues = [issue for issue in issues if not issue.get("pull_request")]
                    
                    return {
                        "success": True,
                        "issues": [
                            {
                                "number": issue["number"],
                                "title": issue["title"],
                                "body": issue["body"],
                                "state": issue["state"],
                                "author": issue["user"]["login"],
                                "avatar_url": issue["user"]["avatar_url"],
                                "created_at": issue["created_at"],
                                "updated_at": issue["updated_at"],
                                "closed_at": issue.get("closed_at"),
                                "html_url": issue["html_url"],
                                "comments": issue.get("comments", 0),
                                "labels": [
                                    {
                                        "name": label["name"],
                                        "color": label["color"],
                                        "description": label.get("description")
                                    }
                                    for label in issue.get("labels", [])
                                ]
                            }
                            for issue in filtered_issues
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch issues: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error listing issues: {e}")
                return {"success": False, "error": str(e)}
    
    async def create_issue(
        self, 
        username: str, 
        repo_name: str, 
        title: str, 
        body: str = "", 
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new issue"""
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "title": title,
                    "body": body
                }
                if labels:
                    payload["labels"] = labels
                
                response = await client.post(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/issues",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    issue = response.json()
                    return {
                        "success": True,
                        "issue": {
                            "number": issue["number"],
                            "title": issue["title"],
                            "html_url": issue["html_url"],
                            "state": issue["state"]
                        }
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "Failed to create issue")
                    }
            except Exception as e:
                logger.error(f"Error creating issue: {e}")
                return {"success": False, "error": str(e)}
    
    async def list_workflow_runs(self, username: str, repo_name: str, limit: int = 10) -> Dict[str, Any]:
        """List GitHub Actions workflow runs"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/actions/runs",
                    headers=self.headers,
                    params={"per_page": limit}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "workflow_runs": [
                            {
                                "id": run["id"],
                                "name": run.get("name", "Workflow"),
                                "status": run["status"],
                                "conclusion": run.get("conclusion"),
                                "head_branch": run["head_branch"],
                                "head_sha": run["head_sha"][:8],
                                "created_at": run["created_at"],
                                "updated_at": run["updated_at"],
                                "html_url": run["html_url"],
                                "workflow_name": run["workflow_url"].split("/")[-1] if run.get("workflow_url") else "unknown"
                            }
                            for run in data.get("workflow_runs", [])
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch workflow runs: {response.status_code}"
                    }
            except Exception as e:
                logger.error(f"Error listing workflow runs: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_repository_stats(self, username: str, repo_name: str) -> Dict[str, Any]:
        """Get repository statistics and insights"""
        async with httpx.AsyncClient() as client:
            try:
                # Get basic repo info
                repo_response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}",
                    headers=self.headers
                )
                
                if repo_response.status_code != 200:
                    return {"success": False, "error": "Repository not found"}
                
                repo_data = repo_response.json()
                
                # Get contributors
                contributors_response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/contributors",
                    headers=self.headers,
                    params={"per_page": 10}
                )
                
                contributors = []
                if contributors_response.status_code == 200:
                    contributors = [
                        {
                            "login": contrib["login"],
                            "avatar_url": contrib["avatar_url"],
                            "contributions": contrib["contributions"]
                        }
                        for contrib in contributors_response.json()
                    ]
                
                # Get languages
                languages_response = await client.get(
                    f"{self.BASE_URL}/repos/{username}/{repo_name}/languages",
                    headers=self.headers
                )
                
                languages = {}
                if languages_response.status_code == 200:
                    languages = languages_response.json()
                
                return {
                    "success": True,
                    "stats": {
                        "name": repo_data["name"],
                        "description": repo_data.get("description", ""),
                        "stars": repo_data["stargazers_count"],
                        "forks": repo_data["forks_count"],
                        "watchers": repo_data["watchers_count"],
                        "open_issues": repo_data["open_issues_count"],
                        "size_kb": repo_data["size"],
                        "default_branch": repo_data["default_branch"],
                        "created_at": repo_data["created_at"],
                        "updated_at": repo_data["updated_at"],
                        "pushed_at": repo_data["pushed_at"],
                        "license": repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
                        "topics": repo_data.get("topics", []),
                        "contributors": contributors,
                        "languages": languages
                    }
                }
            except Exception as e:
                logger.error(f"Error getting repository stats: {e}")
                return {"success": False, "error": str(e)}


# Utility functions
async def validate_github_token(token: str) -> Dict[str, Any]:
    """Validate a GitHub token and return user info"""
    github_service = GitHubService(token)
    return await github_service.check_token_validity()


async def check_repo_availability(token: str, repo_name: str) -> Dict[str, Any]:
    """Check if a repository name is available"""
    github_service = GitHubService(token)
    
    # First validate token and get username
    user_info = await github_service.check_token_validity()
    if not user_info.get("valid"):
        return {"available": False, "error": "Invalid GitHub token"}
    
    username = user_info["username"]
    exists = await github_service.check_repository_exists(repo_name, username)
    
    return {
        "available": not exists,
        "exists": exists,
        "username": username
    }


