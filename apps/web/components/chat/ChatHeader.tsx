/**
 * Chat Header Component
 * Displays chat controls, context usage, and session management
 */
import React from 'react';
import { ChatMode } from '@/types/chat';
import { ContextIndicator, ContextUsage } from './ContextIndicator';
import { SessionManager, SessionInfo } from './SessionManager';

interface ChatHeaderProps {
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  onClear: () => void;
  isConnected?: boolean;
  sessionStatus?: string;
  // Context Management Props
  contextUsage?: ContextUsage;
  currentSession?: SessionInfo | null;
  allSessions?: SessionInfo[];
  canCreateNewSession?: boolean;
  recommendations?: string[];
  onSwitchSession?: (sessionId: string) => void;
  onCreateNewSession?: () => void;
  onExportSession?: (sessionId: string) => void;
  contextLoading?: boolean;
}

export function ChatHeader({ 
  mode, 
  onModeChange, 
  onClear, 
  isConnected,
  sessionStatus,
  // Context props
  contextUsage,
  currentSession,
  allSessions = [],
  canCreateNewSession = false,
  recommendations = [],
  onSwitchSession,
  onCreateNewSession,
  onExportSession,
  contextLoading = false
}: ChatHeaderProps) {
  return (
    <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 rounded-t-2xl">
      {/* Main Header Row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-4">
          {/* Mode Selector */}
          <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => onModeChange('chat')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'chat'
                  ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => onModeChange('act')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'act'
                  ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              Act
            </button>
          </div>

          {/* Connection Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-gray-400'
            }`} />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Session Status */}
          {sessionStatus && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Status: {sessionStatus}
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onClear}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            title="Clear messages"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" 
                    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Context and Session Management Row */}
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0 pr-4">
          {/* Context Usage Indicator */}
          {contextUsage && (
            <ContextIndicator 
              usage={contextUsage} 
              showDetails={true} 
              compact={false} 
            />
          )}
        </div>

        {/* Session Manager */}
        <div className="flex-shrink-0">
          {allSessions.length > 0 && onSwitchSession && onCreateNewSession && (
            <SessionManager
              currentSession={currentSession}
              allSessions={allSessions}
              canCreateNew={canCreateNewSession}
              recommendations={recommendations}
              onSwitchSession={onSwitchSession}
              onCreateNewSession={onCreateNewSession}
              onExportSession={onExportSession}
              isLoading={contextLoading}
            />
          )}
        </div>
      </div>
    </div>
  );
}