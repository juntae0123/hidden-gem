import type { Metadata } from "next";
import { Inter } from "next/font/google"; // Geist 대신 Inter 폰트 사용!
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hidden Gem Finder",
  description: "AI-powered game recommendation system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className={inter.className}>{children}</body>
    </html>
  );
}