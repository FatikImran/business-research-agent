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

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
          previous_messages: messages
        })
      });

      const data: ApiResponse = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || data.response || `API error: ${response.status}`);
      }

      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        timestamp: data.timestamp
      }]);

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
    setError('');
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
      <div className={styles.header}>
        <h1>🔍 Business Research Assistant</h1>
        <p>Multi-Agent AI System • Powered by LangGraph • Deployed on Vercel</p>
      </div>

      <div className={styles.chatContainer}>
        <div className={styles.messagesBox}>
          {messages.length === 0 ? (
            <div className={styles.emptyState}>
              <p className={styles.emptyIcon}>👋</p>
              <h2>Welcome!</h2>
              <p>Ask questions about any company and our AI research team will investigate.</p>
              <div className={styles.examples}>
                <p className={styles.label}>Try asking:</p>
                <ul>
                  <li>"Tell me about Apple Inc"</li>
                  <li>"What about their market position?"</li>
                  <li>"Research Google's AI initiatives"</li>
                </ul>
              </div>
              <p className={styles.features}>
                💡 Features: Real web search • Multi-agent analysis • Confidence scoring
              </p>
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
              <span>⏳ Researching</span>
              <span className={styles.dots}>
                <span>.</span><span>.</span><span>.</span>
              </span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className={styles.inputBox}>
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
            {loading ? '⏳' : '📤'}
          </button>
          <button 
            type="button"
            onClick={downloadChat}
            disabled={messages.length === 0}
            className={styles.downloadBtn}
            title="Download conversation"
          >
            💾
          </button>
          <button 
            type="button"
            onClick={clearChat}
            disabled={messages.length === 0}
            className={styles.clearBtn}
            title="Clear chat"
          >
            🗑️
          </button>
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
