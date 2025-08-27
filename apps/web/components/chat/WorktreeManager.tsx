/**
 * Worktree Manager Component
 * Displays and manages git worktrees for AI sessions
 */
import React, { useState } from 'react';
import { WorktreeSession, WorktreeChanges } from '@/hooks/useWorktree';
import { formatDistanceToNow } from 'date-fns';

interface WorktreeManagerProps {
  worktrees: WorktreeSession[];
  currentWorktree: WorktreeSession | null;
  changes: WorktreeChanges | null;
  isLoading: boolean;
  onSwitchWorktree: (sessionId: string) => void;
  onMergeWorktree: (sessionId: string) => Promise<boolean>;
  onDiscardWorktree: (sessionId: string) => Promise<boolean>;
  onShowDiff: (sessionId: string) => void;
  onCreateWorktree?: () => Promise<void>;
}

export function WorktreeManager({
  worktrees,
  currentWorktree,
  changes,
  isLoading,
  onSwitchWorktree,
  onMergeWorktree,
  onDiscardWorktree,
  onShowDiff,
  onCreateWorktree
}: WorktreeManagerProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleMerge = async (sessionId: string) => {
    setActionLoading(`merge-${sessionId}`);
    try {
      await onMergeWorktree(sessionId);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDiscard = async (sessionId: string) => {
    setActionLoading(`discard-${sessionId}`);
    try {
      await onDiscardWorktree(sessionId);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'merged':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'discarded':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatTimeAgo = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return 'Unknown time';
    }
  };

  if (worktrees.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} />
        {isLoading ? (
          <span className="text-gray-500">Creating worktree...</span>
        ) : onCreateWorktree ? (
          <button
            onClick={onCreateWorktree}
            className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
          >
            Create worktree
          </button>
        ) : (
          <span className="text-gray-500">No worktrees</span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {/* Current Worktree Display */}
      <div className="relative">
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
        >
          <div className="flex items-center gap-2">
            {/* Water emoji and name */}
            {currentWorktree ? (
              <>
                <span className="text-lg">{currentWorktree.water_emoji}</span>
                <div className="flex flex-col items-start">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {currentWorktree.water_display}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded border ${getStatusColor(currentWorktree.status)}`}>
                    {currentWorktree.status}
                  </span>
                </div>
              </>
            ) : (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                No active worktree
              </span>
            )}
          </div>
          
          {/* Changes indicator */}
          {changes && changes.total_changes > 0 && (
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded-full text-xs font-medium">
              {changes.total_changes} changes
            </span>
          )}
          
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Worktree Dropdown */}
        {showDropdown && (
          <div className="absolute top-full left-0 mt-1 w-96 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 max-h-96 overflow-hidden">
            <div className="p-3 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
                🌊 Worktree Sessions
                <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                  {worktrees.filter(wt => wt.status === 'active').length} active
                </span>
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Switch between isolated development environments
              </p>
            </div>

            <div className="max-h-64 overflow-y-auto">
              {worktrees.map((worktree) => (
                <div
                  key={worktree.id}
                  className={`p-3 border-l-2 transition-colors ${
                    worktree.id === currentWorktree?.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-transparent hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      {/* Worktree header */}
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">{worktree.water_emoji}</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {worktree.water_display}
                        </span>
                        <span className={`px-1.5 py-0.5 text-xs rounded border ${getStatusColor(worktree.status)}`}>
                          {worktree.status}
                        </span>
                        {worktree.id === currentWorktree?.id && (
                          <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded">
                            Current
                          </span>
                        )}
                      </div>
                      
                      {/* Branch and timing info */}
                      <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                        <div className="font-mono text-xs">
                          {worktree.branch_name}
                        </div>
                        <div className="flex items-center gap-3">
                          <span>Created {formatTimeAgo(worktree.created_at)}</span>
                          {worktree.changes_count !== undefined && (
                            <span>
                              {worktree.changes_count} changes
                            </span>
                          )}
                          <span className={worktree.is_clean ? 'text-green-600' : 'text-orange-600'}>
                            {worktree.is_clean ? 'Clean' : 'Modified'}
                          </span>
                        </div>
                      </div>
                      
                      {/* Description */}
                      {worktree.description && (
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 truncate">
                          {worktree.description}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 ml-3">
                      {/* Switch button */}
                      {worktree.status === 'active' && worktree.id !== currentWorktree?.id && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSwitchWorktree(worktree.session_id);
                            setShowDropdown(false);
                          }}
                          className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                          title="Switch to this worktree"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                          </svg>
                        </button>
                      )}
                      
                      {/* Diff button */}
                      {worktree.status === 'active' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onShowDiff(worktree.session_id);
                          }}
                          className="p-1 text-gray-400 hover:text-purple-600 dark:hover:text-purple-400"
                          title="View diff"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </button>
                      )}
                      
                      {/* Merge button */}
                      {worktree.status === 'active' && worktree.changes_count && worktree.changes_count > 0 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleMerge(worktree.session_id);
                          }}
                          disabled={actionLoading === `merge-${worktree.session_id}`}
                          className="p-1 text-gray-400 hover:text-green-600 dark:hover:text-green-400 disabled:opacity-50"
                          title="Merge to main"
                        >
                          {actionLoading === `merge-${worktree.session_id}` ? (
                            <div className="w-3 h-3 border border-gray-300 border-t-green-500 rounded-full animate-spin" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </button>
                      )}
                      
                      {/* Discard button */}
                      {worktree.status === 'active' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Discard worktree "${worktree.water_display}"? This will delete all changes.`)) {
                              handleDiscard(worktree.session_id);
                            }
                          }}
                          disabled={actionLoading === `discard-${worktree.session_id}`}
                          className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-50"
                          title="Discard worktree"
                        >
                          {actionLoading === `discard-${worktree.session_id}` ? (
                            <div className="w-3 h-3 border border-gray-300 border-t-red-500 rounded-full animate-spin" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Summary */}
            <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center justify-between">
                <span>
                  {worktrees.filter(wt => wt.status === 'active').length} active, {' '}
                  {worktrees.filter(wt => wt.status === 'merged').length} merged, {' '}
                  {worktrees.filter(wt => wt.status === 'discarded').length} discarded
                </span>
                <span className="font-mono">
                  git worktree
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Click outside to close */}
      {showDropdown && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowDropdown(false)}
        />
      )}
    </div>
  );
}