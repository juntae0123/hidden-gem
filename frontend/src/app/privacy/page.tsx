/**
 * Privacy Policy page.
 * 개인정보처리방침 페이지 (PIPA + GDPR 준수).
 */
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '개인정보처리방침 · Hidden Gem',
  description: 'Hidden Gem 개인정보처리방침',
};

export default function PrivacyPage() {
  const lastUpdated = '2026년 6월 1일';

  return (
    <article className="max-w-3xl mx-auto py-8">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
        개인정보처리방침
      </h1>
      <p className="text-sm text-zinc-500 mb-8">최종 수정일: {lastUpdated}</p>

      <Section title="1. 수집하는 개인정보">
        <p>Hidden Gem(이하 &ldquo;서비스&rdquo;)은 다음 정보를 수집합니다:</p>
        <ul className="list-disc pl-5 space-y-1 mt-2">
          <li><strong>Google 로그인 시</strong>: 이메일, 프로필 이름</li>
          <li><strong>Steam 연동 시</strong>: Steam ID, 공개 라이브러리 정보</li>
          <li><strong>서비스 이용 시</strong>: 검색어, 클릭한 게임, 세션 정보 (익명)</li>
        </ul>
      </Section>

      <Section title="2. 개인정보 이용 목적">
        <ul className="list-disc pl-5 space-y-1">
          <li>맞춤형 게임 추천 제공</li>
          <li>서비스 개선 및 통계 분석 (익명화)</li>
          <li>로그인 및 계정 관리</li>
        </ul>
      </Section>

      <Section title="3. 개인정보 보유 기간">
        <p>
          회원 탈퇴 시 즉시 파기합니다. 단, 관련 법령에 따라 보존이 필요한 경우
          해당 기간 동안 보관합니다.
        </p>
      </Section>

      <Section title="4. 개인정보 제3자 제공">
        <p>
          서비스는 이용자의 개인정보를 제3자에게 제공하지 않습니다.
          단, 익명화·통계화된 데이터는 서비스 개선 및 시장 분석 목적으로
          활용될 수 있습니다 (개인 식별 불가능).
        </p>
      </Section>

      <Section title="5. 분석 도구">
        <p>
          서비스는 익명 방문 통계 분석을 위해 자체 호스팅 Umami Analytics를
          사용합니다. 수집된 데이터는 외부로 전송되지 않으며, 개인을 식별하지
          않습니다.
        </p>
      </Section>

      <Section title="6. 이용자의 권리 (GDPR Article 17)">
        <p>이용자는 다음 권리를 가집니다:</p>
        <ul className="list-disc pl-5 space-y-1 mt-2">
          <li><strong>열람권</strong>: 자신의 개인정보 확인</li>
          <li><strong>삭제권</strong>: 계정 및 모든 데이터 삭제 요청</li>
          <li><strong>이동권</strong>: 데이터 내보내기 요청</li>
        </ul>
        <p className="mt-3">
          데이터 삭제는{' '}
          <a
            href="mailto:privacy@hiddengem.io"
            className="text-purple-600 hover:underline"
          >
            privacy@hiddengem.io
          </a>
          로 요청하실 수 있습니다.
        </p>
      </Section>

      <Section title="7. 쿠키 사용">
        <p>
          서비스는 로그인 유지 및 분석을 위해 쿠키를 사용합니다.
          쿠키 동의는 첫 방문 시 배너를 통해 선택할 수 있으며,
          브라우저 설정에서 거부할 수 있습니다.
        </p>
      </Section>

      <Section title="8. 개인정보 보호책임자">
        <p>
          문의:{' '}
          <a href="mailto:privacy@hiddengem.io" className="text-purple-600 hover:underline">
            privacy@hiddengem.io
          </a>
        </p>
      </Section>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200 mb-2">
        {title}
      </h2>
      <div className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
        {children}
      </div>
    </section>
  );
}
