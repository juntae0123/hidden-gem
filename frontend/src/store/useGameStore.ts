/**
 * Game-related global store (zustand)
 * 게임 관련 전역 상태 저장소 - 선택된 게임, 필터 등
 */
'use client';

import { create } from 'zustand';

interface GameFilters {
  single: boolean;
  multi: boolean;
  korean: boolean;
  sortBy: 'match' | 'gem' | 'recent' | 'review';
}

interface GameStoreState {
  selectedAppId: number | null;
  filters: GameFilters;
  setSelectedAppId: (id: number | null) => void;
  toggleFilter: (key: keyof Omit<GameFilters, 'sortBy'>) => void;
  setSortBy: (sort: GameFilters['sortBy']) => void;
  resetFilters: () => void;
}

const DEFAULT_FILTERS: GameFilters = {
  single: false,
  multi: false,
  korean: false,
  sortBy: 'match',
};

/**
 * Game store hook
 * 게임 상태 관리 zustand 훅
 */
export const useGameStore = create<GameStoreState>((set) => ({
  selectedAppId: null,
  filters: DEFAULT_FILTERS,
  setSelectedAppId: (id) => set({ selectedAppId: id }),
  toggleFilter: (key) =>
    set((state) => ({
      filters: { ...state.filters, [key]: !state.filters[key] },
    })),
  setSortBy: (sort) =>
    set((state) => ({ filters: { ...state.filters, sortBy: sort } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
}));
