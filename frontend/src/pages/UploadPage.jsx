import React, { useState, useRef, useCallback } from 'react'

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export default function UploadPage({ onProcess, onProcessText }) {
    const [mode, setMode] = useState('audio') // 'audio' | 'text'
    const [file, setFile] = useState(null)
    const [text, setText] = useState('')
    const [isDragging, setIsDragging] = useState(false)
    const inputRef = useRef(null)

    const handleFiles = useCallback((files) => {
        const f = files[0]
        if (!f) return
        const ext = f.name.split('.').pop().toLowerCase()
        const allowed = ['mp3', 'wav', 'ogg', 'm4a', 'webm', 'flac', 'aac']
        if (!allowed.includes(ext)) {
            alert(`Formato não suportado: .${ext}\nUse: ${allowed.map(e => '.' + e).join(', ')}`)
            return
        }
        setFile(f)
    }, [])

    const handleDrop = useCallback((e) => {
        e.preventDefault()
        setIsDragging(false)
        handleFiles(e.dataTransfer.files)
    }, [handleFiles])

    const handleDragOver = useCallback((e) => {
        e.preventDefault()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e) => {
        e.preventDefault()
        setIsDragging(false)
    }, [])

    const handleClick = () => {
        inputRef.current?.click()
    }

    const handleInputChange = (e) => {
        handleFiles(e.target.files)
    }

    const removeFile = (e) => {
        e.stopPropagation()
        setFile(null)
        if (inputRef.current) inputRef.current.value = ''
    }

    const handleSubmit = () => {
        if (mode === 'audio' && file) {
            onProcess(file)
        } else if (mode === 'text' && text.trim()) {
            onProcessText(text)
        }
    }

    const canSubmit = mode === 'audio' ? !!file : text.trim().length > 0

    return (
        <div className="upload-page">
            <div className="upload-hero">
                <h2 className="upload-hero__title">
                    Mapeie processos com <span>Inteligência Artificial</span>
                </h2>
                <p className="upload-hero__desc">
                    Envie o áudio da entrevista ou cole o texto transcrito da rotina do setor.
                    Nossa IA irá analisar, otimizar e gerar o fluxograma BPMN automaticamente.
                </p>
            </div>

            {/* Mode Toggle */}
            <div className="mode-toggle">
                <button
                    className={`mode-toggle__btn ${mode === 'audio' ? 'mode-toggle__btn--active' : ''}`}
                    onClick={() => setMode('audio')}
                >
                    🎙️ Enviar Áudio
                </button>
                <button
                    className={`mode-toggle__btn ${mode === 'text' ? 'mode-toggle__btn--active' : ''}`}
                    onClick={() => setMode('text')}
                >
                    📝 Colar Texto
                </button>
            </div>

            {mode === 'audio' ? (
                /* ── Audio Upload ──────────────────────────────────────── */
                <div
                    className={`dropzone ${isDragging ? 'dropzone--active' : ''} ${file ? 'dropzone--has-file' : ''}`}
                    onClick={handleClick}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                >
                    <input
                        ref={inputRef}
                        type="file"
                        accept="audio/*"
                        onChange={handleInputChange}
                        style={{ display: 'none' }}
                    />

                    {!file ? (
                        <>
                            <div className="dropzone__icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                                    <line x1="12" y1="19" x2="12" y2="23" />
                                    <line x1="8" y1="23" x2="16" y2="23" />
                                </svg>
                            </div>
                            <div className="dropzone__text">
                                <div className="dropzone__text-primary">
                                    {isDragging ? 'Solte o arquivo aqui' : 'Arraste o áudio ou clique para selecionar'}
                                </div>
                                <div className="dropzone__text-secondary">
                                    MP3, WAV, OGG, M4A, WebM, FLAC, AAC
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="dropzone__file-info">
                            <span style={{ fontSize: '24px' }}>🎙️</span>
                            <div>
                                <div className="dropzone__file-name">{file.name}</div>
                                <div className="dropzone__file-size">{formatFileSize(file.size)}</div>
                            </div>
                            <button className="dropzone__remove" onClick={removeFile} title="Remover arquivo">
                                ✕
                            </button>
                        </div>
                    )}
                </div>
            ) : (
                /* ── Text Input ────────────────────────────────────────── */
                <div className="text-input-area">
                    <textarea
                        className="text-input-area__textarea"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Cole aqui a transcrição da entrevista de mapeamento do setor..."
                        rows={12}
                    />
                    <div className="text-input-area__footer">
                        <span className="text-input-area__count">
                            {text.length > 0 ? `${text.length.toLocaleString()} caracteres` : ''}
                        </span>
                    </div>
                </div>
            )}

            <button
                className="btn btn--primary btn--lg"
                disabled={!canSubmit}
                onClick={handleSubmit}
            >
                <svg className="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Iniciar Mapeamento com IA
            </button>
        </div>
    )
}
