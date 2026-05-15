'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './page.module.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ApiResponse {
  success: boolean;
  response: string;
  confidence?: number;
  clarification_needed?: boolean;
  clarification_prompt?: string;
  timestamp: string;
  execution_time_ms: number;
  error?: string;
}

function buildDebugMessage(response: Response, rawBody: string) {
  const headers = [
    ['Status', `${response.status} ${response.statusText}`],
    ['Content-Type', response.headers.get('content-type') || 'unknown'],
    ['Response-Mode', response.headers.get('x-response-mode') || 'missing'],
    ['Debug-Status', response.headers.get('x-debug-status') || 'missing'],
    ['Debug-Query', response.headers.get('x-debug-query') || 'missing'],
    ['Debug-Preview', response.headers.get('x-debug-preview') || 'missing'],
  ]
    .map(([label, value]) => `${label}: ${value}`)
    .join('\n');

  const bodyPreview = rawBody.trim().slice(0, 600) || '[empty body]';

  return [
    'The server returned HTML or another non-JSON response.',
    headers,
    'Body preview:',
    bodyPreview,
  ].join('\n\n');
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationState, setConversationState] = useState<any>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const starterPrompts = [
    'Give me a market overview of Apple.',
    'Analyze Tesla’s competitive position.',
    'Research Google’s AI strategy and recent moves.',
    'What are the latest growth signals for NVIDIA?'
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setError('');
    setLoading(true);

    // Add user message to chat
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    }]);

    try {
      const response = await fetch('/api/research', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: userMessage,
          previous_messages: messages,
          state: conversationState,
        })
      });

      const contentType = response.headers.get('content-type') || '';
      const rawBody = await response.text();
      let data: ApiResponse;

      if (contentType.includes('application/json')) {
        try {
          data = JSON.parse(rawBody) as ApiResponse;
        } catch {
          throw new Error(buildDebugMessage(response, rawBody));
        }
      } else {
        throw new Error(buildDebugMessage(response, rawBody));
      }

      if (!response.ok || !data.success) {
        throw new Error(data.error || data.response || `API error: ${response.status}`);
      }

      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        timestamp: data.timestamp
      }]);

      if (data.state) {
        setConversationState(data.state);
      }

      // Show clarification if needed
      if (data.clarification_needed && data.clarification_prompt) {
        setError(`ℹ️ ${data.clarification_prompt}`);
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`❌ ${errorMessage}`);
      console.error('Research error:', err);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setConversationState(null);
    setError('');
  };

  const usePrompt = (prompt: string) => {
    if (loading) return;
    setInput(prompt);
  };

  const downloadChat = () => {
    if (messages.length === 0) return;
    
    const chatText = messages
      .map(msg => `${msg.role.toUpperCase()}: ${msg.content}`)
      .join('\n\n---\n\n');
    
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(chatText));
    element.setAttribute('download', `research-${new Date().toISOString().slice(0,10)}.txt`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <main className={styles.container}>
      <div className={styles.backgroundGlow} aria-hidden="true" />
      <div className={styles.backgroundGrid} aria-hidden="true" />

      <div className={styles.header}>
        <div className={styles.headerTopRow}>
          <div className={styles.kicker}>Caramel Intelligence Suite</div>
          <div className={styles.livePill}>Live web research</div>
        </div>
        <h1>Business Research Assistant</h1>
        <p>
          A modern multi-agent workspace for fast company research, market context,
          and decision-ready insights.
        </p>

        <div className={styles.heroStats}>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Stack</span>
            <strong>LangGraph + Gemini</strong>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Search</span>
            <strong>DuckDuckGo intelligence</strong>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Output</span>
            <strong>Concise, sourced answers</strong>
          </div>
        </div>
      </div>

      <div className={styles.chatContainer}>
        <div className={styles.toolbar}>
          <div>
            <span className={styles.toolbarLabel}>Quick prompts</span>
            <p>Tap a prompt or type your own question.</p>
          </div>
          <div className={styles.toolbarActions}>
            <button type="button" className={styles.ghostBtn} onClick={downloadChat} disabled={messages.length === 0}>
              Download chat
            </button>
            <button type="button" className={styles.ghostBtn} onClick={clearChat} disabled={messages.length === 0}>
              Clear all
            </button>
          </div>
        </div>

        <div className={styles.promptRow}>
          {starterPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className={styles.promptChip}
              onClick={() => usePrompt(prompt)}
              disabled={loading}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className={styles.messagesBox}>
          {messages.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyBadge}>Ready when you are</div>
              <h2>Start a research brief</h2>
              <p>
                Ask about any company, competitor, trend, or strategic move and the
                assistant will gather and synthesize the most relevant context.
              </p>
              <div className={styles.emptyPanel}>
                <p className={styles.label}>Good first questions</p>
                <ul>
                  <li>Company overview and current strategy</li>
                  <li>Competitive positioning and risks</li>
                  <li>Recent AI, product, or expansion moves</li>
                </ul>
              </div>
              <div className={styles.featureRow}>
                <span>Real web search</span>
                <span>Multi-agent analysis</span>
                <span>Confidence scoring</span>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`${styles.message} ${styles[msg.role]}`}>
                <div className={styles.role}>
                  {msg.role === 'user' ? '👤 You' : '🤖 Assistant'}
                </div>
                <div className={styles.content}>{msg.content}</div>
                <div className={styles.timestamp}>
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
          {error && (
            <div className={`${styles.error} ${error.startsWith('ℹ️') ? styles.info : ''}`}>
              <strong>{error}</strong>
            </div>
          )}
          {loading && (
            <div className={styles.loading}>
              <span>Researching</span>
              <span className={styles.dots}>
                <span>.</span><span>.</span><span>.</span>
              </span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className={styles.inputBox}>
          <div className={styles.inputShell}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about any company..."
              disabled={loading}
              maxLength={1000}
              className={styles.input}
              autoFocus
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className={styles.sendBtn}
              title="Send query"
            >
              {loading ? 'Working…' : 'Research'}
            </button>
          </div>
          <p className={styles.inputHint}>
            Ask for a summary, competitive analysis, recent news, or a strategy brief.
          </p>
        </form>
      </div>

      <div className={styles.footer}>
        <p>
          Built with <strong>LangGraph</strong> • 
          Powered by <strong>Google Gemini + DuckDuckGo</strong> • 
          Deployed on <strong>Vercel</strong>
        </p>
      </div>
    </main>
  );
}
