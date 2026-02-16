import { useMemo, useState } from 'react';
import { jsPDF } from 'jspdf';
import { Link, useSearchParams } from 'react-router-dom';

const API_BASE = 'http://localhost:8000';

export default function ClaimsPreparationPage() {
	const [searchParams] = useSearchParams();
	const reportIdParam = searchParams.get('reportId') || '';
	const customerIdParam = searchParams.get('customerId') || '';

	const [reportId, setReportId] = useState(reportIdParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [llmResponse, setLlmResponse] = useState('');
	const [pdfPackets, setPdfPackets] = useState([]);

	const canRun = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	async function run() {
		setBusy(true);
		setError('');
		setResult(null);
		setLlmResponse('');
		setPdfPackets([]);
		try {
			const rid = String(reportId).trim();
			const res = await fetch(`${API_BASE}/api/claims/prepare`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ report_id: rid }),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) throw new Error(data?.detail || `Request failed (${res.status})`);
			setResult(data);

			const created = new Date().toLocaleString();
			const packet = data?.packet || {};
			const accident = packet?.accident || {};
			const customer = packet?.customer || {};
			const evidenceList = Array.isArray(accident?.evidenceUrls) ? accident.evidenceUrls : [];
			const missingItems = Array.isArray(data?.missingItems) ? data.missingItems : [];
			const policyInfo = {
				policyNumber: customer?.policyNumber || 'N/A',
				coverageType: customer?.coverageType || 'N/A',
				customerName: customer?.name || 'N/A',
				customerId: customer?.id ?? 'N/A',
				state: customer?.state || 'N/A',
				vehicle: customer?.vehicle || 'N/A',
			};

			function createDoc(title, lines = []) {
				const doc = new jsPDF();
				let y = 18;
				doc.setFontSize(16);
				doc.text(title, 14, y);
				y += 10;
				doc.setFontSize(11);
				doc.text(`Report ID: ${rid}`, 14, y);
				y += 6;
				doc.text(`Generated: ${created}`, 14, y);
				y += 8;
				lines.forEach((line) => {
					const wrapped = doc.splitTextToSize(String(line), 180);
					doc.text(wrapped, 14, y);
					y += wrapped.length * 6 + 2;
				});
				return doc;
			}

			const packets = [];
			packets.push({
				label: 'Claim form',
				doc: createDoc('Claim Form', [
					"This form confirms that a claim is being filed.",
					`Status: ${data?.status || 'N/A'}`,
					`Customer: ${policyInfo.customerName} (ID: ${policyInfo.customerId})`,
					`Vehicle: ${policyInfo.vehicle}`,
					`Coverage type: ${policyInfo.coverageType}`,
					missingItems.length ? `Missing items: ${missingItems.join(', ')}` : 'Missing items: None',
				]),
			});
			packets.push({
				label: 'Proof of loss',
				doc: createDoc('Proof of Loss', [
					'Provide what happened, when, and how.',
					`Location: ${accident?.location || 'N/A'}`,
					`Injured count: ${accident?.injuredCount ?? 'N/A'}`,
					`Vehicle drivable: ${accident?.vehiclesDrivable ?? 'N/A'}`,
					`Notes: ${accident?.notes || 'N/A'}`,
				]),
			});
			packets.push({
				label: 'Police report',
				doc: createDoc('Police Report (if applicable)', [
					'Attach a police report if the incident involved an accident or theft.',
				]),
			});
			packets.push({
				label: 'Photos or videos',
				doc: createDoc('Photos / Videos of Damage', [
					evidenceList.length ? `Evidence URLs: ${evidenceList.join(', ')}` : 'Evidence URLs: N/A',
					accident?.evidenceOptionalNote ? `Note: ${accident.evidenceOptionalNote}` : '',
				]),
			});
			packets.push({
				label: 'Repair estimates',
				doc: createDoc('Repair Estimates / Bills', [
					'Include quotes or invoices from repair shops.',
					`Vehicle: ${policyInfo.vehicle}`,
				]),
			});
			packets.push({
				label: 'Medical records',
				doc: createDoc('Medical Records / Bills', [
					'Attach medical documentation for injuries.',
					`Injured count: ${accident?.injuredCount ?? 'N/A'}`,
					`Notes: ${accident?.notes || 'N/A'}`,
				]),
			});
			packets.push({
				label: 'Expense receipts',
				doc: createDoc('Receipts for Related Expenses', [
					'Include towing, rental car, or temporary lodging receipts.',
					`Location: ${accident?.location || 'N/A'}`,
				]),
			});
			packets.push({
				label: 'Policy info',
				doc: createDoc('Insurance Policy Info', [
					`Policy number: ${policyInfo.policyNumber}`,
					`Coverage type: ${policyInfo.coverageType}`,
					`Customer: ${policyInfo.customerName} (ID: ${policyInfo.customerId})`,
					`State: ${policyInfo.state}`,
					`Vehicle: ${policyInfo.vehicle}`,
				]),
			});

			const urls = packets.map((packet, idx) => {
				const blob = packet.doc.output('blob');
				return {
					label: packet.label,
					url: URL.createObjectURL(blob),
					name: `claim-${rid || 'report'}-${idx + 1}.pdf`,
				};
			});
			setPdfPackets(urls);
			if (data?.llmResponse) {
				setLlmResponse(String(data.llmResponse));
			}
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
				<h1 style={{ margin: 0 }}>Claims Preparation</h1>
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
					{busy ? 'Working…' : 'Prepare Claim Packet'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16 }}>
					<h3 style={{ marginTop: 0 }}>Claim Packet PDFs</h3>
					{pdfPackets.length ? (
						<ul style={{ paddingLeft: 18 }}>
							{pdfPackets.map((packet) => (
								<li key={packet.url} style={{ marginBottom: 6 }}>
									<a href={packet.url} download={packet.name} style={{ color: '#ffffff', textDecoration: 'underline' }}>
										Download {packet.label}
									</a>
								</li>
							))}
						</ul>
					) : (
						<div style={{ opacity: 0.8 }}>Preparing PDFs…</div>
					)}
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
