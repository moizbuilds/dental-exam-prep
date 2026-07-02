import { supabase } from "../supabaseClient";

// Shuffle helper (Fisher–Yates) — used to randomize question order.
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const Q_COLS =
  "id,domain,subdomain,stem,options,correct_index,correct_explanation," +
  "distractor_rationales,source_book,source_edition,source_page_or_section," +
  "supporting_quote,diagram_svg,visual_type,image_url,difficulty";

// How many verified questions exist per subdomain (for the topic selector).
export async function fetchCounts() {
  const { data, error } = await supabase
    .from("questions")
    .select("domain,subdomain")
    .eq("verification_status", "pass");
  if (error) throw error;
  const counts = {};
  for (const row of data) counts[row.subdomain] = (counts[row.subdomain] || 0) + 1;
  return counts;
}

// Practice: pull a randomized set for one subdomain.
export async function fetchPractice(subdomain, limit = 20) {
  const { data, error } = await supabase
    .from("questions")
    .select(Q_COLS)
    .eq("verification_status", "pass")
    .eq("subdomain", subdomain)
    .limit(200);
  if (error) throw error;
  return shuffle(data).slice(0, limit);
}

// Mock: assemble a 150-question exam in blueprint proportions.
export async function fetchMock(blueprint) {
  const { data, error } = await supabase
    .from("questions")
    .select(Q_COLS)
    .eq("verification_status", "pass")
    .limit(2000);
  if (error) throw error;
  const bySub = {};
  for (const q of data) (bySub[q.subdomain] ||= []).push(q);
  const exam = [];
  for (const b of blueprint) {
    const pool = shuffle(bySub[b.subdomain] || []);
    exam.push(...pool.slice(0, b.mock));
  }

  // Rebalance difficulty: target 30% easy / 50% medium / 20% hard across 150q
  const TARGETS = { easy: 45, medium: 75, hard: 30 };
  const buckets = { easy: [], medium: [], hard: [] };
  for (const q of exam) buckets[q.difficulty || "medium"].push(q);

  const balanced = [];
  for (const level of ["easy", "medium", "hard"]) {
    balanced.push(...shuffle(buckets[level]).slice(0, TARGETS[level]));
  }
  // Fill any shortfall from medium (largest pool)
  const shortage = 150 - balanced.length;
  if (shortage > 0) {
    const used = new Set(balanced.map((q) => q.id));
    const spare = shuffle(exam.filter((q) => !used.has(q.id)));
    balanced.push(...spare.slice(0, shortage));
  }
  return shuffle(balanced);
}

// Record an answer for analytics + spaced repetition.
export async function recordAnswer(userId, questionId, correct) {
  const { error } = await supabase.from("user_progress").insert({
    user_id: userId,
    question_id: questionId,
    answered_correctly: correct,
  });
  if (error) throw error;
}

// All progress rows for the signed-in user (analytics + review).
export async function fetchProgress(userId) {
  const { data, error } = await supabase
    .from("user_progress")
    .select("question_id,answered_correctly,answered_at")
    .eq("user_id", userId)
    .order("answered_at", { ascending: false });
  if (error) throw error;
  return data;
}

// Spaced-repetition review: questions the user most recently got wrong
// and has not since answered correctly.
export async function fetchReviewQueue(userId, limit = 20) {
  const progress = await fetchProgress(userId);
  const latest = {}; // question_id -> most recent correctness
  for (const p of progress) {
    if (!(p.question_id in latest)) latest[p.question_id] = p.answered_correctly;
  }
  const wrongIds = Object.entries(latest)
    .filter(([, correct]) => !correct)
    .map(([id]) => id);
  if (wrongIds.length === 0) return [];
  const { data, error } = await supabase
    .from("questions")
    .select(Q_COLS)
    .eq("verification_status", "pass")
    .in("id", wrongIds.slice(0, 100));
  if (error) throw error;
  return shuffle(data).slice(0, limit);
}
