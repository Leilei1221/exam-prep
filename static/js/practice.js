// practice.js — 作答動畫 + AJAX 提交

async function submitAnswer(answer, questionId) {
  const dayNumber = document.getElementById('dayNumber')?.value || null;

  // Disable all options
  document.querySelectorAll('.btn-option').forEach(b => b.disabled = true);

  const r = await fetch('/api/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question_id: parseInt(questionId),
      answer: answer,
      mode: 'practice',
      day_number: dayNumber ? parseInt(dayNumber) : null,
    }),
  });

  const data = await r.json();
  showResult(data, answer);
}

async function submitMultiple() {
  const questionId = document.getElementById('questionId').value;
  const dayNumber = document.getElementById('dayNumber')?.value || null;

  const checked = Array.from(document.querySelectorAll('.multiple-opt:checked'))
    .map(el => el.value);

  if (checked.length === 0) {
    alert('請至少選擇一個選項');
    return;
  }

  const answer = checked.sort().join(',');

  // Disable
  document.querySelectorAll('.btn-option').forEach(b => b.disabled = true);
  document.querySelectorAll('.multiple-opt').forEach(el => el.disabled = true);

  const r = await fetch('/api/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question_id: parseInt(questionId),
      answer: answer,
      mode: 'practice',
      day_number: dayNumber ? parseInt(dayNumber) : null,
    }),
  });

  const data = await r.json();
  showMultipleResult(data, checked);
}

function showResult(data, userAnswer) {
  const correctAnswers = data.correct_answer.toUpperCase().split(',');

  // Color buttons
  document.querySelectorAll('.btn-option').forEach(btn => {
    const key = btn.querySelector('.option-key')?.textContent?.trim();
    if (!key) return;
    if (correctAnswers.includes(key)) {
      btn.classList.add('correct-answer');
    } else if (key === userAnswer && !data.is_correct) {
      btn.classList.add('wrong-answer');
    }
  });

  // Show result area
  const resultArea = document.getElementById('resultArea');
  const badge = document.getElementById('resultBadge');
  const exp = document.getElementById('explanationText');

  badge.innerHTML = data.is_correct
    ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>答對了！太棒了！</span>'
    : `<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>答錯了，正確答案：<span class="badge bg-success">${data.correct_answer}</span></span>`;

  exp.textContent = data.explanation || '';
  resultArea.classList.remove('d-none');

  // Scroll to result
  resultArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showMultipleResult(data, userAnswers) {
  const correctAnswers = data.correct_answer.toUpperCase().split(',');

  document.querySelectorAll('.option-btn').forEach(label => {
    const key = label.querySelector('.multiple-opt')?.value?.toUpperCase();
    if (!key) return;
    if (correctAnswers.includes(key)) {
      label.classList.add('correct-answer');
    } else if (userAnswers.includes(key) && !data.is_correct) {
      label.classList.add('wrong-answer');
    }
  });

  const resultArea = document.getElementById('resultArea');
  const badge = document.getElementById('resultBadge');
  const exp = document.getElementById('explanationText');

  badge.innerHTML = data.is_correct
    ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>全部答對！</span>'
    : `<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>答錯了，正確答案：<span class="badge bg-success">${data.correct_answer}</span></span>`;

  exp.textContent = data.explanation || '';
  resultArea.classList.remove('d-none');
  resultArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function nextQuestion() {
  const catId = document.getElementById('currentCategoryId')?.value;
  const diff = document.getElementById('currentDifficulty')?.value;
  const tags = document.getElementById('currentTags')?.value;
  const day = document.getElementById('dayNumber')?.value;

  const params = new URLSearchParams();
  if (catId) params.set('category_id', catId);
  if (diff) params.set('difficulty', diff);
  if (tags) params.set('tags', tags);
  if (day) params.set('day', day);

  window.location.href = '/practice' + (params.toString() ? '?' + params.toString() : '');
}
