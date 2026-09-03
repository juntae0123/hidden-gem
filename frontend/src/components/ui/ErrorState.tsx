/**
 * Common error state component
 * 공통 에러 상태 컴포넌트 — 네트워크/404/일반 에러 자동 감지
 */
'use client';

import { RefreshCw, AlertTriangle, WifiOff, SearchX } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  error?: Error | null;
  onRetry?: () => void;
  variant?: 'inline' | 'page' | 'card';
  title?: string;
  description?: string;
  type?: 'network' | 'not-found' | 'generic';
  className?: string;
}

function isNetworkError(error?: Error | null): boolean {
  if (!error) return false;
  const msg = error.message?.toLowerCase() ?? '';
  return (
    msg.includes('network') ||
    msg.includes('timeout') ||
    msg.includes('fetch') ||
    msg.includes('connection') ||
    msg.includes('econnrefused')
  );
}

/**
 * Error state with retry button — auto-detects error type.
 * 재시도 버튼이 있는 에러 상태 — 에러 타입 자동 감지.
 */
export function ErrorState({
  error,
  onRetry,
  variant = 'inline',
  title,
  description,
  type,
  className,
}: ErrorStateProps) {
  const detectedType = type || (isNetworkError(error) ? 'network' : 'generic');

  const config = {
    network: {
      Icon:        WifiOff,
      defaultTitle: '연결에 문제가 있어요',
      defaultDesc:  '인터넷 연결을 확인하고 다시 시도해주세요',
      iconColor:   'text-orange-600',
      iconBg:      'bg-orange-50 dark:bg-orange-950/30',
    },
    'not-found': {
      Icon:        SearchX,
      defaultTitle: '결과를 찾을 수 없어요',
      defaultDesc:  '다른 검색어로 시도해보세요',
      iconColor:   'text-zinc-500',
      iconBg:      'bg-zinc-100 dark:bg-zinc-800',
    },
    generic: {
      Icon:        AlertTriangle,
      defaultTitle: '문제가 발생했어요',
      defaultDesc:  '잠시 후 다시 시도해주세요',
      iconColor:   'text-red-600',
      iconBg:      'bg-red-50 dark:bg-red-950/30',
    },
  }[detectedType];

  const { Icon } = config;

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 text-center',
        variant === 'page'   && 'py-20 px-4',
        variant === 'inline' && 'py-12 px-4',
        variant === 'card'   && 'py-8 px-4 rounded-xl border border-zinc-200 dark:border-zinc-800',
        className
      )}
    >
      <div className={cn('w-12 h-12 rounded-full flex items-center justify-center', config.iconBg)}>
        <Icon className={cn('w-6 h-6', config.iconColor)} />
      </div>

      <div className="max-w-sm">
        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {title || config.defaultTitle}
        </h3>
        <p className="mt-1 text-xs text-zinc-500 leading-relaxed">
          {description || config.defaultDesc}
        </p>
        {error && process.env.NODE_ENV === 'development' && (
          <details className="mt-3 text-left">
            <summary className="text-[10px] text-zinc-400 cursor-pointer">에러 상세 (개발자용)</summary>
            <pre className="mt-1 p-2 bg-zinc-100 dark:bg-zinc-900 rounded text-[10px] text-red-600 overflow-auto max-h-32">
              {error.message}
            </pre>
          </details>
        )}
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            'inline-flex items-center gap-1.5 px-4 py-2 rounded-md',
            'bg-purple-600 hover:bg-purple-700',
            'text-white text-xs font-medium',
            'transition-colors shadow-sm'
          )}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          다시 시도
        </button>
      )}
    </div>
  );
}
