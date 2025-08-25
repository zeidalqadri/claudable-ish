/**
 * Context Warning Component
 * Displays smart warnings and notifications about context usage
 */
import React, { useState, useEffect } from 'react';
import { ContextUsage } from './ContextIndicator';

interface ContextWarningProps {
  usage: ContextUsage | null;
  recommendations: string[];
  onCreateNewSession?: () => void;
  onDismiss?: () => void;
  autoShow?: boolean;
}

export function ContextWarning({
  usage,
  recommendations,
  onCreateNewSession,
  onDismiss,
  autoShow = true
}: ContextWarningProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);
  const [lastWarningLevel, setLastWarningLevel] = useState<string | null>(null);

  // Auto-show warnings based on usage
  useEffect(() => {
    if (!usage || !autoShow) return;

    const shouldShow = () => {
      // Don't show if already dismissed for this level
      if (isDismissed && lastWarningLevel === usage.status) {
        return false;
      }

      // Show for warning and critical levels
      if (usage.status === 'warning' || usage.status === 'critical') {
        return true;
      }

      return false;
    };

    if (shouldShow()) {
      setIsVisible(true);
      setLastWarningLevel(usage.status);
      setIsDismissed(false);
    } else if (usage.status === 'safe') {
      // Auto-hide when usage goes back to safe
      setIsVisible(false);
      setIsDismissed(false);
      setLastWarningLevel(null);
    }
  }, [usage, autoShow, isDismissed, lastWarningLevel]);

  const handleDismiss = () => {
    setIsVisible(false);
    setIsDismissed(true);
    onDismiss?.();
  };

  const handleCreateSession = () => {
    onCreateNewSession?.();
    handleDismiss();
  };

  if (!isVisible || !usage) {
    return null;
  }

  const getWarningConfig = (status: string) => {
    switch (status) {
      case 'critical':
        return {
          title: '🚨 Critical Context Usage',
          bgColor: 'bg-red-50 dark:bg-red-900/20',
          borderColor: 'border-red-200 dark:border-red-800',
          textColor: 'text-red-800 dark:text-red-200',
          buttonColor: 'bg-red-600 hover:bg-red-700 text-white',
          icon: (
            <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          )
        };
      case 'warning':
        return {
          title: '⚠️ Context Usage Warning',
          bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
          borderColor: 'border-yellow-200 dark:border-yellow-800',
          textColor: 'text-yellow-800 dark:text-yellow-200',
          buttonColor: 'bg-yellow-600 hover:bg-yellow-700 text-white',
          icon: (
            <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          )
        };
      default:
        return null;
    }
  };

  const config = getWarningConfig(usage.status);
  if (!config) return null;

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`;
    } else if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  return (
    <div className={`mx-6 mb-4 p-4 rounded-lg border ${config.bgColor} ${config.borderColor}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          {config.icon}
          
          <div className="flex-1">
            <h3 className={`font-medium ${config.textColor} mb-2`}>
              {config.title}
            </h3>
            
            <div className={`text-sm ${config.textColor} mb-3 space-y-1`}>
              <div className="flex items-center gap-4">
                <span>
                  <strong>{formatTokens(usage.current)}</strong> of{' '}
                  <strong>{formatTokens(usage.limit)}</strong> tokens used
                </span>
                <span className="px-2 py-1 bg-white/50 dark:bg-gray-800/50 rounded text-xs">
                  {usage.percentage.toFixed(1)}%
                </span>
              </div>
            </div>

            {recommendations.length > 0 && (
              <ul className={`text-sm ${config.textColor} space-y-1 mb-4`}>
                {recommendations.slice(0, 3).map((rec, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="inline-block w-1 h-1 bg-current rounded-full mt-2 flex-shrink-0" />
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex items-center gap-3">
              {onCreateNewSession && usage.status === 'critical' && (
                <button
                  onClick={handleCreateSession}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${config.buttonColor} transition-colors`}
                >
                  Create New Session
                </button>
              )}
              
              <button
                onClick={handleDismiss}
                className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>

        <button
          onClick={handleDismiss}
          className={`p-1 rounded-md ${config.textColor} hover:bg-black/5 dark:hover:bg-white/5 transition-colors`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// Hook to manage warning state
export function useContextWarnings(usage: ContextUsage | null, recommendations: string[]) {
  const [dismissedWarnings, setDismissedWarnings] = useState<Set<string>>(new Set());
  const [lastNotificationTime, setLastNotificationTime] = useState<number>(0);

  const shouldShowWarning = (currentUsage: ContextUsage | null) => {
    if (!currentUsage) return false;
    
    const warningKey = `${currentUsage.status}-${Math.floor(currentUsage.percentage / 10) * 10}`;
    
    if (dismissedWarnings.has(warningKey)) {
      return false;
    }

    // Rate limit notifications (max once per minute)
    const now = Date.now();
    if (now - lastNotificationTime < 60000) {
      return false;
    }

    return currentUsage.status === 'warning' || currentUsage.status === 'critical';
  };

  const dismissWarning = (currentUsage: ContextUsage | null) => {
    if (!currentUsage) return;
    
    const warningKey = `${currentUsage.status}-${Math.floor(currentUsage.percentage / 10) * 10}`;
    setDismissedWarnings(prev => new Set([...prev, warningKey]));
    setLastNotificationTime(Date.now());
  };

  const showNotification = (currentUsage: ContextUsage | null) => {
    if (!currentUsage || typeof window === 'undefined') return;

    // Browser notification (if permission granted)
    if (Notification.permission === 'granted') {
      const title = currentUsage.status === 'critical' 
        ? 'Critical Context Usage' 
        : 'Context Usage Warning';
      
      const body = `${currentUsage.percentage.toFixed(1)}% of context limit used. Consider creating a new session.`;
      
      new Notification(title, {
        body,
        icon: '/favicon.png',
        tag: 'context-warning', // Prevent duplicate notifications
      });
    }

    setLastNotificationTime(Date.now());
  };

  // Auto-request notification permission
  React.useEffect(() => {
    if (typeof window !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  return {
    shouldShowWarning: shouldShowWarning(usage),
    dismissWarning: () => dismissWarning(usage),
    showNotification: () => showNotification(usage),
    dismissedWarnings
  };
}