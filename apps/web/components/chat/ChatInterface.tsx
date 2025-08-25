/**
 * Chat Interface Component
 * Main chat container component
 */
import React, { useState, useCallback, useEffect } from 'react';
import { ChatMode, ImageAttachment } from '@/types/chat';
import { useChat } from '@/hooks/useChat';
import { useCLI } from '@/hooks/useCLI';
import { useContext } from '@/hooks/useContext';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { CLISelector } from './CLISelector';
import { ContextWarning, useContextWarnings } from './ContextWarning';

interface ChatInterfaceProps {
  projectId: string;
  conversationId?: string;
}

export function ChatInterface({ projectId, conversationId }: ChatInterfaceProps) {
  const [mode, setMode] = useState<ChatMode>('chat');
  const [showCLISelector, setShowCLISelector] = useState(false);
  
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
    exportSession
  } = useContext({ projectId });

  const handleSendMessage = useCallback(async (content: string, images?: ImageAttachment[]) => {
    if (mode === 'chat') {
      await sendMessage(content);
    } else {
      await executeAct(content, {
        cliPreference: preference?.preferred_cli,
        fallbackEnabled: preference?.fallback_enabled,
        images
      });
    }
  }, [mode, sendMessage, executeAct, preference]);

  const handleCLISelect = useCallback(async (cliId: string) => {
    await updatePreference(cliId);
    setShowCLISelector(false);
  }, [updatePreference]);

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
        contextUsage={currentUsage}
        currentSession={contextCurrentSession}
        allSessions={allSessions}
        canCreateNewSession={canCreateNew}
        recommendations={recommendations}
        onSwitchSession={switchSession}
        onCreateNewSession={createNewSession}
        onExportSession={exportSession}
        contextLoading={contextLoading}
      />

      {/* CLI Selector (Act mode only) */}
      {mode === 'act' && (
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

      {/* Context Warning */}
      {shouldShowWarning && (
        <ContextWarning
          usage={currentUsage}
          recommendations={recommendations}
          onCreateNewSession={createNewSession}
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
    </div>
  );
}