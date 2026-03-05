import React, { useState, useRef, useCallback } from 'react'

/**
 * BpmnLinterPage — Upload .bpmn → Validate → Generate DPT
 */
export default function BpmnLinterPage() {
    const [file, setFile] = useState(null)
    const [isDragging, setIsDragging] = useState(false)
    const [loading, setLoading] = useState(false)
    const [loadingDpt, setLoadingDpt] = useState(false)
    const [loadingKpi, setLoadingKpi] = useState(false)
    const [report, setReport] = useState(null)
    const [error, setError] = useState('')
    const inputRef = useRef(null)

    const handleFiles = useCallback((files) => {
        const f = files[0]
        if (!f) return
        const ext = f.name.split('.').pop().toLowerCase()
        if (!['bpmn', 'xml', 'xpdl'].includes(ext)) {
            alert(`Formato não suportado: .${ext}\nUse: .bpmn, .xml ou .xpdl`)
            return
        }
        setFile(f)
        setReport(null)
        setError('')
    }, [])

    const handleDrop = useCallback((e) => {
        e.preventDefault()
        setIsDragging(false)
        handleFiles(e.dataTransfer.files)
    }, [handleFiles])

    const handleSubmit = async () => {
        if (!file) return
        setLoading(true)
        setError('')
        setReport(null)

        try {
            const formData = new FormData()
            formData.append('file', file)
            const res = await fetch('/api/lint-bpmn', { method: 'POST', body: formData })

            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro na validação')
            }

            const json = await res.json()
            setReport(json.report)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    const handleGenerateDpt = async () => {
        if (!file) return
        setLoadingDpt(true)

        try {
            const formData = new FormData()
            formData.append('file', file)
            const res = await fetch('/api/generate-dpt', { method: 'POST', body: formData })

            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro ao gerar DPT')
            }

            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `DPT_${file.name.replace('.bpmn', '')}.docx`
            a.click()
            URL.revokeObjectURL(url)
        } catch (e) {
            alert(e.message)
        } finally {
            setLoadingDpt(false)
        }
    }

    const handleGenerateKpi = async () => {
        if (!file) return
        setLoadingKpi(true)

        try {
            const formData = new FormData()
            formData.append('file', file)
            const res = await fetch('/api/generate-kpi', { method: 'POST', body: formData })

            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro ao gerar Indicadores')
            }

            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `IND_${file.name.replace('.bpmn', '')}.xlsx`
            a.click()
            URL.revokeObjectURL(url)
        } catch (e) {
            alert(e.message)
        } finally {
            setLoadingKpi(false)
        }
    }

    const handleReset = () => {
        setFile(null)
        setReport(null)
        setError('')
        if (inputRef.current) inputRef.current.value = ''
    }

    const canGenerateDpt = report && !report.has_critical

    // Count by level
    const criticalResults = report?.results?.filter(r => r.level === 'CRITICAL') || []
    const errorResults = report?.results?.filter(r => r.level === 'ERROR') || []
    const warnResults = report?.results?.filter(r => r.level === 'WARN') || []
    const infoResults = report?.results?.filter(r => r.level === 'INFO') || []

    return (
        <div className="upload-page">
            <div className="upload-hero">
                <h2 className="upload-hero__title">
                    Validador <span>BPMN</span>, DPT e Indicadores
                </h2>
                <p className="upload-hero__desc">
                    Faça upload do arquivo .bpmn exportado do Bizagi para validar conforme
                    o Manual de Boas Práticas COGEPRO/TJMG, gerar o DPT e a Matriz de Indicadores.
                </p>
            </div>

            {/* Upload Area */}
            {!report && (
                <>
                    <div
                        className={`dropzone ${isDragging ? 'dropzone--active' : ''} ${file ? 'dropzone--has-file' : ''}`}
                        onClick={() => inputRef.current?.click()}
                        onDrop={handleDrop}
                        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
                    >
                        <input
                            ref={inputRef}
                            type="file"
                            accept=".bpmn,.xml,.xpdl"
                            onChange={(e) => handleFiles(e.target.files)}
                            style={{ display: 'none' }}
                        />

                        {!file ? (
                            <>
                                <div className="dropzone__icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                        <polyline points="14 2 14 8 20 8" />
                                        <line x1="16" y1="13" x2="8" y2="13" />
                                        <line x1="16" y1="17" x2="8" y2="17" />
                                    </svg>
                                </div>
                                <div className="dropzone__text">
                                    <div className="dropzone__text-primary">
                                        {isDragging ? 'Solte o arquivo aqui' : 'Arraste o .bpmn ou clique para selecionar'}
                                    </div>
                                    <div className="dropzone__text-secondary">
                                        Arquivos .bpmn, .xml ou .xpdl
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="dropzone__file-info">
                                <span style={{ fontSize: '24px' }}>📄</span>
                                <div>
                                    <div className="dropzone__file-name">{file.name}</div>
                                    <div className="dropzone__file-size">
                                        {(file.size / 1024).toFixed(1)} KB
                                    </div>
                                </div>
                                <button
                                    className="dropzone__remove"
                                    onClick={(e) => { e.stopPropagation(); handleReset() }}
                                    title="Remover"
                                >✕</button>
                            </div>
                        )}
                    </div>

                    <button
                        className="btn btn--primary btn--lg"
                        disabled={!file || loading}
                        onClick={handleSubmit}
                    >
                        {loading ? (
                            <>
                                <span className="step-item__spinner" style={{ width: 16, height: 16 }} />
                                Validando...
                            </>
                        ) : (
                            <>
                                <svg className="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M9 11l3 3L22 4" />
                                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                                </svg>
                                Validar BPMN
                            </>
                        )}
                    </button>
                </>
            )}

            {/* Error */}
            {error && (
                <div className="error-banner">
                    <span className="error-banner__icon">❌</span>
                    <div className="error-banner__content">
                        <div className="error-banner__title">Erro</div>
                        <div className="error-banner__message">{error}</div>
                    </div>
                </div>
            )}

            {/* Report Results */}
            {report && (
                <div className="result-page" style={{ animation: 'fadeInUp 0.5s ease-out' }}>
                    {/* Summary */}
                    <div className="lint-summary">
                        <h3 className="lint-summary__title">
                            {report.has_critical ? '🚫' : report.has_error ? '⚠️' : '✅'}{' '}
                            Relatório de Validação
                        </h3>
                        <div className="lint-summary__counts">
                            {criticalResults.length > 0 && (
                                <span className="lint-badge lint-badge--critical">
                                    {criticalResults.length} Crítico(s)
                                </span>
                            )}
                            {errorResults.length > 0 && (
                                <span className="lint-badge lint-badge--error">
                                    {errorResults.length} Erro(s)
                                </span>
                            )}
                            {warnResults.length > 0 && (
                                <span className="lint-badge lint-badge--warn">
                                    {warnResults.length} Aviso(s)
                                </span>
                            )}
                            {report.results.length === 0 && (
                                <span className="lint-badge lint-badge--success">
                                    Nenhum problema encontrado!
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Result Cards */}
                    {report.results.length > 0 && (
                        <div className="lint-results">
                            {report.results.map((r, i) => (
                                <div key={i} className={`lint-card lint-card--${r.level.toLowerCase()}`}>
                                    <div className="lint-card__header">
                                        <span className="lint-card__level">
                                            {r.level === 'CRITICAL' ? '🚫' : r.level === 'ERROR' ? '❌' : r.level === 'WARN' ? '⚠️' : 'ℹ️'}
                                            {' '}{r.level}
                                        </span>
                                        <span className="lint-card__rule">{r.rule_id}</span>
                                    </div>
                                    <div className="lint-card__message">{r.message}</div>
                                    {r.element_name && (
                                        <div className="lint-card__element">
                                            Elemento: <strong>{r.element_name}</strong>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="module-actions">
                        <div className="module-actions__buttons">
                            {canGenerateDpt && (
                                <button
                                    className="btn btn--primary btn--lg"
                                    onClick={handleGenerateDpt}
                                    disabled={loadingDpt}
                                >
                                    {loadingDpt ? (
                                        <>
                                            <span className="step-item__spinner" style={{ width: 16, height: 16 }} />
                                            Gerando DPT...
                                        </>
                                    ) : (
                                        <>📄 Gerar DPT (.docx)</>
                                    )}
                                </button>
                            )}
                            {canGenerateDpt && (
                                <button
                                    className="btn btn--primary btn--lg"
                                    onClick={handleGenerateKpi}
                                    disabled={loadingKpi}
                                >
                                    {loadingKpi ? (
                                        <>
                                            <span className="step-item__spinner" style={{ width: 16, height: 16 }} />
                                            Gerando Indicadores...
                                        </>
                                    ) : (
                                        <>📊 Gerar Indicadores (.xlsx)</>
                                    )}
                                </button>
                            )}
                            <button className="btn btn--secondary" onClick={handleReset}>
                                Nova Validação
                            </button>
                        </div>
                        {!canGenerateDpt && report.has_critical && (
                            <p style={{ color: 'var(--error)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-md)' }}>
                                O DPT não pode ser gerado enquanto houver erros críticos (CRITICAL).
                            </p>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
