/**
 * Terms of Service page.
 * 이용약관 페이지.
 */
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '이용약관 · Hidden Gem',
  description: 'Hidden Gem 이용약관',
};

export default function TermsPage() {
  const lastUpdated = '2026년 6월 1일';

  return (
    <article className="max-w-3xl mx-auto py-8">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
        이용약관
      </h1>
      <p className="text-sm text-zinc-500 mb-8">최종 수정일: {lastUpdated}</p>

      <Section title="제1조 (목적)">
        <p>
          본 약관은 Hidden Gem(이하 &ldquo;서비스&rdquo;)이 제공하는
          게임 추천 서비스의 이용 조건 및 절차를 규정합니다.
        </p>
      </Section>

      <Section title="제2조 (서비스 내용)">
        <ul className="list-disc pl-5 space-y-1">
          <li>AI 기반 게임 추천</li>
          <li>자연어 게임 검색</li>
          <li>취향 분석 및 맞춤 추천</li>
          <li>게임 정보 제공</li>
        </ul>
      </Section>

      <Section title="제3조 (게임 정보의 출처)">
        <p>
          서비스에서 제공하는 게임 정보는 Steam 등 공개 데이터를 기반으로 하며,
          게임 설명은 AI가 생성한 요약입니다. 정확한 정보는 각 게임의
          공식 스토어 페이지를 확인하시기 바랍니다.
        </p>
      </Section>

      <Section title="제4조 (어필리에이트 고지)">
        <p>
          서비스의 일부 링크는 어필리에이트 링크일 수 있으며,
          이를 통한 구매 시 서비스가 일정 수수료를 받을 수 있습니다.
          이는 이용자의 구매 가격에 영향을 주지 않습니다.
        </p>
      </Section>

      <Section title="제5조 (이용자의 의무)">
        <ul className="list-disc pl-5 space-y-1">
          <li>타인의 권리를 침해하지 않을 것</li>
          <li>서비스를 부정한 목적으로 이용하지 않을 것</li>
          <li>자동화 도구로 과도한 요청을 보내지 않을 것</li>
        </ul>
      </Section>

      <Section title="제6조 (면책)">
        <p>
          서비스는 추천 결과의 정확성을 보장하지 않으며,
          이용자의 게임 구매 결정에 대한 책임을 지지 않습니다.
        </p>
      </Section>

      <Section title="제7조 (약관 변경)">
        <p>
          서비스는 필요 시 약관을 변경할 수 있으며,
          변경 시 서비스 내 공지합니다.
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
