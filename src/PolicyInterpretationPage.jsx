import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

const API_BASE = '';

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

	const canRun = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	async function run() {
		setBusy(true);
		setError('');
		setResult(null);
		try {
			const rid = String(reportId).trim();
			const res = await fetch(`${API_BASE}/api/policy/interpret`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ report_id: rid }),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) throw new Error(data?.detail || `Request failed (${res.status})`);
			setResult(data);
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
				<h1 style={{ margin: 0 }}>Policy Interpretation Agent</h1>
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
					<h3 style={{ marginTop: 0 }}>Result</h3>
					<pre style={{ whiteSpace: 'pre-wrap', background: '#101820', border: '1px solid #223344', padding: 12 }}>
						{asText(result)}
					</pre>
				</div>
			) : null}
		</div>
	);
}
