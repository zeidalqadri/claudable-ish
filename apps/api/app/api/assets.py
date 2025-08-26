from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import base64
import uuid
from datetime import datetime
from typing import Optional
from app.api.deps import get_db
from app.core.config import settings
from app.models.projects import Project as ProjectModel
# from app.models.file_metadata import FileMetadata  # Removed - using simple context passing instead
from app.services.assets import write_bytes
from app.services.file_processor import extract_text_from_pdf
# from app.services.file_processor import process_pdf, generate_thumbnail, validate_pdf_integrity  # Complex processing not needed for context

router = APIRouter(prefix="/api/assets", tags=["assets"]) 


class LogoRequest(BaseModel):
    b64_png: str  # Accept base64-encoded PNG (fallback if no OpenAI key)


@router.post("/{project_id}/logo")
async def upload_logo(project_id: str, body: LogoRequest, db: Session = Depends(get_db)):
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    project_assets = os.path.join(settings.projects_root, project_id, "assets")
    data = base64.b64decode(body.b64_png)
    logo_path = os.path.join(project_assets, "logo.png")
    write_bytes(logo_path, data)
    return {"path": f"assets/logo.png"}


@router.post("/{project_id}/upload")
async def upload_file(project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a file (image or PDF) to project assets directory"""
    print(f"📤 File upload request: project_id={project_id}, filename={file.filename}")
    
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        print(f"❌ Project not found: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check supported file types
    print(f"📁 File info: content_type={file.content_type}, size={file.size}")
    supported_types = ['image/', 'application/pdf']
    is_supported = any(file.content_type and file.content_type.startswith(file_type) for file_type in supported_types)
    
    if not is_supported:
        print(f"❌ Invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="File must be an image (JPG, PNG, GIF, WEBP) or PDF")
    
    # File size limit (500MB for PDFs, 50MB for images)
    max_size = 500 * 1024 * 1024 if file.content_type == 'application/pdf' else 50 * 1024 * 1024
    if file.size and file.size > max_size:
        size_mb = max_size // (1024 * 1024)
        file_type = "PDF" if file.content_type == 'application/pdf' else "image"
        raise HTTPException(status_code=413, detail=f"{file_type} file size must be less than {size_mb}MB")
    
    # Create assets directory if it doesn't exist
    project_assets = os.path.join(settings.projects_root, project_id, "assets")
    print(f"📁 Assets directory: {project_assets}")
    os.makedirs(project_assets, exist_ok=True)
    
    # Generate unique filename to avoid conflicts
    file_extension = os.path.splitext(file.filename or 'file')[1]
    if not file_extension:
        file_extension = '.pdf' if file.content_type == 'application/pdf' else '.png'
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(project_assets, unique_filename)
    print(f"💾 Saving to: {file_path}")
    
    try:
        # Save file
        content = await file.read()
        write_bytes(file_path, content)
        print(f"✅ File saved successfully: {len(content)} bytes")
        
        # Create file metadata record
        file_id = str(uuid.uuid4())
        file_type = "pdf" if file.content_type == 'application/pdf' else "image"
        
        # Validate PDF integrity if it's a PDF
        is_valid = True
        validation_error = None
        if file.content_type == 'application/pdf':
            is_valid = validate_pdf_integrity(file_path)
            if not is_valid:
                validation_error = "PDF file appears to be corrupted or invalid"
        
        file_metadata = FileMetadata(
            id=file_id,
            project_id=project_id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=f"assets/{unique_filename}",
            absolute_path=file_path,
            file_type=file_type,
            mime_type=file.content_type,
            file_extension=file_extension,
            size_bytes=len(content),
            processing_status="pending" if file.content_type == 'application/pdf' else "completed",
            is_validated=is_valid,
            validation_error=validation_error,
            uploaded_at=datetime.utcnow()
        )
        
        # Save to database
        db.add(file_metadata)
        db.commit()
        db.refresh(file_metadata)
        
        result = {
            "id": file_id,
            "path": f"assets/{unique_filename}",
            "absolute_path": file_path,
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_type": file_type,
            "size_bytes": len(content),
            "is_validated": is_valid,
            "validation_error": validation_error
        }
        
        # Process PDF if it's a PDF file
        if file.content_type == 'application/pdf' and is_valid:
            try:
                # Update status to processing
                file_metadata.processing_status = "processing"
                db.commit()
                
                pdf_metadata = await process_pdf(file_path, project_assets)
                
                # Update database with PDF metadata
                file_metadata.processing_status = "completed"
                file_metadata.processed_at = datetime.utcnow()
                file_metadata.text_content = pdf_metadata.get("text_content", "")
                file_metadata.text_content_preview = pdf_metadata.get("text_content", "")[:500] if pdf_metadata.get("text_content") else None
                file_metadata.page_count = pdf_metadata.get("page_count", 0)
                file_metadata.pdf_title = pdf_metadata.get("title", "")
                file_metadata.pdf_author = pdf_metadata.get("author", "")
                file_metadata.thumbnail_path = pdf_metadata.get("thumbnail_path")
                file_metadata.preview_available = bool(pdf_metadata.get("thumbnail_path"))
                
                db.commit()
                
                result.update(pdf_metadata)
                print(f"✅ PDF processed: {pdf_metadata}")
                
            except Exception as e:
                print(f"⚠️ PDF processing failed (file still saved): {e}")
                file_metadata.processing_status = "failed"
                file_metadata.processing_error = str(e)
                file_metadata.processed_at = datetime.utcnow()
                db.commit()
                result["processing_error"] = str(e)
        
        return result
        
    except Exception as e:
        print(f"❌ Failed to save file: {e}")
        # Clean up file if it was partially created
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.get("/{project_id}/files")
async def list_project_files(project_id: str, db: Session = Depends(get_db)):
    """List all uploaded files for a project"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all files for this project
    files = db.query(FileMetadata).filter(FileMetadata.project_id == project_id).order_by(FileMetadata.uploaded_at.desc()).all()
    
    return {
        "project_id": project_id,
        "total_files": len(files),
        "files": [file.to_dict() for file in files]
    }


@router.get("/{project_id}/files/{file_id}")
async def get_file_metadata(project_id: str, file_id: str, db: Session = Depends(get_db)):
    """Get metadata for a specific file"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get file metadata
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.project_id == project_id,
        FileMetadata.id == file_id
    ).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    return file_metadata.to_dict()


@router.delete("/{project_id}/files/{file_id}")
async def delete_file(project_id: str, file_id: str, db: Session = Depends(get_db)):
    """Delete a file and its metadata"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get file metadata
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.project_id == project_id,
        FileMetadata.id == file_id
    ).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Delete physical files
        if os.path.exists(file_metadata.absolute_path):
            os.remove(file_metadata.absolute_path)
            print(f"🗑️ Deleted file: {file_metadata.absolute_path}")
        
        # Delete thumbnail if it exists
        if file_metadata.thumbnail_path:
            thumbnail_abs_path = os.path.join(settings.projects_root, project_id, file_metadata.thumbnail_path)
            if os.path.exists(thumbnail_abs_path):
                os.remove(thumbnail_abs_path)
                print(f"🗑️ Deleted thumbnail: {thumbnail_abs_path}")
        
        # Delete from database
        db.delete(file_metadata)
        db.commit()
        
        return {
            "message": "File deleted successfully",
            "file_id": file_id,
            "filename": file_metadata.filename
        }
        
    except Exception as e:
        print(f"❌ Failed to delete file: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


class ChunkUploadRequest(BaseModel):
    chunk_index: int
    total_chunks: int
    file_id: str
    original_filename: str
    file_type: str
    total_size: int


@router.post("/{project_id}/upload/chunked/init")
async def init_chunked_upload(project_id: str, body: ChunkUploadRequest, db: Session = Depends(get_db)):
    """Initialize chunked upload session"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create temporary directory for chunks
    project_assets = os.path.join(settings.projects_root, project_id, "assets")
    temp_dir = os.path.join(project_assets, "temp", body.file_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create placeholder file metadata
    file_metadata = FileMetadata(
        id=body.file_id,
        project_id=project_id,
        filename=f"temp_{body.file_id}",
        original_filename=body.original_filename,
        file_path="",  # Will be set after upload completes
        absolute_path="",  # Will be set after upload completes
        file_type=body.file_type,
        size_bytes=body.total_size,
        processing_status="uploading",
        uploaded_at=datetime.utcnow()
    )
    
    db.add(file_metadata)
    db.commit()
    
    return {
        "file_id": body.file_id,
        "upload_session_created": True,
        "chunk_size": 5 * 1024 * 1024,  # 5MB chunks
        "total_chunks": body.total_chunks
    }


@router.post("/{project_id}/upload/chunked/{file_id}/chunk/{chunk_index}")
async def upload_chunk(
    project_id: str, 
    file_id: str, 
    chunk_index: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a single chunk"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get file metadata
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.project_id == project_id,
        FileMetadata.id == file_id
    ).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    if file_metadata.processing_status != "uploading":
        raise HTTPException(status_code=400, detail="Upload session is not active")
    
    try:
        # Save chunk
        project_assets = os.path.join(settings.projects_root, project_id, "assets")
        temp_dir = os.path.join(project_assets, "temp", file_id)
        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index:04d}")
        
        content = await file.read()
        write_bytes(chunk_path, content)
        
        print(f"✅ Saved chunk {chunk_index} for file {file_id}: {len(content)} bytes")
        
        return {
            "chunk_index": chunk_index,
            "chunk_size": len(content),
            "status": "uploaded"
        }
        
    except Exception as e:
        print(f"❌ Failed to save chunk {chunk_index}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {str(e)}")


@router.post("/{project_id}/upload/chunked/{file_id}/complete")
async def complete_chunked_upload(project_id: str, file_id: str, db: Session = Depends(get_db)):
    """Complete chunked upload by combining all chunks"""
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get file metadata
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.project_id == project_id,
        FileMetadata.id == file_id
    ).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    if file_metadata.processing_status != "uploading":
        raise HTTPException(status_code=400, detail="Upload session is not active")
    
    try:
        project_assets = os.path.join(settings.projects_root, project_id, "assets")
        temp_dir = os.path.join(project_assets, "temp", file_id)
        
        # Get file extension
        file_extension = os.path.splitext(file_metadata.original_filename or 'file')[1]
        if not file_extension:
            file_extension = '.pdf' if file_metadata.file_type == 'pdf' else '.bin'
        
        # Generate final filename
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        final_path = os.path.join(project_assets, unique_filename)
        
        # Combine chunks
        chunk_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('chunk_')])
        
        with open(final_path, 'wb') as final_file:
            for chunk_file in chunk_files:
                chunk_path = os.path.join(temp_dir, chunk_file)
                with open(chunk_path, 'rb') as chunk:
                    final_file.write(chunk.read())
        
        # Clean up chunks
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Update file metadata
        file_metadata.filename = unique_filename
        file_metadata.file_path = f"assets/{unique_filename}"
        file_metadata.absolute_path = final_path
        file_metadata.processing_status = "pending" if file_metadata.file_type == 'pdf' else "completed"
        
        # Validate file size
        actual_size = os.path.getsize(final_path)
        if abs(actual_size - file_metadata.size_bytes) > 1024:  # Allow 1KB difference
            print(f"⚠️ Size mismatch: expected {file_metadata.size_bytes}, got {actual_size}")
        
        file_metadata.size_bytes = actual_size
        
        # Validate PDF integrity if it's a PDF
        is_valid = True
        validation_error = None
        if file_metadata.file_type == 'pdf':
            is_valid = validate_pdf_integrity(final_path)
            if not is_valid:
                validation_error = "PDF file appears to be corrupted or invalid"
        
        file_metadata.is_validated = is_valid
        file_metadata.validation_error = validation_error
        
        db.commit()
        
        result = {
            "id": file_id,
            "path": f"assets/{unique_filename}",
            "absolute_path": final_path,
            "filename": unique_filename,
            "original_filename": file_metadata.original_filename,
            "file_type": file_metadata.file_type,
            "size_bytes": actual_size,
            "is_validated": is_valid,
            "validation_error": validation_error,
            "upload_complete": True
        }
        
        # Process PDF if it's a valid PDF file
        if file_metadata.file_type == 'pdf' and is_valid:
            try:
                # Update status to processing
                file_metadata.processing_status = "processing"
                db.commit()
                
                pdf_metadata = await process_pdf(final_path, project_assets)
                
                # Update database with PDF metadata
                file_metadata.processing_status = "completed"
                file_metadata.processed_at = datetime.utcnow()
                file_metadata.text_content = pdf_metadata.get("text_content", "")
                file_metadata.text_content_preview = pdf_metadata.get("text_content", "")[:500] if pdf_metadata.get("text_content") else None
                file_metadata.page_count = pdf_metadata.get("page_count", 0)
                file_metadata.pdf_title = pdf_metadata.get("title", "")
                file_metadata.pdf_author = pdf_metadata.get("author", "")
                file_metadata.thumbnail_path = pdf_metadata.get("thumbnail_path")
                file_metadata.preview_available = bool(pdf_metadata.get("thumbnail_path"))
                
                db.commit()
                
                result.update(pdf_metadata)
                print(f"✅ PDF processed: {pdf_metadata}")
                
            except Exception as e:
                print(f"⚠️ PDF processing failed (file still saved): {e}")
                file_metadata.processing_status = "failed"
                file_metadata.processing_error = str(e)
                file_metadata.processed_at = datetime.utcnow()
                db.commit()
                result["processing_error"] = str(e)
        
        print(f"✅ Chunked upload completed: {unique_filename} ({actual_size} bytes)")
        return result
        
    except Exception as e:
        print(f"❌ Failed to complete chunked upload: {e}")
        file_metadata.processing_status = "failed"
        file_metadata.processing_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(e)}")


@router.post("/extract-text")
async def extract_text_from_uploaded_file(file: UploadFile = File(...)):
    """Simple text extraction from PDF for document context (no storage)"""
    try:
        # Check if it's a PDF
        if file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # File size limit (50MB)
        if file.size and file.size > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF file size must be less than 50MB")
        
        # Read file content
        content = await file.read()
        
        # Extract text using the simplified processor
        text = await extract_text_from_pdf(content, file.filename or "document.pdf")
        
        return {
            "filename": file.filename,
            "text": text,
            "size_bytes": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Text extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract text from PDF: {str(e)}")
