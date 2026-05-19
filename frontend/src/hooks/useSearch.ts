/**
 * Search hook with debounced query
 * 디바운스된 검색 쿼리 훅
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { searchGames } from '@/lib/api';

/**
 * Debounce a value
 * 입력값을 디바운스 처리
 */
function useDebounce<T>(value: T, delay: number = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

/**
 * Search games with debouncing
 * 디바운스 적용된 게임 검색 훅
 */
export function useSearch(query: string, limit: number = 12) {
  const debouncedQuery = useDebounce(query, 400);

  return useQuery({
    queryKey: ['search', debouncedQuery, limit],
    queryFn: () => searchGames(debouncedQuery, limit),
    enabled: debouncedQuery.trim().length > 0,
    staleTime: 1000 * 60 * 2,
  });
}
