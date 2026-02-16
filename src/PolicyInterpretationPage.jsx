import { useMemo, useState } from 'react';
import { jsPDF } from 'jspdf';
import { Link, useSearchParams } from 'react-router-dom';

const API_BASE = 'http://localhost:8000';

function asText(v) {
	try {
		return JSON.stringify(v, null, 2);
	} catch {
		return String(v);
	}
}

export default function PolicyInterpretationPage() {
	const [searchParams] = useSearchParams();
	const reportIdParam = searchParams.get('reportId') || '';
	const customerIdParam = searchParams.get('customerId') || '';

	const [reportId, setReportId] = useState(reportIdParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [llmResponse, setLlmResponse] = useState('');
	const [policyPdf, setPolicyPdf] = useState('');
	const [policyImages, setPolicyImages] = useState([]);
	const [pdfUrl, setPdfUrl] = useState('');
	const [pdfName, setPdfName] = useState('policy-interpretation.pdf');

	const canRun = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	async function run() {
		setBusy(true);
		setError('');
		setResult(null);
		setLlmResponse('');
		if (pdfUrl) {
			URL.revokeObjectURL(pdfUrl);
			setPdfUrl('');
		}
		try {
			const rid = String(reportId).trim();
			const res = await fetch(`${API_BASE}/api/policy/interpret`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					report_id: rid,
					policy_pdf_base64: policyPdf || undefined,
					policy_image_base64: policyImages.length ? policyImages : undefined,
				}),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) throw new Error(data?.detail || `Request failed (${res.status})`);
			setResult(data);

			const doc = new jsPDF();
			let y = 18;
			doc.setFontSize(16);
			doc.text('Policy Interpretation Report', 14, y);
			y += 10;
			doc.setFontSize(11);
			doc.text(`Generated: ${new Date().toLocaleString()}`, 14, y);
			y += 8;

			const baseSummary = String(data?.coverageSummary || '').trim();
			const baseAssumptions = Array.isArray(data?.assumptions) ? data.assumptions : [];
			const baseExclusions = Array.isArray(data?.exclusions) ? data.exclusions : [];
			const baseDeductible = data?.estimatedDeductible ?? 'N/A';
			const baseOut = data?.estimatedOutOfPocket ?? 'N/A';

			doc.setFontSize(12);
			doc.text('Policy Interpretation', 14, y);
			y += 7;
			doc.setFontSize(11);
			doc.text(`Estimated deductible: ${baseDeductible}`, 14, y);
			y += 6;
			doc.text(`Estimated out-of-pocket: ${baseOut}`, 14, y);
			y += 6;
			if (baseSummary) {
				const lines = doc.splitTextToSize(baseSummary, 180);
				doc.text(lines, 14, y);
				y += lines.length * 6 + 2;
			}
			if (baseAssumptions.length) {
				doc.text('Assumptions:', 14, y);
				y += 6;
				baseAssumptions.forEach((item) => {
					const lines = doc.splitTextToSize(`• ${item}`, 180);
					doc.text(lines, 14, y);
					y += lines.length * 6;
				});
				y += 2;
			}
			if (baseExclusions.length) {
				doc.text('Exclusions:', 14, y);
				y += 6;
				baseExclusions.forEach((item) => {
					const lines = doc.splitTextToSize(`• ${item}`, 180);
					doc.text(lines, 14, y);
					y += lines.length * 6;
				});
				 y += 2;
			}

			if (data?.pdfInterpretation) {
				const pdfInterp = data.pdfInterpretation;
				const pdfSummary = String(pdfInterp.coverageSummary || '').trim();
				const pdfAssumptions = Array.isArray(pdfInterp.assumptions) ? pdfInterp.assumptions : [];
				const pdfExclusions = Array.isArray(pdfInterp.exclusions) ? pdfInterp.exclusions : [];
				const pdfDeductible = pdfInterp.estimatedDeductible ?? 'N/A';
				const pdfOut = pdfInterp.estimatedOutOfPocket ?? 'N/A';

				y += 6;
				doc.setFontSize(12);
				doc.text('Policy PDF Analysis', 14, y);
				y += 7;
				doc.setFontSize(11);
				doc.text(`Estimated deductible: ${pdfDeductible}`, 14, y);
				y += 6;
				doc.text(`Estimated out-of-pocket: ${pdfOut}`, 14, y);
				y += 6;
				if (pdfSummary) {
					const lines = doc.splitTextToSize(pdfSummary, 180);
					doc.text(lines, 14, y);
					y += lines.length * 6 + 2;
				}
				if (pdfAssumptions.length) {
					doc.text('Assumptions:', 14, y);
					y += 6;
					pdfAssumptions.forEach((item) => {
						const lines = doc.splitTextToSize(`• ${item}`, 180);
						doc.text(lines, 14, y);
						y += lines.length * 6;
					});
					y += 2;
				}
				if (pdfExclusions.length) {
					doc.text('Exclusions:', 14, y);
					y += 6;
					pdfExclusions.forEach((item) => {
						const lines = doc.splitTextToSize(`• ${item}`, 180);
						doc.text(lines, 14, y);
						y += lines.length * 6;
					});
				}
			}

			const blob = doc.output('blob');
			const url = URL.createObjectURL(blob);
			setPdfUrl(url);
			setPdfName(`policy-interpretation-${rid || 'report'}.pdf`);
			if (data?.llmResponse) {
				setLlmResponse(String(data.llmResponse));
			}
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	async function onPolicyPdfChange(e) {
		const file = e.target.files?.[0];
		if (!file) {
			setPolicyPdf('');
			return;
		}
		const reader = new FileReader();
		reader.onload = () => setPolicyPdf(String(reader.result || ''));
		reader.onerror = () => setError('Failed to read PDF file.');
		reader.readAsDataURL(file);
	}

	async function onPolicyImagesChange(e) {
		const files = Array.from(e.target.files || []);
		if (!files.length) {
			setPolicyImages([]);
			return;
		}
		try {
			const reads = await Promise.all(
				files.map(
					(file) =>
						new Promise((resolve, reject) => {
							const reader = new FileReader();
							reader.onload = () => resolve(String(reader.result || ''));
							reader.onerror = () => reject(new Error('Failed to read image file.'));
							reader.readAsDataURL(file);
						})
				)
			);
			setPolicyImages(reads.filter(Boolean));
		} catch (err) {
			setError(err?.message || 'Failed to read image files.');
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
				<h1 style={{ margin: 0 }}>Policy Interpretation</h1>
				<Link to={backLink} style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Accident Report
				</Link>
			</div>

			<div style={{ marginTop: 16 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Report id</label>
				<input value={reportId} onChange={(e) => setReportId(e.target.value)} style={{ width: 'min(720px, 100%)', padding: 10 }} />
			</div>

			<div style={{ marginTop: 12 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Policy PDF</label>
				<input type='file' accept='application/pdf' onChange={onPolicyPdfChange} />
				{policyPdf ? (
					<div style={{ marginTop: 6, fontSize: 13, opacity: 0.8 }}>PDF attached.</div>
				) : null}
			</div>

			<div style={{ marginTop: 12 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Policy images</label>
				<input type='file' accept='image/*' multiple onChange={onPolicyImagesChange} />
				{policyImages.length ? (
					<div style={{ marginTop: 6, fontSize: 13, opacity: 0.8 }}>{policyImages.length} image(s) attached.</div>
				) : null}
			</div>

			<div style={{ marginTop: 12 }}>
				<button onClick={run} disabled={!canRun} style={{ fontSize: '16px', padding: '10px 24px' }}>
					{busy ? 'Working…' : 'Interpret Policy'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16 }}>
					<h3 style={{ marginTop: 0 }}>Policy Interpretation PDF</h3>
					{pdfUrl ? (
						<a href={pdfUrl} download={pdfName} style={{ color: '#ffffff', textDecoration: 'underline' }}>
							Download policy interpretation (PDF)
						</a>
					) : (
						<div style={{ opacity: 0.8 }}>Preparing PDF…</div>
					)}

					{result?.pdfInterpretationError && result.pdfInterpretationError !== 'missing_policy_text' ? (
						<div style={{ marginTop: 12, opacity: 0.8, fontSize: 13 }}>
							PDF analysis error: {String(result.pdfInterpretationError)}
						</div>
					) : null}
				</div>
			) : null}

			{llmResponse ? (
				<div style={{ marginTop: 16, background: '#0b1a2b', border: '1px solid #1f3b5d', padding: 12 }}>
					<strong>Assistant response:</strong>
					<div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{llmResponse}</div>
				</div>
			) : null}
		</div>
	);
}
