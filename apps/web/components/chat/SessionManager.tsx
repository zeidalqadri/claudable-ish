/**
 * Session Manager Component
 * Handles session switching and continuity for context management
 */
import React, { useState, useCallback } from 'react';
import { ContextUsage } from './ContextIndicator';

export interface SessionInfo {
  session_id: string;
  total_tokens: number;
  message_count: number;
  context_percentage: number;
  context_status: string;
  started_at: string;
  is_active: boolean;
}

export interface SessionManagerProps {
  currentSession: SessionInfo | null;
  allSessions: SessionInfo[];
  canCreateNew: boolean;
  recommendations: string[];
  onSwitchSession: (sessionId: string) => void;
  onCreateNewSession: () => void;
  onExportSession?: (sessionId: string) => void;
  isLoading?: boolean;
}

export function SessionManager({
  currentSession,
  allSessions,
  canCreateNew,
  recommendations,
  onSwitchSession,
  onCreateNewSession,
  onExportSession,
  isLoading = false
}: SessionManagerProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showRecommendations, setShowRecommendations] = useState(false);

  const formatDate = useCallback((dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return date.toLocaleDateString();
    }
  }, []);

  const getStatusColor = (status: string) => {
    const colors = {
      safe: 'text-green-600 bg-green-50 border-green-200',
      warning: 'text-yellow-600 bg-yellow-50 border-yellow-200',
      critical: 'text-red-600 bg-red-50 border-red-200'
    };
    return colors[status] || 'text-gray-600 bg-gray-50 border-gray-200';
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`;
    } else if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  const hasWarnings = recommendations.some(rec => 
    rec.toLowerCase().includes('critical') || 
    rec.toLowerCase().includes('warning') ||
    rec.toLowerCase().includes('approaching')
  );

  return (
    <div className="flex items-center gap-3">
      {/* Session Selector */}
      <div className="relative">
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
        >
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              currentSession?.is_active ? 'bg-green-500' : 'bg-gray-400'
            }`} />
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {currentSession ? 
                `Session ${allSessions.findIndex(s => s.session_id === currentSession.session_id) + 1}` : 
                'No Active Session'
              }
            </span>
          </div>
          
          {currentSession && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {formatTokens(currentSession.total_tokens)} tokens
            </span>
          )}
          
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Session Dropdown */}
        {showDropdown && (
          <div className="absolute top-full left-0 mt-1 w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
            <div className="p-3 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                Chat Sessions
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Switch between sessions or create a new one
              </p>
            </div>

            <div className="max-h-64 overflow-y-auto">
              {allSessions.map((session, index) => (
                <button
                  key={session.session_id}
                  onClick={() => {
                    onSwitchSession(session.session_id);
                    setShowDropdown(false);
                  }}
                  className={`w-full p-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors border-l-2 ${
                    session.session_id === currentSession?.session_id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          Session {index + 1}
                        </span>
                        {session.is_active && (
                          <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 rounded">
                            Active
                          </span>
                        )}
                        <span className={`px-1.5 py-0.5 text-xs rounded border ${getStatusColor(session.context_status)}`}>
                          {session.context_status}
                        </span>
                      </div>
                      
                      <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                        <div>Started {formatDate(session.started_at)}</div>
                        <div className="flex items-center gap-3">
                          <span>{formatTokens(session.total_tokens)} tokens</span>
                          <span>{session.message_count} messages</span>
                          <span>{session.context_percentage.toFixed(1)}% used</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 ml-2">
                      {onExportSession && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onExportSession(session.session_id);
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                          title="Export session"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Create New Session */}
            <div className="p-3 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => {
                  onCreateNewSession();
                  setShowDropdown(false);
                }}
                disabled={!canCreateNew || isLoading}
                className="w-full flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                <span className="text-sm font-medium">
                  {canCreateNew ? 'Create New Session' : 'Current session still usable'}
                </span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Recommendations Alert */}
      {hasWarnings && (
        <div className="relative">
          <button
            onClick={() => setShowRecommendations(!showRecommendations)}
            className="p-1.5 text-amber-600 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors animate-pulse"
            title="Context usage recommendations"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </button>

          {/* Recommendations Popup */}
          {showRecommendations && (
            <div className="absolute top-full right-0 mt-1 w-72 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
              <div className="p-3 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
                  <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  Recommendations
                </h3>
              </div>
              <div className="p-3 space-y-2">
                {recommendations.map((rec, index) => (
                  <div key={index} className="flex items-start gap-2 text-sm">
                    <div className="w-1 h-1 bg-gray-400 rounded-full mt-2 flex-shrink-0" />
                    <span className="text-gray-700 dark:text-gray-300">{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Click outside to close dropdowns */}
      {(showDropdown || showRecommendations) && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setShowDropdown(false);
            setShowRecommendations(false);
          }}
        />
      )}
    </div>
  );
}