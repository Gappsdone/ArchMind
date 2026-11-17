import { useEffect, useState } from 'react';
import { api, type InvestigationRecord, type InvestigationReply } from './api';

type Selection = { projectId: string; snapshotId: string; edgeId: string; sourceId: string; targetId: string; relationship: string };

export function Investigation({ selection }: { selection: Selection }) {
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setRecord(null); setQuestion(''); setError(''); }, [selection.edgeId, selection.snapshotId]);
  async function ask(prompt = question) {
    if (!prompt.trim() || busy) return;
    setBusy(true); setError('');
    try {
      const session = record ?? await api.createInvestigation(selection);
      if (!record) setRecord(session);
      const reply = await api.askInvestigation(session.id, prompt.trim());
      setRecord({ ...session, turns: [...session.turns, { role: 'user', content: prompt.trim() }, { role: 'assistant', content: reply }] });
      setQuestion('');
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }
  return <div className="inspector-block investigation-panel">
    <h3>Architecture assistant</h3>
    <p className="muted">Questions stay bound to this edge and snapshot. AI output is a proposal, never an automatic edit.</p>
    <div className="investigation-prompts"><button type="button" disabled={busy} onClick={() => void ask('Where is this dependency coming from?')}>Explain origin</button><button type="button" disabled={busy} onClick={() => void ask('How could I remove or reduce this dependency? Give alternatives and a detailed plan.')}>Explore removal</button></div>
    {record?.turns.map((turn, index) => turn.role === 'user' ? <p className="investigation-question" key={index}>You: {String(turn.content)}</p> : <AssistantReply key={index} reply={turn.content as InvestigationReply} />)}
    {error && <p role="alert" className="error-banner">{error}</p>}
    <form onSubmit={event => { event.preventDefault(); void ask(); }}><label htmlFor="investigation-question">Follow-up question</label><textarea id="investigation-question" value={question} maxLength={4000} onChange={event => setQuestion(event.target.value)} placeholder="Ask about this relationship…" /><button type="submit" disabled={busy || !question.trim()}>{busy ? 'Investigating…' : 'Ask'}</button></form>
  </div>;
}

function AssistantReply({ reply }: { reply: InvestigationReply }) {
  return <div className="investigation-answer"><strong>AI interpretation · proposal only</strong><p>{reply.answer}</p>
    {reply.findings.length > 0 && <><h4>Citation-linked findings</h4>{reply.findings.map((item, i) => <p key={i}>{item.text} <small>Citations: {item.citation_ids.join(', ')}</small></p>)}</>}
    {reply.hypotheses.length > 0 && <><h4>Unverified hypotheses</h4><ul>{reply.hypotheses.map((item, i) => <li key={i}>{item}</li>)}</ul></>}
    {reply.uncertainty.length > 0 && <><h4>Known unknowns</h4><ul>{reply.uncertainty.map((item, i) => <li key={i}>{item}</li>)}</ul></>}
    {reply.alternatives.length > 0 && <><h4>Refactoring alternatives</h4>{reply.alternatives.map((item, i) => <div className="alternative-card" key={i}><strong>{item.title}</strong><p>{item.rationale}</p><p><b>Impact:</b> {item.impact} · <b>Complexity:</b> {item.complexity}</p><p><b>Targets:</b> {item.affected_targets.join(', ') || 'Not established'} · <b>Files:</b> {item.affected_files.join(', ') || 'Not established'}</p><p><b>Trade-offs:</b> {item.tradeoffs.join('; ') || 'Not specified'}</p><p><b>Risks:</b> {item.risks.join('; ') || 'Not specified'}</p><ol>{item.plan_steps.map((step, j) => <li key={j}>{step}</li>)}</ol></div>)}</>}
  </div>;
}
