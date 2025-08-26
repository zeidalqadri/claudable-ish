"use client";

import { useState, useRef, useEffect } from 'react';
import { SendHorizontal, MessageSquare, Image, Wrench, ClipboardList, FileText, Paperclip } from 'lucide-react';
import { ChatMode } from '@/types/chat';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8080';

interface AttachedDocument {
  id: string;
  name: string;
  content: string;
  type: 'pdf' | 'text';
  size: number;
}

interface AttachedImage {
  id: string;
  name: string;
  data: string; // base64
  url: string; // blob URL for preview
}

interface ChatInputProps {
  onSendMessage: (message: string, images?: AttachedImage[], documents?: AttachedDocument[]) => void;
  disabled?: boolean;
  placeholder?: string;
  mode?: ChatMode;
  onModeChange?: (mode: ChatMode) => void;
  projectId?: string;
  preferredCli?: string;
  thinkingMode?: boolean;
  onThinkingModeChange?: (enabled: boolean) => void;
}

export default function ChatInput({ 
  onSendMessage, 
  disabled = false, 
  placeholder = "Ask Claudable...",
  mode = 'act',
  onModeChange,
  projectId,
  preferredCli = 'claude',
  thinkingMode = false,
  onThinkingModeChange
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [attachedDocuments, setAttachedDocuments] = useState<AttachedDocument[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((message.trim() || attachedImages.length > 0 || attachedDocuments.length > 0) && !disabled) {
      // Send message with attached files as context
      onSendMessage(message.trim(), attachedImages, attachedDocuments);
      
      // Clear form
      setMessage('');
      setAttachedImages([]);
      setAttachedDocuments([]);
      if (textareaRef.current) {
        textareaRef.current.style.height = '40px';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = '40px';
      const scrollHeight = textarea.scrollHeight;
      textarea.style.height = `${Math.min(scrollHeight, 200)}px`;
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    
    await handleFiles(files);
  };

  const removeImage = (id: string) => {
    setAttachedImages(prev => {
      const imageToRemove = prev.find(img => img.id === id);
      if (imageToRemove && imageToRemove.url.startsWith('blob:')) {
        URL.revokeObjectURL(imageToRemove.url);
      }
      return prev.filter(img => img.id !== id);
    });
  };

  const removeDocument = (id: string) => {
    setAttachedDocuments(prev => prev.filter(doc => doc.id !== id));
  };

  // Handle files (for both drag drop and file input)
  const handleFiles = async (files: FileList) => {
    if (preferredCli === 'cursor') return;
    
    setIsProcessing(true);
    
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Check if file is supported
        const isImage = file.type.startsWith('image/');
        const isPDF = file.type === 'application/pdf';
        const isText = file.type.startsWith('text/');
        
        if (!isImage && !isPDF && !isText) {
          alert(`File "${file.name}" is not supported. Please upload images, PDFs, or text files.`);
          continue;
        }

        // File size validation (50MB limit)
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
          alert(`File "${file.name}" is too large. Maximum size is 50MB.`);
          continue;
        }

        if (isImage) {
          await processImageFile(file);
        } else if (isPDF || isText) {
          await processDocumentFile(file);
        }
      }
    } catch (error) {
      console.error('File processing failed:', error);
      alert('Failed to process file. Please try again.');
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Process image files for preview
  const processImageFile = async (file: File) => {
    try {
      const reader = new FileReader();
      const imageUrl = URL.createObjectURL(file);
      
      reader.onload = (e) => {
        const result = e.target?.result;
        if (typeof result === 'string') {
          const base64Data = result.split(',')[1]; // Remove data:image/...;base64, prefix
          
          const newImage: AttachedImage = {
            id: crypto.randomUUID(),
            name: file.name,
            data: base64Data,
            url: imageUrl
          };
          
          setAttachedImages(prev => [...prev, newImage]);
        }
      };
      
      reader.readAsDataURL(file);
    } catch (error) {
      console.error('Failed to process image:', error);
      alert(`Failed to process image "${file.name}".`);
    }
  };

  // Process document files by extracting text
  const processDocumentFile = async (file: File) => {
    try {
      let content = '';
      
      if (file.type === 'application/pdf') {
        content = await extractTextFromPDF(file);
      } else if (file.type.startsWith('text/')) {
        content = await extractTextFromTextFile(file);
      }
      
      if (content.trim()) {
        const newDocument: AttachedDocument = {
          id: crypto.randomUUID(),
          name: file.name,
          content: content,
          type: file.type === 'application/pdf' ? 'pdf' : 'text',
          size: file.size
        };
        
        setAttachedDocuments(prev => [...prev, newDocument]);
      } else {
        alert(`No text content could be extracted from "${file.name}".`);
      }
    } catch (error) {
      console.error('Failed to process document:', error);
      alert(`Failed to process document "${file.name}".`);
    }
  };

  // Extract text from PDF using browser-based PDF.js
  const extractTextFromPDF = async (file: File): Promise<string> => {
    try {
      // For now, we'll make a simple API call to extract text
      // This avoids the complexity of loading PDF.js in the browser
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE}/api/assets/extract-text`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`PDF extraction failed: ${response.status}`);
      }

      const result = await response.json();
      return result.text || '';
    } catch (error) {
      console.error('PDF text extraction failed:', error);
      return `[PDF file "${file.name}" attached but text extraction failed]`;
    }
  };

  // Extract text from text files
  const extractTextFromTextFile = async (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const result = e.target?.result;
        if (typeof result === 'string') {
          // Truncate if too long (50,000 characters max)
          const maxLength = 50000;
          let text = result;
          if (text.length > maxLength) {
            text = text.substring(0, maxLength) + '\n\n[Content truncated for length...]';
          }
          resolve(text);
        } else {
          reject(new Error('Failed to read text file'));
        }
      };
      
      reader.onerror = () => reject(new Error('Failed to read text file'));
      reader.readAsText(file);
    });
  };


  // Drag and drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (preferredCli !== 'cursor') {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set to false if we're leaving the container completely
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (preferredCli !== 'cursor') {
      e.dataTransfer.dropEffect = 'copy';
    } else {
      e.dataTransfer.dropEffect = 'none';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (preferredCli === 'cursor') return;

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFiles(files);
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [message]);

  // Handle clipboard paste for files
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      if (preferredCli === 'cursor') return;
      
      const items = e.clipboardData?.items;
      if (!items) return;
      
      const supportedFiles: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.startsWith('image/') || item.type === 'application/pdf' || item.type.startsWith('text/')) {
          const file = item.getAsFile();
          if (file) {
            supportedFiles.push(file);
          }
        }
      }
      
      if (supportedFiles.length > 0) {
        e.preventDefault();
        const fileList = {
          length: supportedFiles.length,
          item: (index: number) => supportedFiles[index],
          [Symbol.iterator]: function* () {
            for (let i = 0; i < supportedFiles.length; i++) {
              yield supportedFiles[i];
            }
          }
        } as FileList;
        
        // Convert to FileList-like object
        Object.defineProperty(fileList, 'length', { value: supportedFiles.length });
        supportedFiles.forEach((file, index) => {
          Object.defineProperty(fileList, index, { value: file });
        });
        
        handleFiles(fileList);
      }
    };
    
    document.addEventListener('paste', handlePaste);
    
    return () => {
      document.removeEventListener('paste', handlePaste);
    };
  }, [preferredCli]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element;
      if (!target.closest('.mode-dropdown-container')) {
        setShowModeDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="flex max-h-[calc(100%-37px)] shrink-0 flex-col overflow-visible">
      <div className="relative top-6">
        <div className="[&_[data-nudge]:not(:first-child)]:hidden"></div>
      </div>
      
      {/* Attached files preview */}
      {(attachedImages.length > 0 || attachedDocuments.length > 0) && (
        <div className="mb-2 flex flex-wrap gap-2 mr-2 md:mr-0">
          {/* Image previews */}
          {attachedImages.map((image, index) => (
            <div key={image.id} className="relative group">
              <img 
                src={image.url} 
                alt={image.name}
                className="w-20 h-20 object-cover rounded-lg border border-gray-200 dark:border-gray-600"
              />
              <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs px-1 py-0.5 rounded-b-lg truncate">
                Image #{index + 1}
              </div>
              <button
                type="button"
                onClick={() => removeImage(image.id)}
                className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                title={`Remove ${image.name}`}
              >
                ×
              </button>
            </div>
          ))}
          
          {/* Document indicators */}
          {attachedDocuments.map((doc, index) => (
            <div key={doc.id} className="relative group">
              <div className="w-20 h-20 flex flex-col items-center justify-center rounded-lg border border-gray-200 dark:border-gray-600 bg-blue-50 dark:bg-blue-900/20">
                <FileText className="w-6 h-6 text-blue-600 dark:text-blue-400 mb-1" />
                <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                  {doc.type.toUpperCase()}
                </span>
              </div>
              
              <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs px-1 py-0.5 rounded-b-lg truncate">
                {doc.name.length > 12 ? doc.name.substring(0, 12) + '...' : doc.name}
              </div>
              
              {/* File size indicator */}
              {doc.size > 1024 * 1024 && (
                <div className="absolute top-0 right-0 bg-green-500 text-white text-xs px-1 py-0.5 rounded-bl rounded-tr-lg">
                  {Math.round(doc.size / (1024 * 1024))}MB
                </div>
              )}
              
              <button
                type="button"
                onClick={() => removeDocument(doc.id)}
                className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                title={`Remove ${doc.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      
      <form 
        onSubmit={handleSubmit}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`group flex flex-col gap-2 rounded-3xl border transition-all duration-150 ease-in-out relative mr-2 md:mr-0 p-3 ${
          isDragOver 
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-lg' 
            : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 hover:border-gray-300 dark:hover:border-gray-600 focus-within:border-gray-400 dark:focus-within:border-gray-500 focus-within:shadow-lg'
        }`}
      >
        <div data-state="closed" style={{ cursor: 'text' }}>
          <div className="relative flex flex-1 items-center">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex w-full ring-offset-background placeholder:text-gray-500 dark:placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 resize-none text-[16px] leading-snug md:text-base max-h-[200px] bg-transparent focus:bg-transparent flex-1 m-1 rounded-md p-0 text-gray-900 dark:text-gray-100"
              id="chatinput"
              placeholder={placeholder}
              disabled={disabled}
              style={{ minHeight: '40px', height: '40px' }}
            />
          </div>
        </div>
        
        {/* Drag overlay */}
        {isDragOver && projectId && preferredCli !== 'cursor' && (
          <div className="absolute inset-0 bg-blue-50/90 dark:bg-blue-900/30 rounded-3xl flex items-center justify-center z-10 border-2 border-dashed border-blue-500">
            <div className="text-center">
              <div className="text-2xl mb-2">📎</div>
              <div className="text-sm font-medium text-blue-600 dark:text-blue-400">
                Drop files here
              </div>
              <div className="text-xs text-blue-500 dark:text-blue-500 mt-1">
                Images: JPG, PNG, GIF, WEBP<br />
                Documents: PDF, TXT (up to 50MB)
              </div>
            </div>
          </div>
        )}
        
        <div className="flex items-center gap-1">
          <div className="flex items-center gap-2">
            {/* File Upload Button */}
            {projectId && (
              preferredCli === 'cursor' ? (
                <div 
                  className="flex items-center justify-center w-8 h-8 text-gray-300 dark:text-gray-600 cursor-not-allowed opacity-50 rounded-full"
                  title="Cursor CLI doesn't support file input"
                >
                  <Paperclip className="h-4 w-4" />
                </div>
              ) : (
                <label 
                  className="flex items-center justify-center w-8 h-8 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Upload files (Images, PDFs & Text files)"
                >
                  <Paperclip className="h-4 w-4" />
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,application/pdf,text/*"
                    multiple
                    onChange={handleFileUpload}
                    disabled={isProcessing || disabled}
                    className="hidden"
                  />
                </label>
              )
            )}
          </div>
          
          <div className="ml-auto flex items-center gap-2">
            {/* Mode Selector - Similar to main page design */}
            <div className="mode-dropdown-container relative">
              <button
                type="button"
                onClick={() => setShowModeDropdown(!showModeDropdown)}
                className="whitespace-nowrap text-sm font-medium transition-colors duration-100 ease-in-out focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/5 shadow-sm hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-300 dark:hover:border-white/20 px-3 py-2 flex h-8 items-center justify-center gap-1.5 rounded-full text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white focus-visible:ring-0"
                title={
                  mode === 'act' ? 'Act Mode: AI can modify code and create/delete files' 
                  : mode === 'plan' ? 'Plan Mode: AI analyzes code and creates implementation plans'
                  : 'Chat Mode: AI provides answers without modifying code'
                }
              >
                {mode === 'act' ? <Wrench className="h-4 w-4" /> 
                 : mode === 'plan' ? <ClipboardList className="h-4 w-4" /> 
                 : <MessageSquare className="h-4 w-4" />}
                <span className="text-xs">
                  {mode === 'act' ? 'Act' : mode === 'plan' ? 'Plan' : 'Chat'}
                </span>
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 -960 960 960" className={`shrink-0 transition-transform ${showModeDropdown ? 'rotate-180' : ''}`} fill="currentColor">
                  <path d="M480-345 240-585l43-43 197 198 197-197 43 43-240 239Z"/>
                </svg>
              </button>
              
              {showModeDropdown && (
                <div className="absolute bottom-full mb-1 right-0 z-50 min-w-[150px] rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-gray-900 backdrop-blur-xl shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      onModeChange?.('act');
                      setShowModeDropdown(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-white/10 first:rounded-t-lg transition-colors ${
                      mode === 'act' 
                        ? 'text-gray-900 dark:text-white bg-gray-50 dark:bg-white/5' 
                        : 'text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white'
                    }`}
                    title="Act Mode: AI can modify code and create/delete files directly"
                  >
                    <Wrench className="h-4 w-4" />
                    <span className="text-xs">Act</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onModeChange?.('plan');
                      setShowModeDropdown(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-white/10 transition-colors ${
                      mode === 'plan' 
                        ? 'text-gray-900 dark:text-white bg-gray-50 dark:bg-white/5' 
                        : 'text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white'
                    }`}
                    title="Plan Mode: AI analyzes code and creates detailed implementation plans"
                  >
                    <ClipboardList className="h-4 w-4" />
                    <span className="text-xs">Plan</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onModeChange?.('chat');
                      setShowModeDropdown(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-white/10 last:rounded-b-lg transition-colors ${
                      mode === 'chat' 
                        ? 'text-gray-900 dark:text-white bg-gray-50 dark:bg-white/5' 
                        : 'text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white'
                    }`}
                    title="Chat Mode: AI provides answers and explanations without modifying code"
                  >
                    <MessageSquare className="h-4 w-4" />
                    <span className="text-xs">Chat</span>
                  </button>
                </div>
              )}
            </div>
            
            
            {/* Send Button */}
            <button
              id="chatinput-send-message-button"
              type="submit"
              className="flex size-8 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-gray-900 transition-all duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50 hover:scale-110 disabled:hover:scale-100"
              disabled={disabled || (!message.trim() && attachedImages.length === 0 && attachedDocuments.length === 0) || isProcessing}
            >
              {disabled ? (
                <div className="w-4 h-4 border-2 border-white dark:border-gray-900 border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <SendHorizontal className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </form>
      
      {/* Loading Overlay */}
      {disabled && (
        <div className="absolute inset-0 bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm rounded-3xl flex items-center justify-center z-20">
          <div className="flex items-center gap-3 px-4 py-2 bg-white dark:bg-gray-800 rounded-full shadow-lg border border-gray-200 dark:border-gray-700">
            <div className="w-4 h-4 border-2 border-gray-600 dark:border-gray-300 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {mode === 'act' ? '🛠️ Making changes...' 
               : mode === 'plan' ? '📋 Creating plan...'
               : '💬 Thinking...'}
            </span>
          </div>
        </div>
      )}
      
      <div className="z-10 h-2 w-full bg-background"></div>
    </div>
  );
}