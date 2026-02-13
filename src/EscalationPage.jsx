import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

const API_BASE = '';

export default function EscalationPage() {
	const [searchParams] = useSearchParams();
	const reportIdParam = searchParams.get('reportId') || '';
	const customerIdParam = searchParams.get('customerId') || '';

	const [reportId, setReportId] = useState(reportIdParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [llmResponse, setLlmResponse] = useState('');

	const canRun = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	async function run() {
		setBusy(true);
		setError('');
		setResult(null);
		setLlmResponse('');
		try {
			const rid = String(reportId).trim();
			const res = await fetch(`${API_BASE}/api/escalation`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ report_id: rid }),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) throw new Error(data?.detail || `Request failed (${res.status})`);
			setResult(data);
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
				<h1 style={{ margin: 0 }}>Escalation & Routing</h1>
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
					{busy ? 'Working…' : 'Escalate & Route'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16 }}>
					<h3 style={{ marginTop: 0 }}>Escalation Summary</h3>
					<div style={{ background: '#101820', border: '1px solid #223344', padding: 12 }}>
						<p style={{ marginTop: 0 }}>
							{`We routed this case to ${result.routedTo || 'the appropriate channel'} because ${result.reason || 'we evaluated the report details'}.`}
						</p>
						{result.summary ? (
							<p>{`Summary: ${result.summary}.`}</p>
						) : null}
						{result.customerState ? (
							<p>{`Detected state for contacts: ${result.customerState}.`}</p>
						) : null}

						{Array.isArray(result.contactNumbers) && result.contactNumbers.length ? (
							<div style={{ marginTop: 12 }}>
								<strong>Recommended contacts:</strong>
								<ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
									{result.contactNumbers.map((contact, idx) => (
										<li key={idx}>
											{contact.label}
											{contact.phone ? ` — Phone: ${contact.phone}` : ''}
											{contact.url ? ` — ${contact.url}` : ''}.
										</li>
									))}
								</ul>
							</div>
						) : null}
					</div>
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
