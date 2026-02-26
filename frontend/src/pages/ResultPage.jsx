import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import BpmnViewer from '../components/BpmnViewer'

/**
 * ResultPage handles all review states:
 * - review1: Show Relatório de Descoberta → approve for Module 2
 * - review2: Show BPMN AS-IS → approve for Module 3
 * - review3a: Show Consultoria → user selects proposals → Module 3B
 * - review3b: Show BPMN TO-BE → approve for Module 4
 * - final: Show everything + downloads
 */
export default function ResultPage({
    view,
    data,
    onApproveModulo2,
    onApproveModulo3a,
    onApproveModulo3b,
    onApproveModulo4,
    onReset,
}) {
    const [propostas, setPropostas] = useState('')
    const [activeTab, setActiveTab] = useState('bpmn_to_be')

    // ── Helpers ──────────────────────────────────────────────────────
    const downloadBpmn = async (xml, filename) => {
        try {
            const res = await fetch('/api/download-bpmn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bpmn_xml: xml, filename })
            })
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${filename}.bpmn`
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            alert('Erro ao baixar arquivo BPMN')
        }
    }

    const downloadPdf = async () => {
        try {
            const res = await fetch('/api/download-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pop_texto: data.pop_texto,
                    processo_nome: 'Processo Mapeado TJMG'
                })
            })
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'POP_Processo_Mapeado_TJMG.pdf'
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            alert('Erro ao baixar PDF do POP')
        }
    }

    const getModuleNumber = () => {
        if (view === 'review1') return 1
        if (view === 'review2') return 2
        if (view === 'review3a' || view === 'review3b') return 3
        if (view === 'final') return 4
        return 0
    }

    // ════════════════════════════════════════════════════════════════
    // REVIEW 1: Relatório de Descoberta
    // ════════════════════════════════════════════════════════════════
    if (view === 'review1') {
        return (
            <div className="result-page">
                <ModuleHeader
                    number={1}
                    title="Extração e Diagnóstico AS-IS"
                    subtitle="Relatório de Descoberta (8 eixos)"
                />
                <div className="tab-content">
                    <div className="tab-content__body">
                        <div className="tab-content__text markdown-body"><ReactMarkdown>{data.relatorio_descoberta}</ReactMarkdown></div>
                    </div>
                </div>
                <div className="module-actions">
                    <p className="module-actions__question">
                        Deseja gerar o código BPMN (Módulo 2)?
                    </p>
                    <div className="module-actions__buttons">
                        <button className="btn btn--primary btn--lg" onClick={onApproveModulo2}>
                            ✅ Aprovar e Gerar BPMN (Módulo 2)
                        </button>
                        <button className="btn btn--secondary" onClick={onReset}>
                            Cancelar
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // ════════════════════════════════════════════════════════════════
    // REVIEW 2: BPMN AS-IS
    // ════════════════════════════════════════════════════════════════
    if (view === 'review2') {
        return (
            <div className="result-page">
                <ModuleHeader
                    number={2}
                    title="Conversor BPMN-XML para Bizagi"
                    subtitle="Fluxo AS-IS convertido em BPMN 2.0"
                />

                {data.aviso_bizagi && (
                    <div className="info-banner">
                        <span className="info-banner__icon">⚠️</span>
                        <div className="info-banner__content">{data.aviso_bizagi}</div>
                    </div>
                )}

                <div className="tab-content">
                    <BpmnViewer xml={data.bpmn_xml_as_is} />
                </div>

                <div className="module-actions">
                    <div className="module-actions__row">
                        <button className="btn btn--secondary" onClick={() => downloadBpmn(data.bpmn_xml_as_is, 'processo_as_is')}>
                            ⬇️ Baixar .BPMN AS-IS
                        </button>
                    </div>
                    <p className="module-actions__question">
                        Deseja iniciar a Consultoria de Redesenho (Módulo 3)?
                    </p>
                    <div className="module-actions__buttons">
                        <button className="btn btn--primary btn--lg" onClick={onApproveModulo3a}>
                            ✅ Aprovar e Iniciar Consultoria (Módulo 3)
                        </button>
                        <button className="btn btn--secondary" onClick={onReset}>
                            Cancelar
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // ════════════════════════════════════════════════════════════════
    // REVIEW 3A: Consultoria (Selecionar propostas)
    // ════════════════════════════════════════════════════════════════
    if (view === 'review3a') {
        return (
            <div className="result-page">
                <ModuleHeader
                    number={3}
                    title="Consultoria e Redesenho TO-BE"
                    subtitle="Fase A — Gargalos, Inovações e KPIs"
                />

                <div className="tab-content">
                    <div className="tab-content__body">
                        <div className="tab-content__text markdown-body"><ReactMarkdown>{data.consultoria}</ReactMarkdown></div>
                    </div>
                </div>

                <div className="module-actions">
                    <p className="module-actions__question">
                        Quais propostas você aprova para o novo fluxo? Escreva abaixo quais sugestões deseja incorporar (ou digite "todas"):
                    </p>
                    <textarea
                        className="module-actions__textarea"
                        value={propostas}
                        onChange={(e) => setPropostas(e.target.value)}
                        placeholder='Ex: "Aprovo as sugestões 1, 3 e 5. A sugestão 2 não se aplica ao nosso setor."'
                        rows={4}
                    />
                    <div className="module-actions__buttons">
                        <button
                            className="btn btn--primary btn--lg"
                            disabled={!propostas.trim()}
                            onClick={() => onApproveModulo3b(propostas)}
                        >
                            ✅ Gerar Novo Fluxo TO-BE (Módulo 3B)
                        </button>
                        <button className="btn btn--secondary" onClick={onReset}>
                            Cancelar
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // ════════════════════════════════════════════════════════════════
    // REVIEW 3B: BPMN TO-BE
    // ════════════════════════════════════════════════════════════════
    if (view === 'review3b') {
        return (
            <div className="result-page">
                <ModuleHeader
                    number={3}
                    title="Redesenho TO-BE"
                    subtitle="Fase B — Novo Fluxo BPMN Otimizado"
                />

                {data.aviso_bizagi && (
                    <div className="info-banner">
                        <span className="info-banner__icon">⚠️</span>
                        <div className="info-banner__content">{data.aviso_bizagi}</div>
                    </div>
                )}

                <div className="tab-content">
                    <BpmnViewer xml={data.bpmn_xml_to_be} />
                </div>

                <div className="module-actions">
                    <div className="module-actions__row">
                        <button className="btn btn--secondary" onClick={() => downloadBpmn(data.bpmn_xml_to_be, 'processo_to_be')}>
                            ⬇️ Baixar .BPMN TO-BE
                        </button>
                    </div>
                    <p className="module-actions__question">
                        Deseja gerar o POP — Procedimento Operacional Padrão (Módulo 4)?
                    </p>
                    <div className="module-actions__buttons">
                        <button className="btn btn--primary btn--lg" onClick={onApproveModulo4}>
                            ✅ Aprovar e Gerar POP (Módulo 4)
                        </button>
                        <button className="btn btn--secondary" onClick={onReset}>
                            Cancelar
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // ════════════════════════════════════════════════════════════════
    // FINAL: Tudo concluído — Downloads
    // ════════════════════════════════════════════════════════════════
    if (view === 'final') {
        const TABS = [
            { id: 'bpmn_to_be', label: '📊 Fluxograma TO-BE' },
            { id: 'bpmn_as_is', label: '📋 Fluxograma AS-IS' },
            { id: 'relatorio', label: '🔍 Relatório de Descoberta' },
            { id: 'consultoria', label: '🚀 Consultoria' },
            { id: 'pop', label: '📄 POP' },
        ]

        return (
            <div className="result-page">
                <div className="result-page__header">
                    <div>
                        <h2 className="result-page__title">✅ Ciclo de Mapeamento Concluído</h2>
                        <p className="result-page__subtitle-text">
                            Todos os 4 módulos foram executados com sucesso.
                        </p>
                    </div>
                    <div className="result-page__actions">
                        <button className="btn btn--primary" onClick={() => downloadBpmn(data.bpmn_xml_to_be, 'processo_to_be_tjmg')}>
                            <svg className="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="7 10 12 15 17 10" />
                                <line x1="12" y1="15" x2="12" y2="3" />
                            </svg>
                            Baixar .BPMN TO-BE (Bizagi)
                        </button>
                        <button className="btn btn--accent" onClick={downloadPdf}>
                            <svg className="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="16" y1="13" x2="8" y2="13" />
                                <line x1="16" y1="17" x2="8" y2="17" />
                            </svg>
                            Baixar PDF (POP)
                        </button>
                        <button className="btn btn--secondary" onClick={() => downloadBpmn(data.bpmn_xml_as_is, 'processo_as_is_tjmg')}>
                            Baixar .BPMN AS-IS
                        </button>
                        <button className="btn btn--secondary" onClick={onReset}>
                            Novo Mapeamento
                        </button>
                    </div>
                </div>

                <div className="tabs">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            className={`tab ${activeTab === tab.id ? 'tab--active' : ''}`}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                <div className="tab-content">
                    {activeTab === 'bpmn_to_be' && <BpmnViewer xml={data.bpmn_xml_to_be} />}
                    {activeTab === 'bpmn_as_is' && <BpmnViewer xml={data.bpmn_xml_as_is} />}
                    {activeTab === 'relatorio' && (
                        <div className="tab-content__body">
                            <div className="tab-content__text markdown-body"><ReactMarkdown>{data.relatorio_descoberta}</ReactMarkdown></div>
                        </div>
                    )}
                    {activeTab === 'consultoria' && (
                        <div className="tab-content__body">
                            <div className="tab-content__text markdown-body"><ReactMarkdown>{data.consultoria}</ReactMarkdown></div>
                        </div>
                    )}
                    {activeTab === 'pop' && (
                        <div className="tab-content__body">
                            <div className="tab-content__text markdown-body"><ReactMarkdown>{data.pop_texto}</ReactMarkdown></div>
                        </div>
                    )}
                </div>
            </div>
        )
    }

    return null
}

// ── Subcomponent: Module Header ─────────────────────────────────
function ModuleHeader({ number, title, subtitle }) {
    return (
        <div className="module-header">
            <div className="module-header__badge">Módulo {number}</div>
            <h2 className="module-header__title">{title}</h2>
            {subtitle && <p className="module-header__subtitle">{subtitle}</p>}
        </div>
    )
}
