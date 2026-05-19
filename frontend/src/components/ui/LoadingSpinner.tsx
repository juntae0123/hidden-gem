/**
 * Loading spinner component
 * 로딩 인디케이터 컴포넌트
 */
import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  label?: string;
}

/**
 * Animated spinner
 * 회전 애니메이션 스피너
 */
export function LoadingSpinner({
  size = 'md',
  className,
  label,
}: LoadingSpinnerProps) {
  const sizeClass = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-[3px]',
  }[size];

  return (
    <div
      className={cn('flex flex-col items-center justify-center gap-3', className)}
    >
      <div
        className={cn(
          'rounded-full animate-spin',
          'border-purple-200 border-t-purple-600',
          'dark:border-zinc-800 dark:border-t-purple-500',
          sizeClass
        )}
        role="status"
        aria-label="loading"
      />
      {label && (
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {label}
        </span>
      )}
    </div>
  );
}
