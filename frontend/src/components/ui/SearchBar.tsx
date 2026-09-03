/**
 * Animated search bar with rotating placeholders
 * 자동 순환 placeholder를 가진 검색바
 */
'use client';

import { useEffect, useState, useRef, FormEvent } from 'react';
import { Search } from 'lucide-react';
import { SEARCH_PLACEHOLDERS, SEARCH_CHIPS } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit?: (v: string) => void;
  showChips?: boolean;
  className?: string;
  autoFocus?: boolean;
}

/**
 * Search bar with hint chips and rotating placeholder
 * 힌트 칩 + 자동 순환 placeholder가 포함된 검색바
 */
export function SearchBar({
  value,
  onChange,
  onSubmit,
  showChips = true,
  className,
  autoFocus = false,
}: SearchBarProps) {
  const [phIdx, setPhIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // placeholder 자동 순환 / Auto-rotate placeholder (Strict Mode safe)
  useEffect(() => {
    let idx = 0;
    const t = setInterval(() => {
      idx = (idx + 1) % SEARCH_PLACEHOLDERS.length;
      setPhIdx(idx);
    }, 2800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  /**
   * Handle form submit
   * 폼 제출 핸들러
   */
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (onSubmit) onSubmit(value);
  };

  /**
   * Handle chip click — set input value and trigger search
   * 칩 클릭 시 input 자동 입력 + 검색 트리거
   */
  const handleChipClick = (chip: string) => {
    onChange(chip);
    if (onSubmit) onSubmit(chip);
    inputRef.current?.focus();
  };

  return (
    <div className={cn('w-full', className)}>
      <form onSubmit={handleSubmit} className="w-full">
        <div
          className={cn(
            'flex items-center gap-3 px-5 py-3.5 w-full',
            'bg-white dark:bg-zinc-900',
            'border border-zinc-200 dark:border-zinc-800',
            'rounded-xl shadow-sm',
            'focus-within:border-purple-500 focus-within:shadow-md',
            'transition-all'
          )}
        >
          <Search className="w-4 h-4 text-zinc-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={SEARCH_PLACEHOLDERS[phIdx]}
            className={cn(
              'flex-1 bg-transparent outline-none',
              'text-sm text-zinc-900 dark:text-zinc-100',
              'placeholder:text-zinc-400 dark:placeholder:text-zinc-500'
            )}
          />
        </div>
      </form>

      {showChips && (
        <div className="mt-4">
          <div className="text-[11px] text-zinc-400 dark:text-zinc-500 mb-2">
            이렇게도 검색해보세요
          </div>
          <div className="flex flex-wrap gap-2">
            {SEARCH_CHIPS.map((chip, i) => {
              const isLong = chip.label.length > 14;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleChipClick(chip.query)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-[12px]',
                    'border transition-all',
                    'hover:border-purple-400 hover:text-purple-600',
                    isLong
                      ? 'bg-purple-50 dark:bg-purple-950/20 border-purple-200/60 dark:border-purple-900/40 text-purple-700 dark:text-purple-300'
                      : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400'
                  )}
                >
                  {chip.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}