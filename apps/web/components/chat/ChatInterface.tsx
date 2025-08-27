/**
 * Chat Interface Component
 * Main chat container component
 */
import React, { useState, useCallback, useEffect } from 'react';
import { ChatMode, ImageAttachment } from '@/types/chat';
import { useChat } from '@/hooks/useChat';
import { useCLI } from '@/hooks/useCLI';
import { useContext } from '@/hooks/useContext';
import { useWorktree } from '@/hooks/useWorktree';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { CLISelector } from './CLISelector';
import { ContextWarning, useContextWarnings } from './ContextWarning';
import { WorktreeManager } from './WorktreeManager';
import { WorktreeDiffViewer } from './WorktreeDiffViewer';
import { MemoryPanel } from '../memory/MemoryPanel';

interface ChatInterfaceProps {
  projectId: string;
  conversationId?: string;
}

export function ChatInterface({ projectId, conversationId }: ChatInterfaceProps) {
  const [mode, setMode] = useState<ChatMode>('chat');
  const [showCLISelector, setShowCLISelector] = useState(false);
  const [showDiffViewer, setShowDiffViewer] = useState(false);
  const [showMemoryPanel, setShowMemoryPanel] = useState(false);
  
  const {
    messages,
    isLoading,
    isConnected,
    currentSession,
    sendMessage,
    executeAct,
    clearMessages
  } = useChat({ projectId, conversationId });

  const {
    cliOptions,
    preference,
    updatePreference
  } = useCLI({ projectId });

  // Context Management
  const {
    currentUsage,
    currentSession: contextCurrentSession,
    allSessions,
    canCreateNew,
    recommendations,
    isLoading: contextLoading,
    switchSession,
    createNewSession,
    resetContext,
    exportSession
  } = useContext({ projectId });

  // Worktree Management
  const {
    worktrees,
    currentWorktree,
    changes: worktreeChanges,
    isLoading: worktreeLoading,
    createWorktree,
    getDiff,
    mergeWorktree,
    discardWorktree,
  } = useWorktree({ 
    projectId, 
    sessionId: currentSession?.id,
    autoRefresh: true,
    refreshInterval: 30000 
  });

  const handleSendMessage = useCallback(async (content: string, images?: ImageAttachment[]) => {
    if (mode === 'chat') {
      await sendMessage(content);
    } else if (mode === 'plan') {
      await executeAct(content, {
        cliPreference: preference?.preferred_cli,
        fallbackEnabled: preference?.fallback_enabled,
        images,
        executionMode: 'plan'
      });
    } else {
      await executeAct(content, {
        cliPreference: preference?.preferred_cli,
        fallbackEnabled: preference?.fallback_enabled,
        images,
        executionMode: 'act'
      });
    }
  }, [mode, sendMessage, executeAct, preference]);

  const handleCLISelect = useCallback(async (cliId: string) => {
    await updatePreference(cliId);
    setShowCLISelector(false);
  }, [updatePreference]);

  // Worktree handlers
  const handleSwitchWorktree = useCallback(async (sessionId: string) => {
    // Switch to different worktree session - this would integrate with session switching
    console.log('Switch to worktree session:', sessionId);
    // TODO: Integrate with session switching logic
  }, []);

  const handleShowDiff = useCallback((sessionId: string) => {
    setShowDiffViewer(true);
  }, []);

  const handleMergeWorktree = useCallback(async (sessionId: string) => {
    const success = await mergeWorktree(sessionId);
    if (success) {
      // Show success message or notification
      console.log('Worktree merged successfully');
    }
    return success;
  }, [mergeWorktree]);

  const handleDiscardWorktree = useCallback(async (sessionId: string) => {
    const success = await discardWorktree(sessionId);
    if (success) {
      // Show success message or notification
      console.log('Worktree discarded successfully');
    }
    return success;
  }, [discardWorktree]);

  // Auto-create worktree when starting a new act session
  useEffect(() => {
    const createWorktreeForSession = async () => {
      if (mode === 'act' && currentSession?.id && !currentWorktree && !worktreeLoading) {
        try {
          console.log('Auto-creating worktree for session:', currentSession.id);
          await createWorktree(currentSession.id);
        } catch (error) {
          console.error('Failed to create worktree for session:', error);
          // Don't retry automatically to avoid infinite loops
        }
      }
    };

    createWorktreeForSession();
  }, [mode, currentSession?.id, currentWorktree, createWorktree, worktreeLoading]);

  // Context warnings
  const {
    shouldShowWarning,
    dismissWarning,
    showNotification
  } = useContextWarnings(currentUsage, recommendations);

  // Show browser notification for critical warnings
  useEffect(() => {
    if (currentUsage?.status === 'critical' && shouldShowWarning) {
      showNotification();
    }
  }, [currentUsage?.status, shouldShowWarning, showNotification]);

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 rounded-2xl shadow-lg">
      {/* Header */}
      <ChatHeader
        mode={mode}
        onModeChange={setMode}
        onClear={clearMessages}
        isConnected={isConnected}
        sessionStatus={currentSession?.status}
        // Context Management Props
        contextUsage={currentUsage || undefined}
        currentSession={contextCurrentSession}
        allSessions={allSessions}
        canCreateNewSession={canCreateNew}
        recommendations={recommendations}
        onSwitchSession={switchSession}
        onCreateNewSession={createNewSession}
        onExportSession={exportSession}
        contextLoading={contextLoading}
        // Memory Props
        onToggleMemory={() => setShowMemoryPanel(!showMemoryPanel)}
      />

      {/* CLI Selector (Plan and Act modes only) */}
      {(mode === 'plan' || mode === 'act') && (
        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">AI Assistant:</span>
              <button
                onClick={() => setShowCLISelector(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
              >
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {cliOptions.find(opt => opt.id === preference?.preferred_cli)?.name || 'Select CLI'}
                </span>
                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            
            {preference?.fallback_enabled && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Fallback enabled
              </span>
            )}
          </div>
        </div>
      )}

      {/* Worktree Manager (Act mode only) */}
      {mode === 'act' && (
        <div className="px-6 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Worktree:</span>
              <WorktreeManager
                worktrees={worktrees}
                currentWorktree={currentWorktree}
                changes={worktreeChanges}
                isLoading={worktreeLoading}
                onSwitchWorktree={handleSwitchWorktree}
                onMergeWorktree={handleMergeWorktree}
                onDiscardWorktree={handleDiscardWorktree}
                onShowDiff={handleShowDiff}
                onCreateWorktree={async () => {
                  if (currentSession?.id) {
                    try {
                      await createWorktree(currentSession.id);
                    } catch (error) {
                      console.error('Failed to create worktree:', error);
                    }
                  }
                }}
              />
            </div>
            
            {currentWorktree && (
              <div className="text-xs text-gray-500 dark:text-gray-400">
                <span className="font-mono">{currentWorktree.branch_name}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Context Warning */}
      {shouldShowWarning && (
        <ContextWarning
          usage={currentUsage}
          recommendations={recommendations}
          onCreateNewSession={createNewSession}
          onResetContext={resetContext}
          onDismiss={dismissWarning}
        />
      )}

      {/* Messages */}
      <MessageList
        messages={messages}
        isLoading={isLoading}
      />

      {/* Input */}
      <MessageInput
        mode={mode}
        onSend={handleSendMessage}
        disabled={isLoading || (currentSession?.status === 'running')}
        placeholder={
          currentSession?.status === 'running' 
            ? 'Please wait...' 
            : mode === 'act' 
            ? 'Describe what you want to build...' 
            : mode === 'plan'
            ? 'Describe what you want to analyze or plan...'
            : 'Type a message...'
        }
      />

      {/* CLI Selector Modal */}
      {showCLISelector && (
        <CLISelector
          options={cliOptions}
          selected={preference?.preferred_cli}
          onSelect={handleCLISelect}
          onClose={() => setShowCLISelector(false)}
        />
      )}

      {/* Worktree Diff Viewer */}
      {showDiffViewer && currentWorktree && (
        <WorktreeDiffViewer
          sessionId={currentWorktree.session_id}
          changes={worktreeChanges}
          onGetDiff={getDiff}
          onClose={() => setShowDiffViewer(false)}
        />
      )}

      {/* Memory Panel */}
      <MemoryPanel
        projectId={projectId}
        isOpen={showMemoryPanel}
        onClose={() => setShowMemoryPanel(false)}
      />
    </div>
  );
}