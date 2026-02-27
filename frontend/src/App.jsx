import React, { useState } from 'react'
import Header from './components/Header'
import StepProgress from './components/StepProgress'
import UploadPage from './pages/UploadPage'
import ResultPage from './pages/ResultPage'

/*
  Flow:
  1. 'upload'     → User uploads audio
  2. 'modulo1'    → Processing Module 1
  3. 'review1'    → User reviews Relatório de Descoberta → Approves for Module 2
  4. 'modulo2'    → Processing Module 2
  5. 'review2'    → User reviews BPMN AS-IS → Approves for Module 3
  6. 'modulo3a'   → Processing Module 3A (consultoria)
  7. 'review3a'   → User reviews proposals → Selects which to approve → Module 3B
  8. 'modulo3b'   → Processing Module 3B (TO-BE XML)
  9. 'review3b'   → User reviews TO-BE BPMN → Approves for Module 4
  10. 'modulo4'   → Processing Module 4
  11. 'final'     → Final view with all results + downloads
*/

export default function App() {
    const [view, setView] = useState('upload')
    const [error, setError] = useState('')

    // Session data accumulated across modules
    const [sessionData, setSessionData] = useState({
        relatorio_descoberta: '',
        bpmn_xml_as_is: '',
        bpmn_validation_as_is: null,
        consultoria: '',
        propostas_aprovadas: '',
        bpmn_xml_to_be: '',
        bpmn_validation_to_be: null,
        pop_texto: '',
        aviso_bizagi: '',
    })

    const updateSession = (updates) => {
        setSessionData(prev => ({ ...prev, ...updates }))
    }

    // ── Module 1: Upload Audio → Relatório de Descoberta ────────────
    const handleUpload = async (file) => {
        setView('modulo1')
        setError('')
        try {
            const formData = new FormData()
            formData.append('file', file)
            const res = await fetch('/api/modulo1', { method: 'POST', body: formData })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 1')
            }
            const json = await res.json()
            updateSession({ relatorio_descoberta: json.relatorio_descoberta })
            setView('review1')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Module 1 (Text): Pasted transcription → Relatório ───────────
    const handleTextUpload = async (text) => {
        setView('modulo1')
        setError('')
        try {
            const res = await fetch('/api/modulo1-text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ transcricao: text })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 1')
            }
            const json = await res.json()
            updateSession({ relatorio_descoberta: json.relatorio_descoberta })
            setView('review1')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Module 2: Relatório → BPMN AS-IS ───────────────────────────
    const handleModulo2 = async () => {
        setView('modulo2')
        setError('')
        try {
            const res = await fetch('/api/modulo2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ relatorio_descoberta: sessionData.relatorio_descoberta })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 2')
            }
            const json = await res.json()
            updateSession({
                bpmn_xml_as_is: json.bpmn_xml_as_is,
                bpmn_validation_as_is: json.bpmn_validation,
                aviso_bizagi: json.aviso_bizagi,
            })
            setView('review2')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Module 3A: Consultoria ──────────────────────────────────────
    const handleModulo3a = async () => {
        setView('modulo3a')
        setError('')
        try {
            const res = await fetch('/api/modulo3a', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    relatorio_descoberta: sessionData.relatorio_descoberta,
                    bpmn_xml_as_is: sessionData.bpmn_xml_as_is,
                })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 3A')
            }
            const json = await res.json()
            updateSession({ consultoria: json.consultoria })
            setView('review3a')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Module 3B: Redesenho TO-BE ─────────────────────────────────
    const handleModulo3b = async (propostas) => {
        setView('modulo3b')
        setError('')
        updateSession({ propostas_aprovadas: propostas })
        try {
            const res = await fetch('/api/modulo3b', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    relatorio_descoberta: sessionData.relatorio_descoberta,
                    consultoria: sessionData.consultoria,
                    propostas_aprovadas: propostas,
                })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 3B')
            }
            const json = await res.json()
            updateSession({
                bpmn_xml_to_be: json.bpmn_xml_to_be,
                bpmn_validation_to_be: json.bpmn_validation,
                aviso_bizagi: json.aviso_bizagi,
            })
            setView('review3b')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Module 4: POP ──────────────────────────────────────────────
    const handleModulo4 = async () => {
        setView('modulo4')
        setError('')
        try {
            const res = await fetch('/api/modulo4', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bpmn_xml_to_be: sessionData.bpmn_xml_to_be,
                    relatorio_descoberta: sessionData.relatorio_descoberta,
                })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Erro no Módulo 4')
            }
            const json = await res.json()
            updateSession({ pop_texto: json.pop_texto })
            setView('final')
        } catch (e) {
            setError(e.message)
            setView('error')
        }
    }

    // ── Reset ──────────────────────────────────────────────────────
    const handleReset = () => {
        setView('upload')
        setError('')
        setSessionData({
            relatorio_descoberta: '',
            bpmn_xml_as_is: '',
            bpmn_validation_as_is: null,
            consultoria: '',
            propostas_aprovadas: '',
            bpmn_xml_to_be: '',
            bpmn_validation_to_be: null,
            pop_texto: '',
            aviso_bizagi: '',
        })
    }

    // Map view to active step for progress indicator
    const getActiveStep = () => {
        if (view.startsWith('modulo1') || view === 'review1') return 0
        if (view.startsWith('modulo2') || view === 'review2') return 1
        if (view.startsWith('modulo3') || view === 'review3a' || view === 'review3b') return 2
        if (view.startsWith('modulo4') || view === 'final') return 3
        return -1
    }

    const isProcessing = ['modulo1', 'modulo2', 'modulo3a', 'modulo3b', 'modulo4'].includes(view)

    return (
        <>
            <Header />
            <main className="main">
                {view === 'upload' && (
                    <UploadPage onProcess={handleUpload} onProcessText={handleTextUpload} />
                )}

                {isProcessing && (
                    <StepProgress currentStep={getActiveStep()} processingLabel={
                        view === 'modulo1' ? 'Analisando o áudio/texto e gerando Relatório de Descoberta...' :
                            view === 'modulo2' ? 'Convertendo fluxo para BPMN XML (AS-IS)...' :
                                view === 'modulo3a' ? 'Executando consultoria Lean...' :
                                    view === 'modulo3b' ? 'Gerando novo fluxo BPMN (TO-BE)...' :
                                        view === 'modulo4' ? 'Gerando Procedimento Operacional Padrão...' : ''
                    } />
                )}

                {(view.startsWith('review') || view === 'final') && (
                    <ResultPage
                        view={view}
                        data={sessionData}
                        onApproveModulo2={handleModulo2}
                        onApproveModulo3a={handleModulo3a}
                        onApproveModulo3b={handleModulo3b}
                        onApproveModulo4={handleModulo4}
                        onReset={handleReset}
                    />
                )}

                {view === 'error' && (
                    <div className="upload-page">
                        <div className="error-banner">
                            <span className="error-banner__icon">❌</span>
                            <div className="error-banner__content">
                                <div className="error-banner__title">Erro no Processamento</div>
                                <div className="error-banner__message">{error}</div>
                            </div>
                        </div>
                        <button className="btn btn--primary" onClick={handleReset}>
                            Tentar Novamente
                        </button>
                    </div>
                )}
            </main>

            <footer className="footer">
                CEPROC — Centro de Gestão de Processos de Trabalho e de Segurança da Informação · Tribunal de Justiça do Estado de Minas Gerais · 2026
            </footer>
        </>
    )
}
