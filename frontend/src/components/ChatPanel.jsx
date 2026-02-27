import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

export default function ChatPanel({ context }) {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [isOpen, setIsOpen] = useState(false)
    const messagesEndRef = useRef(null)

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSend = async () => {
        const userMsg = input.trim()
        if (!userMsg || loading) return

        const newMessages = [...messages, { role: 'user', content: userMsg }]
        setMessages(newMessages)
        setInput('')
        setLoading(true)

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    context,
                    messages: newMessages,
                }),
            })

            if (!res.ok) {
                const err = await res.json().catch(() => ({}))
                throw new Error(err.detail || 'Erro no chat')
            }

            const data = await res.json()
            setMessages([...newMessages, { role: 'assistant', content: data.reply }])
        } catch (e) {
            setMessages([
                ...newMessages,
                { role: 'assistant', content: `❌ Erro: ${e.message}` },
            ])
        } finally {
            setLoading(false)
        }
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    if (!isOpen) {
        return (
            <button className="chat-toggle-btn" onClick={() => setIsOpen(true)}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Conversar com a IA sobre este relatório
            </button>
        )
    }

    return (
        <div className="chat-panel">
            <div className="chat-panel__header">
                <div className="chat-panel__header-info">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                    <span>Chat com a IA</span>
                </div>
                <button className="chat-panel__close" onClick={() => setIsOpen(false)}>✕</button>
            </div>

            <div className="chat-panel__messages">
                {messages.length === 0 && (
                    <div className="chat-panel__empty">
                        <p>Pergunte sobre o relatório, peça esclarecimentos ou solicite modificações.</p>
                        <div className="chat-panel__suggestions">
                            <button onClick={() => setInput('Resuma os principais gargalos identificados')}>
                                Resumir gargalos
                            </button>
                            <button onClick={() => setInput('Quais informações estão faltando no relatório?')}>
                                Informações faltantes
                            </button>
                            <button onClick={() => setInput('Sugira melhorias para este processo')}>
                                Sugerir melhorias
                            </button>
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`chat-msg chat-msg--${msg.role}`}>
                        <div className="chat-msg__avatar">
                            {msg.role === 'user' ? '👤' : '🤖'}
                        </div>
                        <div className="chat-msg__content markdown-body">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="chat-msg chat-msg--assistant">
                        <div className="chat-msg__avatar">🤖</div>
                        <div className="chat-msg__content">
                            <div className="chat-typing">
                                <span></span><span></span><span></span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="chat-panel__input-area">
                <textarea
                    className="chat-panel__input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Pergunte sobre o relatório..."
                    rows={1}
                    disabled={loading}
                />
                <button
                    className="chat-panel__send"
                    onClick={handleSend}
                    disabled={!input.trim() || loading}
                >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                </button>
            </div>
        </div>
    )
}
