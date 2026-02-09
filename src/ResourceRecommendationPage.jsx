import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

// In dev, Vite proxies /api -> backend (see vite.config.js). So we should use
// a relative base; otherwise, you can trip over port mismatches.
// In prod builds, you can set VITE_API_BASE to your deployed backend URL.
const API_BASE = import.meta.env?.VITE_API_BASE || '';

function normalizeResource(r) {
	return {
		type: String(r?.type || 'article'),
		title: String(r?.title || 'Resource'),
		summary: String(r?.summary || ''),
		url: String(r?.url || ''),
	};
}

export default function ResourceRecommendationPage() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const customerIdParam = searchParams.get('customerId') || '';
	const topicParam = searchParams.get('topic') || '';
	const fromParam = searchParams.get('from') || '';

	const [customerId, setCustomerId] = useState(customerIdParam);
	const [topic, setTopic] = useState(topicParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [resources, setResources] = useState([]);

	const canSubmit = useMemo(() => {
		const id = Number(customerId);
		return !busy && Number.isFinite(id) && id > 0 && topic.trim().length > 0;
	}, [busy, customerId, topic]);

	const backUrl = useMemo(() => {
		const id = Number(customerId);
		if (!Number.isFinite(id) || id <= 0) return '/quiz';
		if (fromParam === 'quiz') return `/quiz?customerId=${id}`;
		if (fromParam === 'teacher') return `/teacher?customerId=${id}`;
		return `/quiz?customerId=${id}`;
	}, [customerId, fromParam]);

	async function submit() {
		setBusy(true);
		setError('');
		setResources([]);
		try {
			const id = Number(customerId);
			if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');
			const t = topic.trim();
			if (!t) throw new Error('Please enter a topic.');

			const res = await fetch(`${API_BASE}/api/resources/recommend`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ customer_id: id, topic: t, limit: 8 }),
			});
			const raw = await res.text().catch(() => '');
			const data = raw ? (() => {
				try {
					return JSON.parse(raw);
				} catch {
					return null;
				}
			})() : null;
			if (!res.ok) {
				const detail = data?.detail || raw || '';
				throw new Error(detail ? `Request failed (${res.status}): ${detail}` : `Request failed (${res.status})`);
			}
			const list = Array.isArray(data?.resources) ? data.resources : [];
			setResources(list.map(normalizeResource));
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	return (
		<div style={{ padding: 24, maxWidth: 980, margin: '0 auto' }}>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
				<h1 style={{ margin: 0 }}>Resource Recommendations</h1>
				<div style={{ display: 'flex', gap: 12 }}>
					<button onClick={() => navigate(backUrl)} disabled={busy}>
						Back
					</button>
					<Link to="/">
						Home
					</Link>
				</div>
			</div>

			<div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Customer ID</label>
					<input value={customerId} onChange={(e) => setCustomerId(e.target.value)} placeholder="46" style={{ width: '100%', padding: 10 }} />
				</div>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Topic</label>
					<input
						value={topic}
						onChange={(e) => setTopic(e.target.value)}
						placeholder="deductible, claims process, liability vs collision, discounts..."
						style={{ width: '100%', padding: 10 }}
					/>
				</div>
			</div>

			<div style={{ marginTop: 12, display: 'flex', gap: 12 }}>
				<button onClick={submit} disabled={!canSubmit} style={{ padding: '10px 20px', fontSize: 16 }}>
					{busy ? 'Loading…' : 'Get recommendations'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{resources.length ? (
				<div style={{ marginTop: 18 }}>
					<h3 style={{ marginTop: 0 }}>Recommended resources</h3>
					<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
						{resources.map((r, i) => (
							<div key={`${r.title}-${i}`} style={{ border: '1px solid #333', borderRadius: 10, padding: 12, background: '#071a2a' }}>
								<div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
									<strong style={{ fontSize: 16 }}>{r.title}</strong>
									<span style={{ opacity: 0.75, fontSize: 12, textTransform: 'uppercase' }}>{r.type}</span>
								</div>
								{r.summary ? <div style={{ marginTop: 8, opacity: 0.9, lineHeight: 1.5 }}>{r.summary}</div> : null}
								{r.url ? (
									<div style={{ marginTop: 10 }}>
										<a href={r.url} target="_blank" rel="noreferrer">
											Open
										</a>
									</div>
								) : null}
							</div>
						))}
					</div>
				</div>
			) : null}
		</div>
	);
}
