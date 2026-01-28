import { useMemo, useState } from 'react';
import './oai-styles.css';

const API_BASE = '';

export default function App() {
	const [message, setMessage] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);

	const canSubmit = useMemo(() => message.trim().length > 0 && !busy, [message, busy]);

	function parseOnboardingSentence(text) {
		const s = (text || '').trim();
		if (!s) throw new Error('Please enter your credentials first.');

		const idMatch = s.match(/\b(?:id\s*(?:is)?\s*)(\d+)\b/i) || s.match(/\b(\d+)\b/);
		if (!idMatch) throw new Error("Couldn't find an id (number) in your message.");
		const id = Number(idMatch[1]);

		const ageMatch = s.match(/\b(?:i\s*['’]?m|i\s*am|age\s*(?:is)?)\s*(\d{1,3})\b/i);
		if (!ageMatch) throw new Error("Couldn't find an age in your message (e.g. I'm 16).");
		const age = Number(ageMatch[1]);

		const stateMatch = s.match(/\b(?:live\s*in|i\s*live\s*in|state\s*(?:is)?)\s*([A-Za-z]{2})\b/i);
		if (!stateMatch) throw new Error("Couldn't find a 2-letter state code (e.g. VA, NY).");
		const state = String(stateMatch[1]).toUpperCase();

		const nameMatch = s.match(/\bmy\s*name\s*is\s*([^,\.]+)\b/i);
		if (!nameMatch) throw new Error("Couldn't find 'my name is ...' in your message.");
		const name = String(nameMatch[1]).trim();

		const vehicleMatch = s.match(/\b(?:vehicle\s*(?:is)?|car\s*(?:is)?)\s*(?:a\s+|an\s+)?([^,\.]+)\b/i);
		if (!vehicleMatch) throw new Error("Couldn't find 'my vehicle is ...' in your message.");
		const vehicleName = String(vehicleMatch[1]).trim();

		const coverageMatch = s.match(/\bcoverage\s*(?:type\s*)?is\s*([^,\.]+)\b/i);
		if (!coverageMatch) throw new Error("Couldn't find 'coverage type is ...' in your message.");
		const coverageType = String(coverageMatch[1]).trim();

		return { id, name, age, state, vehicleName, coverageType };
	}

	async function submit() {
		setBusy(true);
		setError('');
		setResult(null);
		try {
			const profile = parseOnboardingSentence(message);

			const res = await fetch(`${API_BASE}/api/profile`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(profile),
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
			<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
				<h1 style={{ marginBottom: 8 }}>Auto Insurance User Onboarding</h1>

				<div style={{ lineHeight: 1.6, marginBottom: 12 }}>
					<div>Hello and welcome to Auto Insurance User Onboarding</div>
					<div>Please type in your credentials and press Enter</div>
				</div>

				<textarea
					value={message}
					onChange={(e) => setMessage(e.target.value)}
					rows={4}
					style={{ width: 'min(720px, 100%)', padding: 12, marginTop: 8 }}
					placeholder="My id is 46, my name is Alex, I'm 16, I live in VA, my vehicle is a Honda Accord, and my coverage type is liability"
				/>

				<div style={{ display: 'flex', justifyContent: 'center', width: '100%', marginTop: 12 }}>
					<button onClick={submit} disabled={!canSubmit} style={{ fontSize: '16px', padding: '10px 44px' }}>
						{busy ? 'Saving\u2026' : 'Enter'}
					</button>
				</div>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{result ? (
				<div style={{ marginTop: 16, textAlign: 'center' }}>
					<h3 style={{ margin: 0 }}>Saved!</h3>
				</div>
			) : null}
		</div>
	);
}
