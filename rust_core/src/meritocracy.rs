use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
struct Candidate {
    backend: String,
    provider: String,
    model: String,
    text: String,
    ok: bool,
    latency_ms: f64,
    error: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct QualityScore {
    adequacy: f64,
    relevance: f64,
    thread_relevance: f64,
    coherence: f64,
    hallucination_risk: f64,
    overall: f64,
    notes: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct RankedCandidate {
    backend: String,
    provider: String,
    model: String,
    ok: bool,
    latency_ms: f64,
    error: Option<String>,
    quality: QualityScore,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct SelectionPolicy {
    min_overall: f64,
    min_relevance: f64,
    min_thread_relevance: f64,
    max_hallucination_risk: f64,
}

impl Default for SelectionPolicy {
    fn default() -> Self {
        Self {
            min_overall: 0.35,
            min_relevance: 0.25,
            min_thread_relevance: 0.25,
            max_hallucination_risk: 0.65,
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct SelectionResult {
    selected_backend: String,
    selected_provider: String,
    selected_model: String,
    selected_quality: QualityScore,
    ranking: Vec<RankedCandidate>,
}

fn clamp(value: f64, low: f64, high: f64) -> f64 {
    value.max(low).min(high)
}

fn tokenize(text: &str) -> Vec<String> {
    let mut tokens: Vec<String> = Vec::new();
    let mut current = String::new();
    for ch in text.chars() {
        if ch.is_alphanumeric() || matches!(ch, '_' | '+' | '.' | '-') {
            for lower in ch.to_lowercase() {
                current.push(lower);
            }
        } else if !current.is_empty() {
            tokens.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

fn meaningful_tokens(text: &str) -> Vec<String> {
    const STOPWORDS: &[&str] = &[
        "и", "в", "во", "на", "с", "со", "к", "ко", "по", "за", "из", "у", "о", "об", "от",
        "а", "но", "или", "что", "как", "почему", "зачем", "где", "когда", "чем", "это",
        "этот", "эта", "эти", "the", "a", "an", "and", "or", "to", "of", "for", "in", "on",
    ];
    tokenize(text)
        .into_iter()
        .filter(|token| token.len() > 1 && !STOPWORDS.contains(&token.as_str()))
        .collect()
}

fn overlap(a: &[String], b: &[String]) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let mut matches = 0usize;
    for token in a {
        if b.contains(token) {
            matches += 1;
        }
    }
    matches as f64 / a.len().max(1) as f64
}

fn cause_cue_score(answer: &str) -> f64 {
    let answer_lower = answer.to_lowercase();
    let cues = ["потому что", "так как", "поскольку", "because", "since", "due to", "из-за"];
    if cues.iter().any(|cue| answer_lower.contains(cue)) {
        1.0
    } else {
        0.0
    }
}

fn structure_score(answer: &str) -> f64 {
    let text = answer.trim();
    if text.is_empty() {
        return 0.0;
    }
    let mut score = 0.45;
    if matches!(text.chars().last(), Some('.' | '!' | '?' | ':')) {
        score += 0.25;
    }
    if text.split_whitespace().count() >= 8 {
        score += 0.15;
    }
    if [";", "\n", " - ", "- "].iter().any(|sep| text.contains(sep)) {
        score += 0.10;
    }
    clamp(score, 0.0, 1.0)
}

fn specificity_risk(question: &str, answer: &str, thread_context: &str) -> f64 {
    let q_tokens = meaningful_tokens(question);
    let t_tokens = meaningful_tokens(thread_context);
    let a_tokens = meaningful_tokens(answer);
    let digit_count = answer.chars().filter(|c| c.is_ascii_digit()).count();
    let grounded_overlap = a_tokens
        .iter()
        .filter(|token| q_tokens.contains(*token) || t_tokens.contains(*token))
        .count();

    let mut risk = 0.15;
    risk += (digit_count as f64 * 0.05).min(0.20);
    risk -= (grounded_overlap as f64 * 0.04).min(0.20);
    if a_tokens.len() < 8 {
        risk += 0.10;
    }
    if answer.contains('?') {
        risk += 0.05;
    }
    clamp(risk, 0.0, 1.0)
}

fn evaluate_quality(question: &str, answer: &str, thread_context: &str) -> QualityScore {
    if answer.trim().is_empty() {
        return QualityScore {
            adequacy: 0.0,
            relevance: 0.0,
            thread_relevance: 0.0,
            coherence: 0.0,
            hallucination_risk: 1.0,
            overall: 0.0,
            notes: vec!["empty-answer".to_string()],
        };
    }

    let q_terms = meaningful_tokens(question);
    let a_terms = meaningful_tokens(answer);
    let t_terms = meaningful_tokens(thread_context);
    let lexical_overlap = clamp(overlap(&q_terms, &a_terms), 0.0, 1.0);
    let thread_overlap = clamp(overlap(&t_terms, &a_terms), 0.0, 1.0);
    let cause = cause_cue_score(answer);
    let structure = structure_score(answer);
    let adequacy = clamp(0.30 + 0.25 * cause + 0.45 * structure, 0.0, 1.0);
    let relevance = clamp(0.55 * lexical_overlap + 0.25 * cause + 0.20 * structure, 0.0, 1.0);
    let thread_relevance = clamp(0.60 * thread_overlap + 0.20 * cause + 0.20 * structure, 0.0, 1.0);
    let coherence = clamp(0.65 * structure + 0.35 * (answer.split_whitespace().count() as f64 / 18.0).min(1.0), 0.0, 1.0);
    let hallucination_risk = specificity_risk(question, answer, thread_context);
    let overall = clamp(
        0.30 * adequacy
            + 0.30 * relevance
            + 0.20 * thread_relevance
            + 0.20 * coherence
            - 0.20 * hallucination_risk,
        0.0,
        1.0,
    );

    let mut notes: Vec<String> = Vec::new();
    if relevance < 0.35 {
        notes.push("low-question-overlap".to_string());
    }
    if thread_relevance < 0.35 {
        notes.push("low-thread-alignment".to_string());
    }
    if coherence < 0.45 {
        notes.push("weak-structure".to_string());
    }
    if hallucination_risk > 0.55 {
        notes.push("high-specificity-risk".to_string());
    }
    if notes.is_empty() {
        notes.push("balanced".to_string());
    }

    QualityScore {
        adequacy: (adequacy * 1000.0).round() / 1000.0,
        relevance: (relevance * 1000.0).round() / 1000.0,
        thread_relevance: (thread_relevance * 1000.0).round() / 1000.0,
        coherence: (coherence * 1000.0).round() / 1000.0,
        hallucination_risk: (hallucination_risk * 1000.0).round() / 1000.0,
        overall: (overall * 1000.0).round() / 1000.0,
        notes,
    }
}

#[pyfunction]
#[pyo3(signature = (question, thread_context=None, candidates_json=\"[]\", policy_json=None))]
pub fn meritocracy_select_json(
    question: &str,
    thread_context: Option<&str>,
    candidates_json: &str,
    policy_json: Option<&str>,
) -> PyResult<String> {
    let thread = thread_context.unwrap_or(question);
    let candidates: Vec<Candidate> = serde_json::from_str(candidates_json)
        .map_err(|e| PyValueError::new_err(format!("invalid candidates json: {}", e)))?;
    let policy: SelectionPolicy = match policy_json {
        Some(raw) if !raw.trim().is_empty() => serde_json::from_str(raw)
            .map_err(|e| PyValueError::new_err(format!("invalid policy json: {}", e)))?,
        _ => SelectionPolicy::default(),
    };

    let mut ranked: Vec<RankedCandidate> = candidates
        .into_iter()
        .map(|candidate| RankedCandidate {
            backend: candidate.backend,
            provider: candidate.provider,
            model: candidate.model,
            ok: candidate.ok,
            latency_ms: candidate.latency_ms,
            error: candidate.error,
            quality: evaluate_quality(question, &candidate.text, thread),
        })
        .collect();

    ranked.sort_by(|a, b| {
        let a_key = (
            if a.ok { 1 } else { 0 },
            (a.quality.overall * 1000.0) as i64,
            (a.quality.relevance * 1000.0) as i64,
            (a.quality.thread_relevance * 1000.0) as i64,
            -((a.quality.hallucination_risk * 1000.0) as i64),
            -(a.latency_ms as i64),
        );
        let b_key = (
            if b.ok { 1 } else { 0 },
            (b.quality.overall * 1000.0) as i64,
            (b.quality.relevance * 1000.0) as i64,
            (b.quality.thread_relevance * 1000.0) as i64,
            -((b.quality.hallucination_risk * 1000.0) as i64),
            -(b.latency_ms as i64),
        );
        b_key.cmp(&a_key)
    });

    if ranked.is_empty() {
        return Err(PyValueError::new_err("no candidates provided"));
    }

    let selected = ranked
        .iter()
        .find(|item| {
            item.quality.overall >= policy.min_overall
                && item.quality.relevance >= policy.min_relevance
                && item.quality.thread_relevance >= policy.min_thread_relevance
                && item.quality.hallucination_risk <= policy.max_hallucination_risk
        })
        .unwrap_or(&ranked[0])
        .clone();

    let result = SelectionResult {
        selected_backend: selected.backend.clone(),
        selected_provider: selected.provider.clone(),
        selected_model: selected.model.clone(),
        selected_quality: selected.quality.clone(),
        ranking: ranked,
    };
    serde_json::to_string(&result)
        .map_err(|e| PyValueError::new_err(format!("failed to serialize result: {}", e)))
}
