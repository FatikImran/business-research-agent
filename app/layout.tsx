import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Business Research Assistant',
  description: 'Multi-agent AI system for business research powered by LangGraph, Google Gemini, and DuckDuckGo. Deployed on Vercel.',
  keywords: 'business research, AI, multi-agent, langgraph, gemini, research assistant',
  viewport: 'width=device-width, initial-scale=1',
  authors: [{ name: 'Synapse AI Solutions' }],
  openGraph: {
    title: 'Business Research Assistant',
    description: 'Multi-agent AI system for business research',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="theme-color" content="#667eea" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>{children}</body>
    </html>
  );
}
