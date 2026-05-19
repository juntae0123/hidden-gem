/**
 * Game detail page
 * 게임 상세 페이지
 */
'use client';

import { useParams } from 'next/navigation';
import { GameDetail } from '@/components/game/GameDetail';
import { RecommendList } from '@/components/game/RecommendList';

/**
 * Game detail route component
 * /game/[appId] 라우트 컴포넌트
 */
export default function GameDetailPage() {
  const params = useParams<{ appId: string }>();
  const appId = Number(params?.appId);

  if (Number.isNaN(appId)) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        잘못된 게임 ID 입니다.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <GameDetail appId={appId} />
      <RecommendList appId={appId} count={6} />
    </div>
  );
}
