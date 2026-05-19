import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ 
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter"
});

export const metadata: Metadata = {
  title: "Hidden Gem Finder | AI 게임 추천",
  description: "AI가 5,000+ 게임을 분석하여 당신의 숨겨진 인생 명작을 발굴합니다.",
  keywords: ["게임 추천", "인디 게임", "숨겨진 명작", "AI 추천"],
  authors: [{ name: "Hidden Gem Team" }],
  openGraph: {
    title: "Hidden Gem Finder",
    description: "AI가 당신의 인생 명작을 0.1초 만에 발굴합니다",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={inter.variable}>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="theme-color" content="#0a0a0a" />
      </head>
      <body className={`${inter.className} antialiased`}>
        {children}
      </body>
    </html>
  );
}
