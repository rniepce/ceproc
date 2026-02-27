import React from 'react'

export default function Header() {
    return (
        <header className="header">
            <div className="header__logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect width="8" height="8" x="3" y="3" rx="2" />
                    <path d="M7 11v4a2 2 0 0 0 2 2h4" />
                    <rect width="8" height="8" x="13" y="13" rx="2" />
                </svg>
            </div>
            <div className="header__content">
                <h1 className="header__title">Mapeador Inteligente</h1>
                <p className="header__subtitle">CEPROC — Centro de Gestão de Processos de Trabalho e de Segurança da Informação</p>
            </div>
            <span className="header__badge">TJMG</span>
        </header>
    )
}
