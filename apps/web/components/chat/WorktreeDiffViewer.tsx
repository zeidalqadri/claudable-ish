/**
 * Worktree Diff Viewer Component
 * Shows git diff between worktree and main branch
 */
import React, { useState, useEffect } from 'react';
import { WorktreeChanges } from '@/hooks/useWorktree';

interface WorktreeDiffViewerProps {
  sessionId: string;
  changes: WorktreeChanges | null;
  onGetDiff: (sessionId: string, filePath?: string) => Promise<string | null>;
  onClose: () => void;
}

interface DiffLine {
  type: 'context' | 'added' | 'removed' | 'info';
  content: string;
  lineNumber?: {
    old?: number;
    new?: number;
  };
}

export function WorktreeDiffViewer({ sessionId, changes, onGetDiff, onClose }: WorktreeDiffViewerProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [diffContent, setDiffContent] = useState<string>('');
  const [parsedDiff, setParsedDiff] = useState<DiffLine[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('unified');

  // Get all changed files
  const allFiles = changes ? [
    ...changes.changes.modified.map(f => ({ path: f, status: 'modified' as const })),
    ...changes.changes.added.map(f => ({ path: f, status: 'added' as const })),
    ...changes.changes.deleted.map(f => ({ path: f, status: 'deleted' as const }))
  ] : [];

  // Load diff for selected file or all files
  useEffect(() => {
    const loadDiff = async () => {
      if (!sessionId) return;

      setIsLoading(true);
      try {
        const diff = await onGetDiff(sessionId, selectedFile || undefined);
        setDiffContent(diff || '');
        setParsedDiff(parseDiff(diff || ''));
      } catch (error) {
        console.error('Failed to load diff:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadDiff();
  }, [sessionId, selectedFile, onGetDiff]);

  // Parse git diff into structured lines
  const parseDiff = (diff: string): DiffLine[] => {
    const lines = diff.split('\n');
    const parsed: DiffLine[] = [];
    
    let oldLineNum = 0;
    let newLineNum = 0;

    for (const line of lines) {
      if (line.startsWith('@@')) {
        // Hunk header
        const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/);
        if (match) {
          oldLineNum = parseInt(match[1]) - 1;
          newLineNum = parseInt(match[2]) - 1;
        }
        parsed.push({
          type: 'info',
          content: line,
        });
      } else if (line.startsWith('+++') || line.startsWith('---')) {
        // File headers
        parsed.push({
          type: 'info',
          content: line,
        });
      } else if (line.startsWith('+')) {
        // Added line
        newLineNum++;
        parsed.push({
          type: 'added',
          content: line.slice(1),
          lineNumber: { new: newLineNum },
        });
      } else if (line.startsWith('-')) {
        // Removed line
        oldLineNum++;
        parsed.push({
          type: 'removed',
          content: line.slice(1),
          lineNumber: { old: oldLineNum },
        });
      } else if (line.startsWith(' ')) {
        // Context line
        oldLineNum++;
        newLineNum++;
        parsed.push({
          type: 'context',
          content: line.slice(1),
          lineNumber: { old: oldLineNum, new: newLineNum },
        });
      } else if (line.startsWith('diff --git')) {
        // File separator
        parsed.push({
          type: 'info',
          content: line,
        });
      }
    }

    return parsed;
  };

  const getLineClassName = (type: string) => {
    switch (type) {
      case 'added':
        return 'bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500';
      case 'removed':
        return 'bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500';
      case 'info':
        return 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400';
      default:
        return 'bg-white dark:bg-gray-900';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'added':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'modified':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'deleted':
        return 'text-red-600 bg-red-50 border-red-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  if (!changes) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
          <p className="text-center text-gray-500 dark:text-gray-400">
            No changes to display
          </p>
          <button
            onClick={onClose}
            className="mt-4 w-full px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-7xl h-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Worktree Changes
            </h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {changes.branch_name}
            </span>
            <span className="px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded text-sm">
              {changes.total_changes} changes
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            {/* View mode toggle */}
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setViewMode('unified')}
                className={`px-3 py-1 text-xs rounded ${
                  viewMode === 'unified'
                    ? 'bg-white dark:bg-gray-600 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                Unified
              </button>
              <button
                onClick={() => setViewMode('split')}
                className={`px-3 py-1 text-xs rounded ${
                  viewMode === 'split'
                    ? 'bg-white dark:bg-gray-600 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                Split
              </button>
            </div>
            
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* File list sidebar */}
          <div className="w-80 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto">
            <div className="p-3 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedFile(null)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    selectedFile === null
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  All files
                </button>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ({allFiles.length})
                </span>
              </div>
            </div>
            
            <div className="p-2 space-y-1">
              {allFiles.map((file, index) => (
                <button
                  key={index}
                  onClick={() => setSelectedFile(file.path)}
                  className={`w-full text-left p-2 rounded-lg transition-colors ${
                    selectedFile === file.path
                      ? 'bg-blue-100 dark:bg-blue-900/20'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 text-xs rounded border ${getStatusColor(file.status)}`}>
                      {file.status.charAt(0).toUpperCase()}
                    </span>
                    <span className="text-sm font-mono text-gray-900 dark:text-white truncate">
                      {file.path}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Diff content */}
          <div className="flex-1 overflow-auto">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                  <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
                  Loading diff...
                </div>
              </div>
            ) : parsedDiff.length > 0 ? (
              <div className="font-mono text-sm">
                {parsedDiff.map((line, index) => (
                  <div
                    key={index}
                    className={`px-4 py-1 flex ${getLineClassName(line.type)}`}
                  >
                    {/* Line numbers */}
                    <div className="flex-shrink-0 w-20 text-xs text-gray-500 dark:text-gray-400 select-none">
                      {line.lineNumber && (
                        <>
                          <span className="inline-block w-8 text-right">
                            {line.lineNumber.old || ''}
                          </span>
                          <span className="inline-block w-8 text-right">
                            {line.lineNumber.new || ''}
                          </span>
                        </>
                      )}
                    </div>
                    
                    {/* Line content */}
                    <div className="flex-1 whitespace-pre-wrap break-all">
                      {line.content}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <p>No diff content available</p>
                  <p className="text-xs mt-1">
                    {selectedFile ? `No changes in ${selectedFile}` : 'No changes to display'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer with file statistics */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 bg-green-500 rounded-full" />
                {changes.changes.added.length} added
              </span>
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 bg-blue-500 rounded-full" />
                {changes.changes.modified.length} modified
              </span>
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 bg-red-500 rounded-full" />
                {changes.changes.deleted.length} deleted
              </span>
            </div>
            
            <div className="flex items-center gap-2">
              <span>
                Showing: {selectedFile || 'All files'}
              </span>
              <span className="font-mono">
                git diff main {changes.branch_name}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}