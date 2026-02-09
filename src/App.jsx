import { useMemo, useState } from 'react';
import { Routes, Route, useNavigate, useSearchParams, Link } from 'react-router-dom';
import './oai-styles.css';
import KnowledgeQuizPage from './KnowledgeQuizPage.jsx';

const API_BASE = '';


function OnboardingPage() {
	const navigate = useNavigate();
	const [message, setMessage] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [result, setResult] = useState(null);
	const [status, setStatus] = useState('');

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
		setStatus('');
		try {
			const profile = parseOnboardingSentence(message);

			const existingRes = await fetch(`${API_BASE}/api/customers/${profile.id}`);
			if (existingRes.ok) {
				const existingData = await existingRes.json();
				setResult(existingData);
				setStatus('exists');
				navigate(`/curriculum?customerId=${profile.id}`);
				return;
			}
			if (existingRes.status !== 404) {
				let msg = `Lookup failed (${existingRes.status})`;
				try {
					const err = await existingRes.json();
					msg = err?.detail || msg;
				} catch {
					
				}
				throw new Error(msg);
			}

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
	const canSubmit = useMemo(() => query.trim().length > 0 && !busy, [query, busy]);
	const nextUrl = useMemo(() => {
		const id = Number(customerId);
		return Number.isFinite(id) && id > 0 ? `/teacher?customerId=${id}` : '/teacher';
	}, [customerId]);

	function _extractCustomerId() {
		const id = Number(customerId);
		if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');
		return id;
	}

	function _isShowRequest(text) {
		const t = (text || '').toLowerCase();
		return t.includes('curriculum') && (t.includes('show') || t.includes('view') || t.includes('get') || t.includes('see'));
				// (resources route removed)
	}

	function _isPlanRequest(text) {
		const t = (text || '').toLowerCase();
		return t.includes('curriculum') && (t.includes('plan') || t.includes('create') || t.includes('generate') || t.includes('make'));
	}

	async function submit() {
		setBusy(true);
		setError('');
		setNotice('');
		setAction('');
		setShowNext(false);
		setResult(null);
		try {
			const id = _extractCustomerId();
			const text = query.trim();

			let res;
			const isShow = _isShowRequest(text);
			const isPlan = _isPlanRequest(text);
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
				setNotice('Done.');
				setShowNext(true);
				return;
			}

			setResult(data);
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
					<ol style={{ textAlign: 'left' }}>
						{result.curriculum.map((m, idx) => (
							<li key={idx} style={{ marginBottom: 8 }}>
								<div style={{ fontWeight: 600 }}>{m.module}</div>
								<div style={{ opacity: 0.9 }}>{m.description}</div>
							</li>
						))}
					</ol>
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
			// Default the module selector to the first module order, if present
			const firstOrder = (data?.curriculum || [])?.[0]?.order;
			if (firstOrder != null) setModuleOrder(String(firstOrder));
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	function _ytSearchUrl(query) {
		const q = encodeURIComponent(String(query || '').trim() || 'auto insurance basics');
		return `https://www.youtube.com/results?search_query=${q}`;
	}

	function curatedVideoUrlForModuleTitle(title) {
		const t = String(title || '').trim();
		if (!t) return _ytSearchUrl('auto insurance basics');

		// Exact topic-to-video mapping per hackathon requirements.
		// If a topic is specified as “YouTube search”, we intentionally return a search URL.
		const map = {
			'What is Insurance?': 'https://www.youtube.com/watch?v=SYnKjo8nbpg',
			'Understanding Deductibles': 'https://www.youtube.com/watch?v=UoPN84v2KrU',
			'Steps to Take During a Car Accident': _ytSearchUrl('what to do after a car accident steps YouTube'),
			"Do’s and Don’ts of Safe Driving": _ytSearchUrl("safe driving tips do’s and don’ts YouTube"),
			"Do's and Don'ts of Safe Driving": _ytSearchUrl("safe driving tips do’s and don’ts YouTube"),
			'What is a Premium?': 'https://www.youtube.com/watch?v=cWEiafGi4QE',
			'What is a Claim?': _ytSearchUrl('what is an insurance claim explained YouTube'),
			'How to File a Claim': 'https://www.youtube.com/watch?v=lsq4hD6kg8o',
			'What is Coverage?': 'https://www.youtube.com/watch?v=WaXyCIHVtXg',
			'Types of Coverage for Auto Insurance': 'https://www.youtube.com/watch?v=q6ztnQLLZkg',
			'Factors Affecting Insurance Rates': _ytSearchUrl('factors affecting auto insurance rates explained'),
			'Tips for First-Time Drivers': 'https://www.youtube.com/watch?v=_sHAmGoKDWs',
			'How Insurance Works for Young Drivers': 'https://www.youtube.com/watch?v=VJOMUeBvRWw',
			'Impact of Driving History on Insurance Rates': _ytSearchUrl('impact of driving history on insurance rates YouTube'),
			'The Importance of Safe Driving Courses': _ytSearchUrl('importance of safe driving courses insurance YouTube'),
			'How to Maintain a Clean Driving Record': _ytSearchUrl('maintaining clean driving record tips YouTube'),
			'Understanding Insurance Requirements for Student Drivers': _ytSearchUrl('student driver insurance requirements YouTube'),
			'Common Auto Insurance Terms Explained': _ytSearchUrl('common auto insurance terms explained YouTube'),
			'How to Choose the Right Insurance Plan': _ytSearchUrl('how to choose right car insurance plan YouTube'),
			'Importance of Liability Coverage': _ytSearchUrl('What Is Liability Insurance Coverage? YouTube'),
			'Understanding Comprehensive and Collision Coverage': _ytSearchUrl('comprehensive vs collision coverage YouTube'),
			'How to Lower Your Insurance Premiums': _ytSearchUrl('how to lower insurance premiums YouTube'),
			'Seasonal Driving Tips & Insurance Implications': _ytSearchUrl('seasonal driving tips insurance implications YouTube'),
			'Impact of Traffic Violations on Insurance Rates': _ytSearchUrl('traffic violations effect on insurance rates YouTube'),
			'How to Read Your Insurance Policy': _ytSearchUrl('how to read car insurance policy YouTube'),
			'Benefits of Bundling Insurance Policies': _ytSearchUrl('benefits of bundling insurance policies YouTube'),
			'Understanding No-Fault Insurance': _ytSearchUrl('no fault insurance explained YouTube'),
			'What to Do in Case of a Total Loss': _ytSearchUrl('total loss claim explained car insurance YouTube'),
			'How to Handle Uninsured Motorist Situations': _ytSearchUrl('Uninsured Motorist Insurance Explained YouTube'),
			'Importance of Regular Vehicle Maintenance for Insurance': _ytSearchUrl('importance of vehicle maintenance insurance YouTube'),
			'How to Update Your Insurance Policy': _ytSearchUrl('how to update insurance policy YouTube'),
			'Understanding Policy Endorsements': _ytSearchUrl('policy endorsements auto insurance explained YouTube'),
			'The Claims Process: Step-by-Step Guide': _ytSearchUrl('How Do Car Insurance Claims Work? YouTube'),
			'How to Dispute a Denied Claim': _ytSearchUrl('dispute denied car insurance claim YouTube'),
			'The Role of an Insurance Adjuster': _ytSearchUrl('insurance adjuster role explained YouTube'),
			'Understanding Rental Car Coverage': _ytSearchUrl('rental car coverage explained auto insurance YouTube'),
			'How to Switch Insurance Providers': _ytSearchUrl('how to switch auto insurance companies YouTube'),
			'Impact of Life Changes on Insurance Needs': _ytSearchUrl('impact of life changes on insurance needs YouTube'),
			'Understanding Roadside Assistance Coverage': _ytSearchUrl('roadside assistance coverage explained YouTube'),
			'The Importance of Accurate Vehicle Info': _ytSearchUrl('accurate vehicle info auto insurance YouTube'),
			'How to Avoid Insurance Fraud': _ytSearchUrl('how to avoid insurance fraud YouTube'),
			'Understanding Gap Insurance': _ytSearchUrl('understanding gap insurance YouTube'),
			'The Role of Telematics in Auto Insurance': _ytSearchUrl('telematics auto insurance YouTube'),
			'Difference Between Actual Cash Value & Replacement Cost': _ytSearchUrl('ACV vs replacement cost car insurance YouTube'),
			'How to Handle Multiple Vehicles on One Policy': _ytSearchUrl('multiple vehicles one policy auto insurance YouTube'),
			'Impact of Driving History on Insurance': _ytSearchUrl('driving history impact insurance rates YouTube'),
			'Understanding Grace Period for Premium Payments': _ytSearchUrl('grace period premium payments car insurance YouTube'),
			'How to Get Discounts on Auto Insurance': _ytSearchUrl('how to get discounts on auto insurance YouTube'),
			'Importance of Reviewing Policy Annually': _ytSearchUrl('importance reviewing insurance policy YouTube'),
			'Difference Between State Minimums & Recommended Coverage': _ytSearchUrl('state minimum vs recommended coverage auto insurance YouTube'),
			'How to Handle Insurance After a Move': _ytSearchUrl('insurance after move auto insurance YouTube'),
			'The Role of Family Members in a Policy': _ytSearchUrl('role of family members insurance policy YouTube'),
			'Impact of Vehicle Modifications on Insurance': _ytSearchUrl('vehicle modifications insurance impact YouTube'),
			'How to Choose a Deductible Amount': _ytSearchUrl('how to choose a deductible amount YouTube'),
			"Importance of Documenting Your Vehicle’s Condition": _ytSearchUrl('importance documenting vehicle condition for claims YouTube'),
			"Importance of Documenting Your Vehicle's Condition": _ytSearchUrl('importance documenting vehicle condition for claims YouTube'),
			'Difference Between Personal & Commercial Auto Insurance': _ytSearchUrl('personal vs commercial auto insurance YouTube'),
		};

		if (map[t]) return map[t];
		// Safe fallback for any other module title.
		return _ytSearchUrl(t);
	}

	const selectedModule = useMemo(() => {
		const mo = Number(moduleOrder);
		if (!Array.isArray(curriculum)) return null;
		return curriculum.find((m) => Number(m?.order) === mo) || null;
	}, [curriculum, moduleOrder]);
	const selectedModuleTitle = useMemo(() => (selectedModule?.module ? String(selectedModule.module) : ''), [selectedModule]);
	const effectiveVideoUrl = useMemo(() => curatedVideoUrlForModuleTitle(selectedModuleTitle), [selectedModuleTitle]);
	const quizUrl = useMemo(() => {
		const id = Number(customerId);
		const mo = Number(moduleOrder);
		if (!Number.isFinite(id) || id <= 0) return '/quiz';
		if (Number.isFinite(mo) && mo > 0) return `/quiz?customerId=${id}&moduleOrder=${mo}`;
		return `/quiz?customerId=${id}`;
	}, [customerId, moduleOrder]);

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
					<ol style={{ textAlign: 'left' }}>
						{curriculum.map((m, idx) => (
							<li key={idx} style={{ marginBottom: 8 }}>
								<div style={{ fontWeight: 600 }}>
									{m.order}. {m.module}
								</div>
								<div style={{ opacity: 0.9 }}>{m.description}</div>
							</li>
						))}
					</ol>

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
											{m?.order}. {m?.module}
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

			{/* Teach functionality removed: no lesson panel */}

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
			<Route path='/quiz' element={<KnowledgeQuizPage />} />
			{/* resources route removed */}
		</Routes>
	);
}
