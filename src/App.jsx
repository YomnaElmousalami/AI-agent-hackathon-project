import { useMemo, useState } from 'react';
import { Routes, Route, useNavigate, useSearchParams, Link } from 'react-router-dom';
import './oai-styles.css';
import KnowledgeQuizPage from './KnowledgeQuizPage.jsx';
import ResourceRecommendationPage from './ResourceRecommendationPage.jsx';
import AccidentReportingPage from './AccidentReportingPage.jsx';
import AccidentSeverityPage from './AccidentSeverityPage.jsx';
import PolicyInterpretationPage from './PolicyInterpretationPage.jsx';
import ClaimsPreparationPage from './ClaimsPreparationPage.jsx';
import ActionPlanPage from './ActionPlanPage.jsx';
import EscalationPage from './EscalationPage.jsx';

const API_BASE = 'http://127.0.0.1:8801';

// --- Module-level pure helpers ---
// Defined outside components so they are never re-allocated on re-render.

function parseOnboardingSentence(text) {
	const s = (text || '').trim();
	if (!s) throw new Error('Please enter your credentials first.');

	const idMatch = s.match(/\b(?:id\s*(?:is)?\s*)(\d+)\b/i) || s.match(/\b(\d+)\b/);
	if (!idMatch) throw new Error("Couldn't find an id (number) in your message.");
	const id = Number(idMatch[1]);

	const ageMatch = s.match(/\b(?:i\s*['']?m|i\s*am|age\s*(?:is)?)\s*(\d{1,3})\b/i);
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

function extractCustomerId(customerId) {
	const id = Number(customerId);
	if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');
	return id;
}

function isShowRequest(text) {
	const t = (text || '').toLowerCase();
	return t.includes('curriculum') && (t.includes('show') || t.includes('view') || t.includes('get') || t.includes('see'));
}

function isPlanRequest(text) {
	const t = (text || '').toLowerCase();
	return t.includes('curriculum') && (t.includes('plan') || t.includes('create') || t.includes('generate') || t.includes('make'));
}

function stripLeadingModuleNumber(title) {
	const raw = String(title || '').trim();
	return raw.replace(/^\s*\d+\s*[\.)-]\s*/, '').trim() || raw;
}

function ytSearchUrl(query) {
	const q = encodeURIComponent(String(query || '').trim() || 'auto insurance basics');
	return `https://www.youtube.com/results?search_query=${q}`;
}

function curatedVideoUrlForModuleTitle(title) {
	const t = String(title || '').trim();
	if (!t) return ytSearchUrl('auto insurance basics');
	return CURATED_VIDEO_MAP[t] || ytSearchUrl(t);
}

// Module-level constant — defined once, never re-allocated on re-render.
const CURATED_VIDEO_MAP = {
	'What is Car Insurance?': 'https://www.youtube.com/watch?v=q6ztnQLLZkg&t=372s',
	'Understanding Deductibles': 'https://www.youtube.com/watch?v=UoPN84v2KrU&t=3s',
	'Steps to Take During a car accident.': 'https://www.youtube.com/watch?v=wToIYkLuwPY',
	"Do's and Don'ts of Safe Driving": 'https://www.youtube.com/watch?v=qoaF04Lsux4',
	'What is a premium?': 'https://www.youtube.com/watch?v=Ly3tiv7f4Hg',
	'What is a claim?': 'https://www.youtube.com/watch?v=S-I6ZLrF3oQ',
	'How to file a claim?': 'https://www.youtube.com/watch?v=lsq4hD6kg8o',
	'What is coverage?': 'https://www.youtube.com/watch?v=iAXvv9BM-3U',
	'Types of coverage for auto insurance': 'https://www.youtube.com/watch?v=g8uMWX1JcC4',
	'Factors affecting insurance rates': 'https://www.youtube.com/watch?v=-QfmcoYYb5E',
	'Understanding the impact of driving history on insurance rates': 'https://www.youtube.com/watch?v=e5ESP_FtOzo',
	'How to maintain a clean driving record': 'https://www.youtube.com/watch?v=csO9yYp-vYE',
	'Common auto insurance terms explained': 'https://www.youtube.com/watch?v=TVA2xaWzsSY',
	'How to choose the right insurance plan': 'https://www.youtube.com/watch?v=LWDPRx3k4-8',
	'Importance of liability coverage': 'https://www.youtube.com/watch?v=sulcwnaHAvI',
	'Understanding comprehensive and collision coverage': 'https://www.youtube.com/watch?v=lMcxwBLOpjs',
	'How to lower your insurance premiums': 'https://www.youtube.com/watch?v=IRi5Z7pp1K4',
	'Seasonal driving tips and insurance implications': 'https://www.youtube.com/watch?v=46xdKVgTbJE',
	'Impact of traffic violations on insurance rates': 'https://www.youtube.com/watch?v=x-N0jCGr0Bg',
	'How to read your insurance policy': 'https://www.youtube.com/watch?v=NYwZVxYe8QU',
	'Benefits of bundling insurance policies': 'https://www.youtube.com/watch?v=M_tpraTiJMk',
	'Understanding no-fault insurance': 'https://www.youtube.com/watch?v=stdqM-OTmyk',
	'What to do in case of a total loss': 'https://www.youtube.com/watch?v=Ynbgf5uda7Q',
	'How to handle uninsured motorist situations': 'https://www.youtube.com/watch?v=jcuN4jDCE3M',
	'Understanding policy endorsements': 'https://www.youtube.com/watch?v=am8XBrdFHfU',
	'How to dispute a denied claim': 'https://www.youtube.com/watch?v=vsdXq0WOH8M',
	'Understanding rental car coverage': 'https://www.youtube.com/watch?v=s6LcnFEqQxY',
};


function OnboardingPage() {
	const navigate = useNavigate();
	const [message, setMessage] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [status, setStatus] = useState('');
	const [llmResponse, setLlmResponse] = useState('');

	const canSubmit = useMemo(() => message.trim().length > 0 && !busy, [message, busy]);

	async function submit() {
		setBusy(true);
		setError('');
		setResult(null);
		setStatus('');
		setLlmResponse('');
		try {
			const profile = parseOnboardingSentence(message);

			const res = await fetch(`${API_BASE}/api/onboard`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ message }),
			});
			const raw = await res.text().catch(() => '');
			const data = raw
				? (() => {
					try {
						return JSON.parse(raw);
					} catch {
						return null;
					}
				})()
				: null;
			if (!res.ok) {
				const detail = data?.detail || raw || 'Onboarding failed';
				throw new Error(detail);
			}
			if (!data) {
				throw new Error('Onboarding succeeded, but the server returned an empty response.');
			}
			setResult(data);
			setStatus('saved');
			navigate(`/curriculum?customerId=${profile.id}`);
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
					{status === 'exists' ? (
						<h3 style={{ fontSize: '24px', margin: 0 }}>This user already exists</h3>
					) : (
						<h3 style={{ fontSize: '24px', margin: 0 }}>Saved!</h3>
					)}
					<div style={{ marginTop: 8 }}>
						<Link to={result?.parsed?.id ? `/curriculum?customerId=${result.parsed.id}` : '/curriculum'}>
							Continue to Curriculum Planner
						</Link>
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


function CurriculumPlannerPage() {
	const [searchParams] = useSearchParams();
	const customerIdParam = searchParams.get('customerId') || '';
	const [customerId, setCustomerId] = useState(customerIdParam);
	const [query, setQuery] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [notice, setNotice] = useState('');
	const [action, setAction] = useState('');
	const [showNext, setShowNext] = useState(false);
	const [llmResponse, setLlmResponse] = useState('');
	const canSubmit = useMemo(() => query.trim().length > 0 && !busy, [query, busy]);
	const nextUrl = useMemo(() => {
		const id = Number(customerId);
		return Number.isFinite(id) && id > 0 ? `/teacher?customerId=${id}` : '/teacher';
	}, [customerId]);

	async function submit() {
		setBusy(true);
		setError('');
		setNotice('');
		setAction('');
		setShowNext(false);
		setResult(null);
		setLlmResponse('');
		try {
			const id = extractCustomerId(customerId);
			const text = query.trim();

			let res;
			const isShow = isShowRequest(text);
			const isPlan = isPlanRequest(text);
			setAction(isShow ? 'show' : isPlan ? 'plan' : '');

			if (isShow) {
				res = await fetch(`${API_BASE}/api/curriculum/${id}`);
			} else if (isPlan) {
				res = await fetch(`${API_BASE}/api/curriculum/plan`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ customer_id: id }),
				});
			} else {
				throw new Error("Type something like: 'Plan a curriculum' or 'Show the curriculum'.");
			}

			let data = null;
			try {
				data = await res.json();
			} catch {
				data = null;
			}

			if (!res.ok) {
				if (res.status === 404) {
					setNotice(data?.detail || 'No curriculum found yet. Try planning one first.');
					setShowNext(true);
					return;
				}
				throw new Error(data?.detail || `Request failed (${res.status})`);
			}

			if (isPlan) {
				if (data?.llmResponse) {
					setLlmResponse(String(data.llmResponse));
				}
				setNotice('Done.');
				setShowNext(true);
				return;
			}

			setResult(data);
			if (data?.llmResponse) {
				setLlmResponse(String(data.llmResponse));
			}
			setShowNext(true);
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	return (
		<div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Curriculum Planner</h1>
				<Link to='/' style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Onboarding
				</Link>
			</div>

			<div style={{ marginTop: 12 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>Customer id</label>
				<input
					value={customerId}
					onChange={(e) => setCustomerId(e.target.value)}
					style={{ width: 240, padding: 10 }}
					placeholder='e.g. 2'
				/>
			</div>

			<div style={{ marginTop: 12 }}>
				<label style={{ display: 'block', marginBottom: 6 }}>What do you want to do?</label>
				<textarea
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					rows={3}
					style={{ width: 'min(720px, 100%)', padding: 12 }}
					placeholder="Examples: 'Plan a curriculum' or 'Show the curriculum'"
				/>
			</div>

			<div style={{ marginTop: 12 }}>
				<button onClick={submit} disabled={!canSubmit} style={{ fontSize: '16px', padding: '10px 44px' }}>
					{busy ? 'Working…' : 'Enter'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{notice ? (
				<div style={{ marginTop: 16, background: '#001b2b', border: '1px solid #004466', padding: 12 }}>
					<strong>{action === 'plan' && notice === 'Done.' ? 'Status' : 'Note'}:</strong> {notice}
				</div>
			) : null}

			{result?.curriculum ? (
				<div style={{ marginTop: 16 }}>
					<h3 style={{ marginTop: 0 }}>Curriculum</h3>
					<ul style={{ textAlign: 'left', listStyle: 'none', paddingLeft: 0 }}>
						{result.curriculum.map((m, idx) => (
							<li key={idx} style={{ marginBottom: 8 }}>
								<div style={{ fontWeight: 600 }}>{m.module}</div>
							</li>
						))}
					</ul>
				</div>
			) : null}

			{llmResponse ? (
				<div style={{ marginTop: 16, background: '#0b1a2b', border: '1px solid #1f3b5d', padding: 12 }}>
					<strong>Assistant response:</strong>
					<div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{llmResponse}</div>
				</div>
			) : null}

			{showNext ? (
				<div style={{ marginTop: 16 }}>
					<Link to={nextUrl} style={{ display: 'inline-block' }}>
						<button style={{ fontSize: '16px', padding: '10px 44px' }}>Next</button>
					</Link>
				</div>
			) : null}
		</div>
	);
}


function TeacherAgentPage() {
	const [searchParams] = useSearchParams();
	const customerIdParam = searchParams.get('customerId') || '';
	const [customerId, setCustomerId] = useState(customerIdParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const [curriculum, setCurriculum] = useState(null);
	const [moduleOrder, setModuleOrder] = useState('');

	const canLoadCurriculum = useMemo(() => !busy && String(customerId).trim().length > 0, [busy, customerId]);

	async function loadCurriculum() {
		setBusy(true);
		setError('');
		setNotice('');
		try {
			const id = Number(customerId);
			if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');
			const res = await fetch(`${API_BASE}/api/curriculum/${id}`);
			const data = await res.json().catch(() => null);
			if (!res.ok) {
				if (res.status === 404) {
					setNotice(data?.detail || 'No curriculum found yet. Go back and plan one first.');
					setCurriculum(null);
					return;
				}
				throw new Error(data?.detail || `Failed to load curriculum (${res.status})`);
			}
			setCurriculum(data?.curriculum || []);
			const firstOrder = (data?.curriculum || [])?.[0]?.order;
			if (firstOrder != null) setModuleOrder(String(firstOrder));
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	const selectedModule = useMemo(() => {
		const mo = Number(moduleOrder);
		if (!Array.isArray(curriculum)) return null;
		return curriculum.find((m) => Number(m?.order) === mo) || null;
	}, [curriculum, moduleOrder]);
	const selectedModuleTitle = useMemo(
		() => (selectedModule?.module ? stripLeadingModuleNumber(String(selectedModule.module)) : ''),
		[selectedModule]
	);
	const effectiveVideoUrl = useMemo(() => curatedVideoUrlForModuleTitle(selectedModuleTitle), [selectedModuleTitle]);
	const quizUrl = useMemo(() => {
		const id = Number(customerId);
		const mo = Number(moduleOrder);
		if (!Number.isFinite(id) || id <= 0) return '/quiz';
		if (Number.isFinite(mo) && mo > 0) return `/quiz?customerId=${id}&moduleOrder=${mo}`;
		return `/quiz?customerId=${id}`;
	}, [customerId, moduleOrder]);

	const agentLinks = useMemo(() => {
		const id = Number(customerId);
		const qs = new URLSearchParams();
		if (Number.isFinite(id) && id > 0) qs.set('customerId', String(id));
		const q = qs.toString();
		return {
			accident: `/accident${q ? `?${q}` : ''}`,
		};
	}, [customerId]);

	return (
		<div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Welcome to your Agentic AI Tutor</h1>
				<Link to='/' style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Onboarding
				</Link>
			</div>

			<div style={{ marginTop: 16 }}>
				<div style={{ opacity: 0.95, lineHeight: 1.6 }}>
					<div>Step 1: load your curriculum. Step 2: pick a module.</div>
				</div>
			</div>

			<div style={{ marginTop: 12, background: '#001b2b', border: '1px solid #004466', padding: 12 }}>
				<strong>Accident / Claims agents:</strong>{' '}
				<Link to={agentLinks.accident} style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Start Accident Report
				</Link>
			</div>

			<div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Customer id</label>
					<input
						value={customerId}
						onChange={(e) => setCustomerId(e.target.value)}
						style={{ width: 240, padding: 10 }}
						placeholder='e.g. 46'
					/>
				</div>
				<button onClick={loadCurriculum} disabled={!canLoadCurriculum} style={{ fontSize: '16px', padding: '10px 44px' }}>
					{busy ? 'Loading…' : 'Load Curriculum'}
				</button>
			</div>

			{error ? (
				<div style={{ marginTop: 16, background: '#2b0000', border: '1px solid #660000', padding: 12 }}>
					<strong>Problem:</strong> {error}
				</div>
			) : null}

			{notice ? (
				<div style={{ marginTop: 16, background: '#001b2b', border: '1px solid #004466', padding: 12 }}>
					<strong>Note:</strong> {notice}
				</div>
			) : null}

			{Array.isArray(curriculum) ? (
				<div style={{ marginTop: 16 }}>
					<h2 style={{ margin: 0 }}>Your Curriculum</h2>
					<p style={{ marginTop: 8, opacity: 0.95 }}>Pick a module, then watch the video or take a quiz.</p>
					<ul style={{ textAlign: 'left', listStyle: 'none', paddingLeft: 0 }}>
						{curriculum.map((m, idx) => (
							<li key={idx} style={{ marginBottom: 8 }}>
								<div style={{ fontWeight: 600 }}>{stripLeadingModuleNumber(m.module)}</div>
							</li>
						))}
					</ul>

					<div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: 12 }}>
						<div>
							<label style={{ display: 'block', marginBottom: 6 }}>Module</label>
							<select
								value={moduleOrder}
								onChange={(e) => setModuleOrder(e.target.value)}
								disabled={!Array.isArray(curriculum) || curriculum.length === 0}
								style={{ width: 520, maxWidth: '100%', padding: 10 }}
							>
								{Array.isArray(curriculum) && curriculum.length ? null : <option value=''>Load curriculum first…</option>}
								{Array.isArray(curriculum)
									? curriculum.map((m) => (
											<option key={String(m?.order ?? m?.module)} value={String(m?.order ?? '')}>
												{stripLeadingModuleNumber(m?.module)}
											</option>
										))
									: null}
							</select>
						</div>
						<Link to={quizUrl} style={{ display: 'inline-block' }}>
							<button disabled={busy} style={{ fontSize: '16px', padding: '10px 24px' }}>
								Take a Quiz
							</button>
						</Link>
					</div>

					<div style={{ marginTop: 16 }}>
						<h3 style={{ marginTop: 0, marginBottom: 8 }}>Video link</h3>
						<div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
							<a
								href={effectiveVideoUrl}
								target='_blank'
								rel='noreferrer'
								style={{ display: 'inline-block' }}
							>
								<button style={{ fontSize: '16px', padding: '10px 44px' }}>Watch a video for this topic</button>
							</a>
							{selectedModuleTitle ? (
								<div style={{ opacity: 0.9 }}>
									Selected: <span style={{ fontWeight: 600 }}>{selectedModuleTitle}</span>
								</div>
							) : null}
						</div>
					</div>
				</div>
			) : null}

			{}

			<div style={{ marginTop: 16 }}>
				<Link to={customerIdParam ? `/curriculum?customerId=${customerIdParam}` : '/curriculum'} style={{ color: '#ffffff' }}>
					Back to Curriculum Planner
				</Link>
			</div>
		</div>
	);
}


function CustomerIdLine({ customerId }) {
	if (!customerId) return <span>Select a customer to begin.</span>;
	return <span>Customer id: {customerId}</span>;
}


export default function App() {
	return (
		<Routes>
			<Route path='/' element={<OnboardingPage />} />
			<Route path='/curriculum' element={<CurriculumPlannerPage />} />
			<Route path='/teacher' element={<TeacherAgentPage />} />
			<Route path='/accident' element={<AccidentReportingPage />} />
			<Route path='/severity' element={<AccidentSeverityPage />} />
			<Route path='/policy' element={<PolicyInterpretationPage />} />
			<Route path='/claims' element={<ClaimsPreparationPage />} />
			<Route path='/action-plan' element={<ActionPlanPage />} />
			<Route path='/escalation' element={<EscalationPage />} />
			<Route path='/quiz' element={<KnowledgeQuizPage />} />
			<Route path='/resources' element={<ResourceRecommendationPage />} />
		</Routes>
	);
}
