/**
 * Context Management Hook
 * Handles context usage tracking, session management, and warnings
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { ContextUsage, calculateContextUsage } from '@/components/chat/ContextIndicator';
import { SessionInfo } from '@/components/chat/SessionManager';

interface ContextResponse {
  current_session: SessionInfo | null;
  all_sessions: SessionInfo[];
  can_create_new: boolean;
  recommendations: string[];
}

interface UseContextOptions {
  projectId: string;
  refreshInterval?: number; // milliseconds
  autoRefresh?: boolean;
}

export function useContext({ 
  projectId, 
  refreshInterval = 30000, // 30 seconds
  autoRefresh = true 
}: UseContextOptions) {
  const [contextData, setContextData] = useState<ContextResponse | null>(null);
  const [currentUsage, setCurrentUsage] = useState<ContextUsage | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  // Refs for cleanup
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch context data
  const fetchContextData = useCallback(async (signal?: AbortSignal) => {
    try {
      setError(null);
      
      const response = await fetch(`/api/context/${projectId}/context`, {
        signal
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch context data: ${response.status}`);
      }
      
      const data: ContextResponse = await response.json();
      setContextData(data);
      setLastUpdate(new Date());
      
      // Calculate current usage from active session
      if (data.current_session) {
        const usage = calculateContextUsage(
          data.current_session.total_tokens,
          200000 // Default model limit
        );
        usage.session_id = data.current_session.session_id;
        setCurrentUsage(usage);
      } else {
        setCurrentUsage(null);
      }
      
      return data;
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error('Context fetch error:', error);
        setError(error.message || 'Failed to fetch context data');
      }
      throw error;
    }
  }, [projectId]);

  // Load context data with loading state
  const loadContextData = useCallback(async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    
    try {
      // Cancel previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Create new abort controller
      abortControllerRef.current = new AbortController();
      
      await fetchContextData(abortControllerRef.current.signal);
    } catch (error) {
      // Error already handled in fetchContextData
    } finally {
      setIsLoading(false);
    }
  }, [fetchContextData, isLoading]);

  // Switch to a different session
  const switchSession = useCallback(async (sessionId: string) => {
    try {
      setIsLoading(true);
      
      // Here you would typically call an API to set the active session
      // For now, we'll just refresh the context data
      await loadContextData();
      
      // Trigger a custom event that the chat system can listen to
      window.dispatchEvent(new CustomEvent('session-switch', { 
        detail: { projectId, sessionId } 
      }));
      
    } catch (error) {
      console.error('Session switch error:', error);
      setError('Failed to switch session');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, loadContextData]);

  // Create new session
  const createNewSession = useCallback(async () => {
    try {
      setIsLoading(true);
      
      const currentSessionId = contextData?.current_session?.session_id;
      
      const response = await fetch(`/api/context/${projectId}/sessions/new`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          previous_session_id: currentSessionId,
          include_summary: true
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create new session: ${response.status}`);
      }
      
      const newSession = await response.json();
      
      // Refresh context data to get the new session
      await loadContextData();
      
      // Trigger session creation event
      window.dispatchEvent(new CustomEvent('session-created', { 
        detail: { 
          projectId, 
          sessionId: newSession.session_id,
          previousSessionId: currentSessionId,
          summary: newSession.summary
        } 
      }));
      
      return newSession;
    } catch (error: any) {
      console.error('Create session error:', error);
      setError(error.message || 'Failed to create new session');
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [projectId, contextData, loadContextData]);

  // Export session data
  const exportSession = useCallback(async (sessionId: string) => {
    try {
      setIsLoading(true);
      
      // Fetch session messages
      const response = await fetch(`/api/chat/${projectId}/messages?session_id=${sessionId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to export session: ${response.status}`);
      }
      
      const messages = await response.json();
      const session = contextData?.all_sessions.find(s => s.session_id === sessionId);
      
      // Create export data
      const exportData = {
        session_id: sessionId,
        project_id: projectId,
        started_at: session?.started_at,
        total_tokens: session?.total_tokens,
        message_count: session?.message_count,
        messages: messages,
        exported_at: new Date().toISOString()
      };
      
      // Download as JSON file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `session-${sessionId.slice(0, 8)}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (error: any) {
      console.error('Export session error:', error);
      setError(error.message || 'Failed to export session');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, contextData]);

  // Update context usage (called by chat system)
  const updateContextUsage = useCallback(async (totalTokens: number, sessionId?: string) => {
    try {
      const targetSessionId = sessionId || contextData?.current_session?.session_id;
      if (!targetSessionId) return;
      
      const response = await fetch(
        `/api/context/${projectId}/sessions/${targetSessionId}/context`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ total_tokens: totalTokens })
        }
      );
      
      if (!response.ok) {
        throw new Error(`Failed to update context: ${response.status}`);
      }
      
      const result = await response.json();
      
      // Update local usage state
      const newUsage: ContextUsage = {
        current: totalTokens,
        limit: 200000, // TODO: Get from session data
        percentage: result.percentage,
        status: result.status,
        session_id: targetSessionId
      };
      
      setCurrentUsage(newUsage);
      
      // Update recommendations
      if (contextData) {
        setContextData(prev => prev ? {
          ...prev,
          recommendations: result.recommendations
        } : null);
      }
      
      return result;
    } catch (error: any) {
      console.error('Update context error:', error);
      // Don't set error state for context updates to avoid disrupting chat flow
    }
  }, [projectId, contextData]);

  // Get warnings for current context state
  const getWarnings = useCallback(() => {
    const warnings: string[] = [];
    
    if (currentUsage) {
      if (currentUsage.status === 'critical') {
        warnings.push('Context usage is critical - create a new session to continue');
      } else if (currentUsage.status === 'warning') {
        warnings.push('Approaching context limit - consider wrapping up complex tasks');
      }
    }
    
    return warnings;
  }, [currentUsage]);

  // Check if should show warning
  const shouldShowWarning = useCallback(() => {
    return currentUsage?.status === 'warning' || currentUsage?.status === 'critical';
  }, [currentUsage]);

  // Setup auto-refresh
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      refreshIntervalRef.current = setInterval(() => {
        if (!isLoading) {
          fetchContextData();
        }
      }, refreshInterval);
    }
    
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, refreshInterval, isLoading, fetchContextData]);

  // Initial load
  useEffect(() => {
    loadContextData();
    
    // Cleanup on unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [loadContextData]);

  return {
    // Data
    contextData,
    currentUsage,
    currentSession: contextData?.current_session || null,
    allSessions: contextData?.all_sessions || [],
    canCreateNew: contextData?.can_create_new || false,
    recommendations: contextData?.recommendations || [],
    
    // State
    isLoading,
    error,
    lastUpdate,
    
    // Actions
    loadContextData,
    switchSession,
    createNewSession,
    exportSession,
    updateContextUsage,
    
    // Helpers
    getWarnings,
    shouldShowWarning
  };
}