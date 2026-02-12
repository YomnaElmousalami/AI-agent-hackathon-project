import { useMemo, useState } from 'react';
import { jsPDF } from 'jspdf';
import { Link, useSearchParams } from 'react-router-dom';

const API_BASE = '';

export default function AccidentSeverityPage() {
	const [searchParams] = useSearchParams();
	const reportIdParam = searchParams.get('reportId') || '';
	const customerIdParam = searchParams.get('customerId') || '';

	const [reportId, setReportId] = useState(reportIdParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [pdfUrl, setPdfUrl] = useState('');
	const [pdfName, setPdfName] = useState('accident-severity.pdf');

	const canRun = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	async function run() {
		setBusy(true);
		setError('');
		setResult(null);
		if (pdfUrl) {
			URL.revokeObjectURL(pdfUrl);
			setPdfUrl('');
		}
		try {
			const rid = String(reportId).trim();
			const res = await fetch(`${API_BASE}/api/accident/severity`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ report_id: rid }),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) throw new Error(data?.detail || `Request failed (${res.status})`);
			setResult(data);

			const doc = new jsPDF();
			let y = 18;
			doc.setFontSize(16);
			doc.text('Accident Severity Report', 14, y);
			y += 10;
			doc.setFontSize(11);
			doc.text(`Generated: ${new Date().toLocaleString()}`, 14, y);
			y += 8;

			const details = [
				`Report ID: ${data?.reportId ?? ''}`,
				`Severity: ${data?.severity ?? ''}`,
				`Urgency: ${data?.urgency ?? ''}`,
				`Accident Type: ${data?.accidentType ?? 'N/A'}`,
			];
			details.forEach((line) => {
				doc.text(line, 14, y);
				y += 7;
			});

			const rationale = String(data?.rationale || '').trim();
			if (rationale) {
				doc.setFontSize(12);
				doc.text('Rationale', 14, y);
				y += 7;
				doc.setFontSize(11);
				const rationaleLines = doc.splitTextToSize(rationale, 180);
				doc.text(rationaleLines, 14, y);
				y += rationaleLines.length * 6 + 4;
			}

			const recommended = Array.isArray(data?.recommendedActions) ? data.recommendedActions : [];
			if (recommended.length) {
				doc.setFontSize(12);
				doc.text('Recommended Actions', 14, y);
				y += 7;
				doc.setFontSize(11);
				recommended.forEach((item) => {
					const lines = doc.splitTextToSize(`• ${item}`, 180);
					doc.text(lines, 14, y);
					y += lines.length * 6;
				});
			}

			const imageAnalysis = data?.imageAnalysis || null;
			const imageError = data?.imageAnalysisError || '';
			const imageScore = imageAnalysis?.severityScore ?? null;
			const imageSummary = String(imageAnalysis?.summary || '').trim();
			const imageActions = Array.isArray(imageAnalysis?.suggestedActions)
				? imageAnalysis.suggestedActions
				: [];

			y += 6;
			doc.setFontSize(12);
			doc.text('Image-based Assessment', 14, y);
			y += 7;
			doc.setFontSize(11);
			doc.text(`Severity Score: ${imageScore != null ? imageScore : 'N/A'}`, 14, y);
			y += 7;
			if (imageError) {
				const errorLines = doc.splitTextToSize(`Image analysis error: ${imageError}`, 180);
				doc.text(errorLines, 14, y);
				y += errorLines.length * 6 + 2;
			}
			if (imageSummary) {
				const summaryLines = doc.splitTextToSize(imageSummary, 180);
				doc.text(summaryLines, 14, y);
				y += summaryLines.length * 6 + 2;
			} else {
				doc.text('Summary: N/A', 14, y);
				y += 7;
			}
			if (imageActions.length) {
				imageActions.forEach((item) => {
					const lines = doc.splitTextToSize(`• ${item}`, 180);
					doc.text(lines, 14, y);
					y += lines.length * 6;
				});
			} else {
				doc.text('Suggested Actions: N/A', 14, y);
				y += 7;
			}

			const blob = doc.output('blob');
			const url = URL.createObjectURL(blob);
			setPdfUrl(url);
			setPdfName(`accident-severity-${rid || 'report'}.pdf`);
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	const backLink = useMemo(() => {
		const qs = new URLSearchParams();
		if (customerIdParam) qs.set('customerId', customerIdParam);
		if (reportId) qs.set('reportId', String(reportId).trim());
		const q = qs.toString();
		return `/accident${q ? `?${q}` : ''}`;
	}, [customerIdParam, reportId]);

	return (
		<div style={{ padding: 24, maxWidth: 980, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Accident Severity Assessment Agent</h1>
				<Link to={backLink} style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Accident Report
				</Link>
			</div>

			<div style={{ marginTop: 16 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Report id</label>
				<input value={reportId} onChange={(e) => setReportId(e.target.value)} style={{ width: 'min(720px, 100%)', padding: 10 }} />
			</div>

			<div style={{ marginTop: 12 }}>
				<button onClick={run} disabled={!canRun} style={{ fontSize: '16px', padding: '10px 24px' }}>
					{busy ? 'Assessing…' : 'Assess Severity'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16 }}>
					<h3 style={{ marginTop: 0 }}>Accident Severity PDF</h3>
					{pdfUrl ? (
						<a
							href={pdfUrl}
							download={pdfName}
							style={{ color: '#ffffff', textDecoration: 'underline' }}
						>
							Download severity report (PDF)
						</a>
					) : (
						<div style={{ opacity: 0.8 }}>Preparing PDF…</div>
					)}
					{result?.imageAnalysisError ? (
						<div style={{ marginTop: 8, opacity: 0.8, fontSize: 13 }}>
							Image analysis error: {String(result.imageAnalysisError)}
						</div>
					) : null}
				</div>
			) : null}
		</div>
	);
}
