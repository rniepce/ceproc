import React from 'react'

export default function Header() {
    return (
        <header className="header">
            <div className="header__logo">TJ</div>
            <div className="header__content">
                <h1 className="header__title">Mapeador Inteligente</h1>
                <p className="header__subtitle">CEPROC — Centro de Estudos de Procedimentos</p>
            </div>
            <span className="header__badge">TJMG</span>
        </header>
    )
}
