import { useMemo, useState } from 'react';
import './oai-styles.css';

const API_BASE = 'http://127.0.0.1:8001';

export default function App() {
	const [message, setMessage] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);

	const canSubmit = useMemo(() => message.trim().length > 0 && !busy, [message, busy]);

	async function submit() {
		setBusy(true);
		setError('');
		setResult(null);
		try {
			const res = await fetch(`${API_BASE}/api/onboard`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ message }),
			});
			const data = await res.json();
			if (!res.ok) {
				throw new Error(data?.detail || 'Onboarding failed');
			}
			setResult(data);
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	return (
		<div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
			<h1>Auto Insurance User Onboarding</h1>

			<div style={{ marginTop: 8, lineHeight: 1.5 }}>
				<div>Hello and welcome to Auto Insurance User Onboarding</div>
				<div>Please type in your credentials and press Enter</div>
				<div>Once you&apos;re done, type &apos;exit&apos; to quit</div>
				<div>Here is a sample message:</div>
				<div style={{ marginTop: 8, opacity: 0.9 }}>
					Hey. My id is 2, my name is Samuel, I&apos;m 16, I live in NY, my vehicle
					is a Toyota Camry, and my coverage type is full coverage.
				</div>
			</div>

			<label style={{ display: 'block', marginTop: 16, fontWeight: 600 }}>Onboarding sentence</label>
			<textarea
				value={message}
				onChange={(e) => setMessage(e.target.value)}
				rows={4}
				style={{ width: '100%', padding: 12, marginTop: 8 }}
				placeholder="My id is 46, my name is Alex, I'm 16, I live in VA, my vehicle is a Honda Accord, and my coverage type is liability"
			/>

			<div style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center' }}>
				<button onClick={submit} disabled={!canSubmit} style={{ padding: '10px 14px' }}>
					{busy ? 'Saving…' : 'Enter'}
				</button>
				<span style={{ opacity: 0.75 }}>{API_BASE}</span>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16 }}>
					<h3>Saved</h3>
					<pre style={{ whiteSpace: 'pre-wrap', background: '#111', padding: 12 }}>
						{JSON.stringify(result, null, 2)}
					</pre>
				</div>
			) : null}
		</div>
	);
}
