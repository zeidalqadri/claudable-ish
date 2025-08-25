/**
 * Context Indicator Component
 * Displays token usage and context limits with visual feedback
 */
import React from 'react';

export interface ContextUsage {
  current: number;
  limit: number;
  percentage: number;
  status: 'safe' | 'warning' | 'critical' | 'unknown';
}

interface ContextIndicatorProps {
  usage: ContextUsage;
  showDetails?: boolean;
  compact?: boolean;
}

export function ContextIndicator({ usage, showDetails = true, compact = false }: ContextIndicatorProps) {
  const getStatusColor = (status: string, type: 'bg' | 'text' | 'border' = 'bg') => {
    const colors = {
      safe: {
        bg: 'bg-green-500',
        text: 'text-green-600',
        border: 'border-green-300'
      },
      warning: {
        bg: 'bg-yellow-500',
        text: 'text-yellow-600',
        border: 'border-yellow-300'
      },
      critical: {
        bg: 'bg-red-500',
        text: 'text-red-600',
        border: 'border-red-300'
      },
      unknown: {
        bg: 'bg-gray-400',
        text: 'text-gray-500',
        border: 'border-gray-300'
      }
    };
    
    return colors[status as keyof typeof colors]?.[type] || colors.unknown[type];
  };

  const getStatusMessage = (status: string, percentage: number) => {
    switch (status) {
      case 'safe':
        return 'Context usage is healthy';
      case 'warning':
        return 'Approaching context limit - consider wrapping up complex tasks';
      case 'critical':
        return 'Critical context usage - create new session to continue';
      default:
        return 'Context usage unknown';
    }
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`;
    } else if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" title={getStatusMessage(usage.status, usage.percentage)}>
          <div className={`w-full h-full rounded-full ${getStatusColor(usage.status)}`} />
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {usage.percentage.toFixed(0)}%
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Progress Bar */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
            Context Usage
          </span>
          {showDetails && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {formatTokens(usage.current)} / {formatTokens(usage.limit)}
            </span>
          )}
        </div>
        
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${getStatusColor(usage.status)}`}
            style={{ width: `${Math.min(usage.percentage, 100)}%` }}
          />
          
          {/* Warning thresholds */}
          <div 
            className="absolute top-0 w-px h-full bg-yellow-400 opacity-50"
            style={{ left: '70%' }}
            title="Warning threshold (70%)"
          />
          <div 
            className="absolute top-0 w-px h-full bg-red-400 opacity-50"
            style={{ left: '85%' }}
            title="Critical threshold (85%)"
          />
        </div>
      </div>

      {/* Status Indicator */}
      <div className="flex items-center gap-2">
        <div 
          className={`w-3 h-3 rounded-full ${getStatusColor(usage.status)} flex-shrink-0`}
          title={getStatusMessage(usage.status, usage.percentage)}
        />
        
        {showDetails && (
          <span className={`text-sm font-medium ${getStatusColor(usage.status, 'text')}`}>
            {usage.percentage.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Warning Icon for Critical Status */}
      {usage.status === 'critical' && (
        <div className="text-red-500 animate-pulse" title="Context limit critical!">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path 
              fillRule="evenodd" 
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" 
              clipRule="evenodd" 
            />
          </svg>
        </div>
      )}
    </div>
  );
}

// Helper function to calculate context usage
export function calculateContextUsage(totalTokens: number, modelLimit?: number): ContextUsage {
  // Default limits for different models
  const defaultLimits = {
    'claude-sonnet-4': 200000,
    'claude-opus-4': 200000,
    'claude-haiku-4': 200000,
    default: 200000
  };

  const limit = modelLimit || defaultLimits.default;
  const percentage = (totalTokens / limit) * 100;
  
  let status: ContextUsage['status'];
  if (percentage < 70) {
    status = 'safe';
  } else if (percentage < 85) {
    status = 'warning';
  } else {
    status = 'critical';
  }

  return {
    current: totalTokens,
    limit,
    percentage,
    status
  };
}