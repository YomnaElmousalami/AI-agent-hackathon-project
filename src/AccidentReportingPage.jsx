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

export default function AccidentReportingPage() {
	const [searchParams] = useSearchParams();
	const customerIdParam = searchParams.get('customerId') || '';
	const reportIdParam = searchParams.get('reportId') || '';

	const [customerId, setCustomerId] = useState(customerIdParam);
	const [reportId, setReportId] = useState(reportIdParam);
	const [location, setLocation] = useState('');
	const [injuredCount, setInjuredCount] = useState('0');
	const [vehiclesDrivable, setVehiclesDrivable] = useState('');
	const [notes, setNotes] = useState('');
	const [evidenceUrls, setEvidenceUrls] = useState('');

	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);

	const canUpdate = useMemo(() => {
		const id = Number(customerId);
		return !busy && Number.isFinite(id) && id > 0;
	}, [busy, customerId]);
	const canFinalize = useMemo(() => !busy && String(reportId).trim().length > 0, [busy, reportId]);

	function parseVehiclesDrivable(v) {
		const t = String(v || '').trim().toLowerCase();
		if (t === '') return undefined;
		if (t === 'true' || t === 'yes' || t === 'y') return true;
		if (t === 'false' || t === 'no' || t === 'n') return false;
		return undefined;
	}

	async function updateReport() {
		setBusy(true);
		setError('');
		setResult(null);
		try {
			const id = Number(customerId);
			if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');

			// If we don't have a report yet, create one now.
			let rid = String(reportId).trim();
			if (!rid) {
				const createRes = await fetch(`${API_BASE}/api/accident/report/start`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ customer_id: id }),
				});
				const createData = await createRes.json().catch(() => null);
				if (!createRes.ok) throw new Error(createData?.detail || `Failed to create report (${createRes.status})`);
				rid = String(createData?.reportId || '').trim();
				if (!rid) throw new Error('Failed to create report (missing reportId).');
				setReportId(rid);
			}

			const injured = injuredCount === '' ? undefined : Number(injuredCount);
			if (injured != null && !Number.isFinite(injured)) throw new Error('Injured count must be a number.');

			const evidence = String(evidenceUrls || '')
				.split(',')
				.map((s) => s.trim())
				.filter(Boolean);

			const payload = {
				report_id: rid,
				location: location.trim() || undefined,
				injured_count: injured != null ? injured : undefined,
				vehicles_drivable: parseVehiclesDrivable(vehiclesDrivable),
				notes: notes.trim() || undefined,
				evidence_urls: evidence.length ? evidence : undefined,
			};

			const res = await fetch(`${API_BASE}/api/accident/report/update`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload),
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

	async function finalizeReport() {
		setBusy(true);
		setError('');
		setResult(null);
		try {
			// Finalize should only run on an existing report.
			// If the user hasn't updated/saved yet, prompt them to do so.
			const rid = String(reportId).trim();
			if (!rid) throw new Error('No report found yet. Click "Update Report" first to create and save the report.');

			const res = await fetch(`${API_BASE}/api/accident/report/finalize`, {
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

	const nextLinks = useMemo(() => {
		const rid = String(reportId).trim();
		const cid = Number(customerId);
		const qs = new URLSearchParams();
		if (Number.isFinite(cid) && cid > 0) qs.set('customerId', String(cid));
		if (rid) qs.set('reportId', rid);
		const q = qs.toString();
		return {
			severity: `/severity${q ? `?${q}` : ''}`,
			policy: `/policy${q ? `?${q}` : ''}`,
			claims: `/claims${q ? `?${q}` : ''}`,
			actionPlan: `/action-plan${q ? `?${q}` : ''}`,
			escalation: `/escalation${q ? `?${q}` : ''}`,
		};
	}, [customerId, reportId]);

	return (
		<div style={{ padding: 24, maxWidth: 980, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Accident Reporting</h1>
				<Link to='/' style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Onboarding
				</Link>
			</div>

			<p style={{ opacity: 0.95, lineHeight: 1.6, marginTop: 12 }}>
				Fill out the details and click Update Report to save it. Then click Finalize Report to mark it ready.
			</p>

			<div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Customer id</label>
					<input value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 240, padding: 10 }} />
				</div>
			</div>

			{reportId ? (
				<div style={{ marginTop: 16 }}>
					<div style={{ opacity: 0.9, marginBottom: 6 }}>Report id (auto-generated)</div>
					<div
						style={{
							width: 'min(720px, 100%)',
							padding: 10,
							border: '1px solid #223344',
							background: '#0b0b0f',
							borderRadius: 6,
							fontFamily:
								'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
							fontSize: 13,
						}}
					>
						{reportId}
					</div>
				</div>
			) : null}

			<div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Location (City, ST)</label>
					<input value={location} onChange={(e) => setLocation(e.target.value)} style={{ width: '100%', padding: 10 }} placeholder='e.g. Norfolk, VA' />
				</div>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Injured count</label>
					<input value={injuredCount} onChange={(e) => setInjuredCount(e.target.value)} style={{ width: '100%', padding: 10 }} placeholder='0' />
				</div>
			</div>

			<div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Vehicle drivable? (true/false)</label>
					<input value={vehiclesDrivable} onChange={(e) => setVehiclesDrivable(e.target.value)} style={{ width: '100%', padding: 10 }} placeholder='true / false' />
				</div>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Evidence URLs (comma-separated)</label>
					<input value={evidenceUrls} onChange={(e) => setEvidenceUrls(e.target.value)} style={{ width: '100%', padding: 10 }} placeholder='https://…/photo1.jpg, https://…/video.mp4' />
				</div>
			</div>

			<div style={{ marginTop: 12 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Notes</label>
				<textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} style={{ width: 'min(720px, 100%)', padding: 10 }} placeholder='rear-end accident, side-impact, etc.' />
			</div>

			<div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
				<button onClick={updateReport} disabled={!canUpdate} style={{ fontSize: '16px', padding: '10px 24px' }}>
					{busy ? 'Working…' : 'Update Report'}
				</button>
				<button onClick={finalizeReport} disabled={!canFinalize} style={{ fontSize: '16px', padding: '10px 24px' }}>
					{busy ? 'Working…' : 'Finalize Report'}
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

			<div style={{ marginTop: 16 }}>
				<h3 style={{ marginTop: 0 }}>Next agents</h3>
				<div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
					<Link to={nextLinks.severity} style={{ color: '#ffffff', textDecoration: 'underline' }}>
						Severity Assessment
					</Link>
					<Link to={nextLinks.policy} style={{ color: '#ffffff', textDecoration: 'underline' }}>
						Policy Interpretation
					</Link>
					<Link to={nextLinks.claims} style={{ color: '#ffffff', textDecoration: 'underline' }}>
						Claims Preparation
					</Link>
					<Link to={nextLinks.actionPlan} style={{ color: '#ffffff', textDecoration: 'underline' }}>
						Action Plan
					</Link>
					<Link to={nextLinks.escalation} style={{ color: '#ffffff', textDecoration: 'underline' }}>
						Escalation & Routing
					</Link>
				</div>
			</div>
		</div>
	);
}
