/**
 * Worktree Management Hook
 * Handles git worktree operations for AI sessions
 */
import { useState, useEffect, useCallback } from 'react';

export interface WorktreeSession {
  id: string;
  session_id: string;
  branch_name: string;
  water_name: string;
  water_display: string;
  water_emoji: string;
  worktree_path: string;
  status: 'active' | 'merged' | 'discarded';
  created_at: string;
  last_activity?: string;
  changes_count?: number;
  is_clean: boolean;
  description?: string;
}

export interface WorktreeChanges {
  session_id: string;
  branch_name: string;
  changes: {
    modified: string[];
    added: string[];
    deleted: string[];
  };
  total_changes: number;
}

export interface UseWorktreeOptions {
  projectId: string;
  sessionId?: string;
  autoRefresh?: boolean;
  refreshInterval?: number; // in milliseconds
}

export interface UseWorktreeReturn {
  // Data
  worktrees: WorktreeSession[];
  currentWorktree: WorktreeSession | null;
  changes: WorktreeChanges | null;
  
  // State
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  
  // Actions
  createWorktree: (sessionId: string, baseBranch?: string) => Promise<WorktreeSession | null>;
  listWorktrees: () => Promise<void>;
  getWorktree: (sessionId: string) => Promise<WorktreeSession | null>;
  getChanges: (sessionId: string) => Promise<WorktreeChanges | null>;
  getDiff: (sessionId: string, filePath?: string) => Promise<string | null>;
  mergeWorktree: (sessionId: string, targetBranch?: string) => Promise<boolean>;
  discardWorktree: (sessionId: string) => Promise<boolean>;
  refreshWorktree: (sessionId: string) => Promise<void>;
}

export function useWorktree({ 
  projectId, 
  sessionId, 
  autoRefresh = false, 
  refreshInterval = 30000 
}: UseWorktreeOptions): UseWorktreeReturn {
  const [worktrees, setWorktrees] = useState<WorktreeSession[]>([]);
  const [currentWorktree, setCurrentWorktree] = useState<WorktreeSession | null>(null);
  const [changes, setChanges] = useState<WorktreeChanges | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // API helper function
  const apiCall = useCallback(async <T>(
    endpoint: string, 
    options?: RequestInit
  ): Promise<T | null> => {
    try {
      const response = await fetch(`/api/worktree/${projectId}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err: any) {
      setError(err.message);
      console.error('Worktree API error:', err);
      return null;
    }
  }, [projectId]);

  // Create a new worktree
  const createWorktree = useCallback(async (
    sessionId: string, 
    baseBranch: string = 'main'
  ): Promise<WorktreeSession | null> => {
    setIsCreating(true);
    setError(null);
    
    try {
      const result = await apiCall<WorktreeSession>('/worktree/create', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          base_branch: baseBranch,
        }),
      });

      if (result) {
        // Add to worktrees list
        setWorktrees(prev => [result, ...prev]);
        
        // Set as current if it's for the active session
        if (sessionId === sessionId) {
          setCurrentWorktree(result);
        }
      }

      return result;
    } finally {
      setIsCreating(false);
    }
  }, [apiCall, sessionId]);

  // List all worktrees
  const listWorktrees = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await apiCall<WorktreeSession[]>('/worktree');
      if (result) {
        setWorktrees(result);
        
        // Set current worktree if sessionId matches
        if (sessionId) {
          const current = result.find(wt => wt.session_id === sessionId);
          setCurrentWorktree(current || null);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [apiCall, sessionId]);

  // Get specific worktree
  const getWorktree = useCallback(async (sessionId: string): Promise<WorktreeSession | null> => {
    setError(null);
    
    const result = await apiCall<WorktreeSession>(`/worktree/${sessionId}`);
    
    if (result) {
      // Update in worktrees list
      setWorktrees(prev => 
        prev.map(wt => wt.session_id === sessionId ? result : wt)
      );
      
      // Update current worktree if it matches
      if (sessionId === sessionId) {
        setCurrentWorktree(result);
      }
    }

    return result;
  }, [apiCall, sessionId]);

  // Get changes for a worktree
  const getChanges = useCallback(async (sessionId: string): Promise<WorktreeChanges | null> => {
    setError(null);
    
    const result = await apiCall<WorktreeChanges>(`/worktree/${sessionId}/changes`);
    
    if (result && sessionId === sessionId) {
      setChanges(result);
    }

    return result;
  }, [apiCall, sessionId]);

  // Get diff for a worktree
  const getDiff = useCallback(async (
    sessionId: string, 
    filePath?: string
  ): Promise<string | null> => {
    setError(null);
    
    const queryParams = filePath ? `?file_path=${encodeURIComponent(filePath)}` : '';
    const result = await apiCall<{ diff_content: string }>(`/worktree/${sessionId}/diff${queryParams}`);
    
    return result?.diff_content || null;
  }, [apiCall]);

  // Merge worktree
  const mergeWorktree = useCallback(async (
    sessionId: string, 
    targetBranch: string = 'main'
  ): Promise<boolean> => {
    setError(null);
    
    const result = await apiCall<{ success: boolean }>(`/worktree/${sessionId}/merge`, {
      method: 'POST',
      body: JSON.stringify({
        target_branch: targetBranch,
      }),
    });

    if (result?.success) {
      // Update worktree status
      setWorktrees(prev =>
        prev.map(wt =>
          wt.session_id === sessionId
            ? { ...wt, status: 'merged' as const }
            : wt
        )
      );
      
      // Update current worktree
      if (currentWorktree?.session_id === sessionId) {
        setCurrentWorktree(prev => prev ? { ...prev, status: 'merged' } : null);
      }
    }

    return result?.success || false;
  }, [apiCall, currentWorktree]);

  // Discard worktree
  const discardWorktree = useCallback(async (sessionId: string): Promise<boolean> => {
    setError(null);
    
    const result = await apiCall<{ success: boolean }>(`/worktree/${sessionId}/discard`, {
      method: 'POST',
    });

    if (result?.success) {
      // Update worktree status
      setWorktrees(prev =>
        prev.map(wt =>
          wt.session_id === sessionId
            ? { ...wt, status: 'discarded' as const }
            : wt
        )
      );
      
      // Clear current worktree if it was discarded
      if (currentWorktree?.session_id === sessionId) {
        setCurrentWorktree(null);
      }
    }

    return result?.success || false;
  }, [apiCall, currentWorktree]);

  // Refresh specific worktree data
  const refreshWorktree = useCallback(async (sessionId: string) => {
    await Promise.all([
      getWorktree(sessionId),
      getChanges(sessionId)
    ]);
  }, [getWorktree, getChanges]);

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh || !sessionId) return;

    const interval = setInterval(() => {
      refreshWorktree(sessionId);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, sessionId, refreshInterval, refreshWorktree]);

  // Initial load
  useEffect(() => {
    listWorktrees();
  }, [projectId]);

  // Load current worktree and changes when sessionId changes
  useEffect(() => {
    if (sessionId) {
      refreshWorktree(sessionId);
    }
  }, [sessionId, refreshWorktree]);

  return {
    // Data
    worktrees,
    currentWorktree,
    changes,
    
    // State
    isLoading,
    isCreating,
    error,
    
    // Actions
    createWorktree,
    listWorktrees,
    getWorktree,
    getChanges,
    getDiff,
    mergeWorktree,
    discardWorktree,
    refreshWorktree,
  };
}