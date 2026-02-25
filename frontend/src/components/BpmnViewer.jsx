import React, { useEffect, useRef } from 'react'
import BpmnJS from 'bpmn-js/lib/NavigatedViewer'

export default function BpmnViewer({ xml }) {
    const containerRef = useRef(null)
    const viewerRef = useRef(null)

    useEffect(() => {
        if (!containerRef.current || !xml) return

        // Destroy previous instance
        if (viewerRef.current) {
            viewerRef.current.destroy()
        }

        const viewer = new BpmnJS({
            container: containerRef.current,
        })

        viewerRef.current = viewer

        viewer.importXML(xml).then(({ warnings }) => {
            if (warnings.length) {
                console.warn('BPMN import warnings:', warnings)
            }
            // Fit diagram to viewport
            const canvas = viewer.get('canvas')
            canvas.zoom('fit-viewport', 'auto')
        }).catch((err) => {
            console.error('BPMN import error:', err)
        })

        return () => {
            viewer.destroy()
        }
    }, [xml])

    const handleZoomIn = () => {
        if (viewerRef.current) {
            const canvas = viewerRef.current.get('canvas')
            canvas.zoom(canvas.zoom() * 1.2)
        }
    }

    const handleZoomOut = () => {
        if (viewerRef.current) {
            const canvas = viewerRef.current.get('canvas')
            canvas.zoom(canvas.zoom() / 1.2)
        }
    }

    const handleFitView = () => {
        if (viewerRef.current) {
            const canvas = viewerRef.current.get('canvas')
            canvas.zoom('fit-viewport', 'auto')
        }
    }

    return (
        <div style={{ position: 'relative' }}>
            <div ref={containerRef} className="bpmn-container" />
            <div className="bpmn-controls">
                <button className="bpmn-control-btn" onClick={handleZoomIn} title="Zoom In">+</button>
                <button className="bpmn-control-btn" onClick={handleZoomOut} title="Zoom Out">−</button>
                <button className="bpmn-control-btn" onClick={handleFitView} title="Ajustar">⊡</button>
            </div>
        </div>
    )
}
