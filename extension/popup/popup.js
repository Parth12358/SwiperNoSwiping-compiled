// SwiperNoSwiping — Popup logic
// Stats panel + onboarding form

const BACKEND_URL = 'http://localhost:8000';
const USER_ID = 1;

// --- API helpers ---

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// --- Toast ---

function showToast(message, type) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type} show`;
  setTimeout(() => { toast.classList.remove('show'); }, 3000);
}

// --- Stats ---

async function loadStats() {
  try {
    const data = await apiFetch(`/api/stats/${USER_ID}`);
    document.getElementById('stat-denied').textContent = data.denied_count ?? '—';
    document.getElementById('stat-approved').textContent = data.approved_count ?? '—';
    document.getElementById('stat-saved').textContent = data.saved_cents
      ? `$${(data.saved_cents / 100).toFixed(2)}`
      : '—';
    document.getElementById('stat-category').textContent = data.top_category || '—';
  } catch {
    document.getElementById('stat-denied').textContent = '—';
    document.getElementById('stat-approved').textContent = '—';
    document.getElementById('stat-saved').textContent = '—';
    document.getElementById('stat-category').textContent = '—';
  }
}

// --- Profile ---

async function loadProfile() {
  try {
    const data = await apiFetch(`/api/profile/${USER_ID}`);
    const form = document.getElementById('profile-form');
    form.display_name.value = data.display_name || '';
    form.income_band.value = data.income_band || '';
    form.monthly_budget_dollars.value = data.monthly_budget_cents
      ? (data.monthly_budget_cents / 100).toString()
      : '';
    form.savings_goal.value = data.savings_goal || '';
    form.goal_target_dollars.value = data.goal_target_cents
      ? (data.goal_target_cents / 100).toString()
      : '';
    form.known_weakness.value = data.known_weakness || '';
  } catch {
    // no profile yet — that's fine
  }
}

async function saveProfile(e) {
  e.preventDefault();
  const form = e.target;
  const body = {
    user_id: USER_ID,
    display_name: form.display_name.value,
    income_band: form.income_band.value,
    monthly_budget_cents: Math.round(parseFloat(form.monthly_budget_dollars.value || '0') * 100),
    savings_goal: form.savings_goal.value,
    goal_target_cents: Math.round(parseFloat(form.goal_target_dollars.value || '0') * 100),
    known_weakness: form.known_weakness.value,
  };

  try {
    await fetch(`${BACKEND_URL}/api/profile/${USER_ID}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    showToast('Profile saved.', 'success');
    showStatsPanel();
    loadStats();
  } catch {
    showToast('Failed to save profile.', 'error');
  }
}

// --- Navigation ---

function showStatsPanel() {
  document.getElementById('stats-panel').style.display = 'block';
  document.getElementById('profile-panel').style.display = 'none';
}

function showProfilePanel() {
  document.getElementById('stats-panel').style.display = 'none';
  document.getElementById('profile-panel').style.display = 'block';
  loadProfile();
}

// --- Init ---

document.getElementById('btn-edit-profile').addEventListener('click', showProfilePanel);
document.getElementById('btn-back').addEventListener('click', showStatsPanel);
document.getElementById('profile-form').addEventListener('submit', saveProfile);

loadStats();
