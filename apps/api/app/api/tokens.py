"""
Service tokens API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.api.deps import get_db
from app.services.token_service import (
    save_service_token,
    get_service_token,
    delete_service_token,
    get_token,
    update_last_used
)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])

class TokenCreate(BaseModel):
    provider: str  # github, supabase, vercel
    token: str
    name: str

class TokenResponse(BaseModel):
    id: str
    provider: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None

def validate_github_token(token: str) -> tuple[bool, str]:
    """Validate GitHub token format and clean it"""
    import re
    
    # Clean the token - remove any extra information after @
    clean_token = token.split('@')[0].strip()
    
    # GitHub token patterns
    classic_pattern = r'^[a-f0-9]{40}$'  # Classic tokens: 40 hex chars
    new_pattern = r'^ghp_[a-zA-Z0-9]{36}$'  # New tokens: ghp_ prefix + 36 chars
    
    is_valid = bool(re.match(classic_pattern, clean_token) or re.match(new_pattern, clean_token))
    return is_valid, clean_token

@router.post("/", response_model=TokenResponse)
async def create_token(body: TokenCreate, db: Session = Depends(get_db)):
    """Save a new service token"""
    if body.provider not in ['github', 'supabase', 'vercel']:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    if not body.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")
    
    # Validate GitHub token format
    if body.provider == "github":
        is_valid, clean_token = validate_github_token(body.token)
        if not is_valid:
            raise HTTPException(
                status_code=400, 
                detail="Invalid GitHub token format. Expected format: ghp_xxxx... or 40 hex characters"
            )
        body.token = clean_token
    
    try:
        service_token = save_service_token(
            db=db,
            provider=body.provider,
            token=body.token.strip(),
            name=body.name.strip() or f"{body.provider.capitalize()} Token"
        )
        
        return TokenResponse(
            id=service_token.id,
            provider=service_token.provider,
            name=service_token.name,
            created_at=service_token.created_at,
            last_used=service_token.last_used
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save token: {str(e)}")

@router.get("/{provider}", response_model=TokenResponse)
async def get_token(provider: str, db: Session = Depends(get_db)):
    """Get service token by provider"""
    if provider not in ['github', 'supabase', 'vercel']:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    service_token = get_service_token(db, provider)
    if not service_token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    return TokenResponse(
        id=service_token.id,
        provider=service_token.provider,
        name=service_token.name,
        created_at=service_token.created_at,
        last_used=service_token.last_used
    )

@router.delete("/{token_id}")
async def delete_token(token_id: str, db: Session = Depends(get_db)):
    """Delete a service token"""
    success = delete_service_token(db, token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    
    return {"message": "Token deleted successfully"}

# Internal API for getting tokens (used by service integrations)
@router.get("/internal/{provider}/token")
async def get_token_internal(provider: str, db: Session = Depends(get_db)):
    """Get token for internal use (used by service integrations)"""
    if provider not in ['github', 'supabase', 'vercel']:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    token = get_token(db, provider)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # Update last used
    update_last_used(db, provider)
    
    return {"token": token}