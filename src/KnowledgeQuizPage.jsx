import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

const API_BASE = '';

function normalizeQuestion(q) {
	const type = String(q?.type || 'multiple_choice');
	const choices = Array.isArray(q?.choices) ? q.choices : [];
	return {
		id: String(q?.id || ''),
		type,
		prompt: String(q?.question || q?.prompt || ''),
		choices,
		moduleOrder: q?.moduleOrder ?? null,
		moduleTitle: String(q?.moduleTitle || q?.topic || ''),
		expected: q?.expected,
		explanation: q?.explanation,
		weight: q?.weight,
	};
}

export default function KnowledgeQuizPage() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const customerIdParam = searchParams.get('customerId') || '';
	const moduleOrderParam = searchParams.get('moduleOrder') || '';

	const [customerId, setCustomerId] = useState(customerIdParam);
	const [moduleOrder, setModuleOrder] = useState(moduleOrderParam);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const [curriculum, setCurriculum] = useState([]);
	const [loadingCurriculum, setLoadingCurriculum] = useState(false);

	const [attemptId, setAttemptId] = useState('');
	const [questions, setQuestions] = useState([]);
	const [idx, setIdx] = useState(0);
	const [selected, setSelected] = useState('');
	const [graded, setGraded] = useState(null);
	const [score, setScore] = useState({ earned: 0, possible: 0, correct: 0, total: 0 });
	const [isFinished, setIsFinished] = useState(false);

	const current = useMemo(() => (questions[idx] ? normalizeQuestion(questions[idx]) : null), [questions, idx]);

	const canStart = useMemo(() => {
		const id = Number(customerId);
		return !busy && Number.isFinite(id) && id > 0;
	}, [busy, customerId]);

	useEffect(() => {
		let cancelled = false;
		const id = Number(customerId);
		if (!Number.isFinite(id) || id <= 0) {
			setCurriculum([]);
			return () => {
				cancelled = true;
			};
		}

		setLoadingCurriculum(true);
		fetch(`${API_BASE}/api/curriculum/${id}`)
			.then((res) => res.json().catch(() => null).then((data) => ({ ok: res.ok, status: res.status, data })))
			.then(({ ok, data }) => {
				if (cancelled) return;
				if (!ok) {
					setCurriculum([]);
					return;
				}
				const list = Array.isArray(data?.curriculum) ? data.curriculum : [];
				setCurriculum(list);
				// If user hasn't selected a module yet, default to the first module.
				if (!moduleOrder && list.length && list[0]?.order != null) {
					setModuleOrder(String(list[0].order));
				}
			})
			.catch(() => {
				if (cancelled) return;
				setCurriculum([]);
			})
			.finally(() => {
				if (cancelled) return;
				setLoadingCurriculum(false);
			});

		return () => {
			cancelled = true;
		};
		// Intentionally only reacts to customerId changes.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [customerId]);

	async function startQuiz() {
		setBusy(true);
		setError('');
		setNotice('');
		setGraded(null);
		setSelected('');
		setQuestions([]);
		setIdx(0);
		setScore({ earned: 0, possible: 0, correct: 0, total: 0 });
		setIsFinished(false);
		try {
			const id = Number(customerId);
			if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');

			const mo = moduleOrder ? Number(moduleOrder) : null;
			const moduleOrderBody = mo != null && Number.isFinite(mo) && mo > 0 ? mo : null;

			// Start attempt (persisted)
			const startRes = await fetch(`${API_BASE}/api/knowledge/attempts/start`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ customer_id: id, questions_limit: 10, module_order: moduleOrderBody }),
			});
			const startData = await startRes.json().catch(() => null);
			if (!startRes.ok) {
				throw new Error(startData?.detail || `Failed to start quiz (${startRes.status})`);
			}
			const newAttemptId = String(startData?.attemptId || '');
			setAttemptId(newAttemptId);
			if (!newAttemptId) {
				throw new Error('Failed to start quiz (missing attemptId).');
			}

			// Fetch questions for display
			const qRes = await fetch(`${API_BASE}/api/knowledge/questions`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				// IMPORTANT: tie questions to the same attempt to keep question_ids consistent
				// between "start attempt" and "answer".
				body: JSON.stringify({
					customer_id: id,
					limit: 10,
					module_order: moduleOrderBody,
					attempt_id: newAttemptId,
				}),
			});
			const qData = await qRes.json().catch(() => null);
			if (!qRes.ok) {
				throw new Error(qData?.detail || `Failed to load questions (${qRes.status})`);
			}
			const qs = Array.isArray(qData?.questions) ? qData.questions : [];
			if (qs.length === 0) {
				throw new Error('No questions available yet. Make sure you planned a curriculum first.');
			}
			setQuestions(qs);

			// Record module view if module is selected
			if (moduleOrderBody != null) {
				fetch(`${API_BASE}/api/knowledge/module_view`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ customer_id: id, module_order: moduleOrderBody }),
				}).catch(() => null);
			}

			setNotice('Quiz started. Good luck!');
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	function choiceLabel(i) {
		return ['A', 'B', 'C', 'D'][i] || String(i + 1);
	}

	function OptionRow({ value, label, text }) {
		const disabled = busy || graded != null;
		const isSelected = selected === String(value);
		return (
			<button
				type='button'
				disabled={disabled}
				onClick={() => setSelected(String(value))}
				style={{
					width: '100%',
					display: 'block',
					textAlign: 'left',
					padding: '10px 12px',
					borderRadius: 8,
					border: isSelected ? '2px solid #4da3ff' : '1px solid #333',
					background: isSelected ? '#001b2b' : '#0b0b0f',
					color: '#fff',
					cursor: disabled ? 'not-allowed' : 'pointer',
					fontSize: 15,
					lineHeight: 1.4,
				}}
			>
				<span
					style={{
						fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
						fontWeight: 700,
						marginRight: 8,
					}}
				>
					{label})
				</span>
				<span>{text}</span>
			</button>
		);
	}

	async function submitAnswer() {
		setBusy(true);
		setError('');
		setNotice('');
		try {
			const id = Number(customerId);
			if (!Number.isFinite(id) || id <= 0) throw new Error('Missing/invalid customer id.');
			if (!attemptId) throw new Error('Quiz attempt not started.');
			if (!current?.id) throw new Error('No current question.');
			if (!selected) throw new Error('Please pick an answer.');

			const normalizedAnswer =
				current?.type === 'true_false' || current?.type === 'true/false'
					? String(selected).toLowerCase()
					: String(selected);

			const res = await fetch(`${API_BASE}/api/knowledge/attempts/answer`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					customer_id: id,
					attempt_id: attemptId,
					question_id: current.id,
					answer: normalizedAnswer,
				}),
			});
			const data = await res.json().catch(() => null);
			if (!res.ok) {
				throw new Error(
					data?.detail ||
					`Answer submit failed (${res.status}) [qid=${String(current.id)}; attempt=${String(attemptId)}]`
				);
			}

			setGraded(data);
			const correct = Boolean(data?.correct);
			const earned = Number(data?.score ?? 0);
			const possible = Number(data?.weight ?? 0);
			setScore((s) => ({
				earned: s.earned + earned,
				possible: s.possible + possible,
				correct: s.correct + (correct ? 1 : 0),
				total: s.total + 1,
			}));
		} catch (e) {
			setError(e?.message || String(e));
		} finally {
			setBusy(false);
		}
	}

	function nextQuestion() {
		setGraded(null);
		setSelected('');
		setNotice('');
		if (idx + 1 >= questions.length) {
			setNotice('You finished the quiz!');
			setIsFinished(true);
			return;
		}
		setIdx((i) => i + 1);
	}

	async function retryQuiz() {
		await startQuiz();
	}

	useEffect(() => {
		if (customerIdParam && String(customerIdParam) !== String(customerId)) return;
		// no-op
	}, [customerIdParam, customerId]);

	const progressText = useMemo(() => {
		if (!questions.length) return '';
		return `Question ${idx + 1} of ${questions.length}`;
	}, [questions.length, idx]);

	const teacherBackUrl = useMemo(() => {
		const id = Number(customerId || customerIdParam);
		return Number.isFinite(id) && id > 0 ? `/teacher?customerId=${id}` : '/teacher';
	}, [customerId, customerIdParam]);

	const resourcesUrl = useMemo(() => {
		const id = Number(customerId || customerIdParam);
		if (!Number.isFinite(id) || id <= 0) return '/resources?from=quiz';
		// Default topic: prefer module title if available, otherwise a generic starter.
		const topicText = String(
			curriculum.find((m) => String(m?.order ?? '') === String(moduleOrder))?.module ||
			'auto insurance basics'
		);
		return `/resources?customerId=${id}&topic=${encodeURIComponent(topicText)}&from=quiz`;
	}, [customerId, customerIdParam, curriculum, moduleOrder]);

	return (
		<div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
				<h1 style={{ margin: 0 }}>Knowledge Check Quiz</h1>
				<Link to='/' style={{ color: '#ffffff', textDecoration: 'underline' }}>
					Back to Onboarding
				</Link>
			</div>

			<div style={{ marginTop: 16, opacity: 0.95, lineHeight: 1.6 }}>
				<div>Start a short quiz to confirm understanding.</div>
			</div>

			<div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: 12 }}>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Customer id</label>
					<input value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 240, padding: 10 }} placeholder='e.g. 46' />
				</div>
				<div>
					<label style={{ display: 'block', marginBottom: 6 }}>Module</label>
					<select
						value={moduleOrder}
						onChange={(e) => setModuleOrder(e.target.value)}
						disabled={busy || loadingCurriculum || !curriculum.length}
						style={{ width: 420, maxWidth: '100%', padding: 10 }}
					>
						{!curriculum.length ? <option value=''>{loadingCurriculum ? 'Loading modules…' : 'Load curriculum first…'}</option> : null}
						{curriculum.map((m) => (
							<option key={String(m?.order ?? m?.module)} value={String(m?.order ?? '')}>
								{m?.order}. {m?.module}
							</option>
						))}
					</select>
				</div>
				<button onClick={startQuiz} disabled={!canStart} style={{ fontSize: '16px', padding: '10px 44px' }}>
					{busy ? 'Starting…' : 'Start quiz'}
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

			{questions.length ? (
				<div style={{ marginTop: 20 }}>
					<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
						<h2 style={{ margin: 0 }}>{progressText}</h2>
						<div style={{ opacity: 0.9 }}>
							Score: {score.earned.toFixed(1)} / {score.possible.toFixed(1)} ({score.correct}/{score.total} correct)
						</div>
					</div>

					{isFinished ? (
						<div style={{ marginTop: 12, background: '#0b0b0f', border: '1px solid #222', padding: 14, borderRadius: 8 }}>
							<h2 style={{ marginTop: 0 }}>Quiz complete</h2>
							<div style={{ marginTop: 8, opacity: 0.95, lineHeight: 1.6 }}>
								<div>
									Final score: <strong>{score.earned.toFixed(1)}</strong> / <strong>{score.possible.toFixed(1)}</strong>
								</div>
								<div>
									Correct: <strong>{score.correct}</strong> out of <strong>{score.total}</strong>
								</div>
							</div>

							<div style={{ marginTop: 14, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
								<button onClick={retryQuiz} disabled={busy} style={{ fontSize: '16px', padding: '10px 30px' }}>
									{busy ? 'Restarting…' : 'Retry same quiz'}
								</button>
								<button onClick={() => navigate(resourcesUrl)} disabled={busy} style={{ fontSize: '16px', padding: '10px 18px' }}>
									Get learning resources
								</button>
								<button onClick={() => navigate(teacherBackUrl)} disabled={busy} style={{ fontSize: '16px', padding: '10px 18px' }}>
									Back to Teacher
								</button>
							</div>
						</div>
					) : current ? (
						<div style={{ marginTop: 12, background: '#0b0b0f', border: '1px solid #222', padding: 14, borderRadius: 8 }}>
							<div style={{ marginTop: 8, fontSize: 18, fontWeight: 600 }}>{current.prompt}</div>

							<div style={{ marginTop: 12 }}>
								{current.type === 'true_false' ? (
									<ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none' }}>
										<li style={{ marginTop: 10, paddingLeft: 0 }}>
											<OptionRow value='true' label='A' text='True' />
										</li>
										<li style={{ marginTop: 10, paddingLeft: 0 }}>
											<OptionRow value='false' label='B' text='False' />
										</li>
									</ul>
								) : (
									<ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none' }}>
										{current.choices.map((c, i) => (
											<li key={i} style={{ marginTop: 10, paddingLeft: 0 }}>
												<OptionRow
													value={choiceLabel(i)}
													label={choiceLabel(i)}
													text={String(c)}
												/>
											</li>
										))}
									</ul>
								)}
							</div>

							<div style={{ marginTop: 14, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
								<button onClick={submitAnswer} disabled={busy || graded != null} style={{ fontSize: '16px', padding: '10px 30px' }}>
									{busy ? 'Submitting…' : 'Submit'}
								</button>
								<button onClick={nextQuestion} disabled={busy || graded == null} style={{ fontSize: '16px', padding: '10px 30px' }}>
									Next
								</button>
								<button
									onClick={() => navigate(teacherBackUrl)}
									disabled={busy}
									style={{ fontSize: '16px', padding: '10px 18px' }}
								>
									Back to Teacher
								</button>
							</div>

							{selected ? (
								<div style={{ marginTop: 10, opacity: 0.85, fontSize: 13 }}>
									Selected: <span style={{ fontFamily: 'monospace' }}>{selected}</span>
								</div>
							) : null}

							{graded ? (
									<div style={{ marginTop: 14, padding: 12, border: '1px solid #333', borderRadius: 8, background: graded.correct ? '#001b2b' : '#2b0000' }}>
										<div>
											<strong>{graded.correct ? 'Correct' : 'Not quite'}</strong>
											{graded.correct ? <> — {graded.feedback}</> : null}
										</div>
										{/* Per UX request: don't show any explanation text under quiz results. */}
									</div>
							) : null}
						</div>
					) : null}
				</div>
			) : null}
		</div>
	);
}
