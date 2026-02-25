import React from 'react'

const STEPS = [
    {
        title: 'Módulo 1 — Extração e Diagnóstico AS-IS',
        desc: 'Analisando o áudio e gerando Relatório de Descoberta (8 eixos)',
    },
    {
        title: 'Módulo 2 — Conversor BPMN-XML',
        desc: 'Convertendo o fluxo AS-IS para código BPMN 2.0 (Bizagi)',
    },
    {
        title: 'Módulo 3 — Consultoria e Redesenho TO-BE',
        desc: 'Análise Lean, inovações, KPIs e geração do novo fluxo',
    },
    {
        title: 'Módulo 4 — Geração do POP',
        desc: 'Criando o Procedimento Operacional Padrão para o servidor',
    },
]

export default function StepProgress({ currentStep, processingLabel }) {
    return (
        <div className="step-progress">
            <div className="step-progress__header">
                <h2 className="step-progress__title">Processando com IA</h2>
                {processingLabel && (
                    <p className="step-progress__subtitle">{processingLabel}</p>
                )}
            </div>
            <div className="step-progress__steps">
                {STEPS.map((step, idx) => {
                    let status = 'pending'
                    if (idx < currentStep) status = 'done'
                    else if (idx === currentStep) status = 'active'

                    return (
                        <div key={idx} className={`step-item step-item--${status}`}>
                            <div className="step-item__number">
                                {status === 'done' ? '✓' : idx + 1}
                            </div>
                            <div className="step-item__content">
                                <div className="step-item__title">{step.title}</div>
                                <div className="step-item__desc">{step.desc}</div>
                            </div>
                            {status === 'active' && <div className="step-item__spinner" />}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
