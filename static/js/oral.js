// oral.js — SVG/Canvas 倒計時圓環

const TIMER_TOTAL = 180; // 3分鐘
let timerSeconds = TIMER_TOTAL;
let timerInterval = null;
let timerRunning = false;

const canvas = document.getElementById('timerCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const W = canvas ? canvas.width : 140;
const H = canvas ? canvas.height : 140;
const CX = W / 2;
const CY = H / 2;
const RADIUS = 56;
const STROKE = 10;

function drawTimer(remaining) {
  if (!ctx) return;
  ctx.clearRect(0, 0, W, H);

  // Background circle
  ctx.beginPath();
  ctx.arc(CX, CY, RADIUS, 0, Math.PI * 2);
  ctx.strokeStyle = '#e9ecef';
  ctx.lineWidth = STROKE;
  ctx.stroke();

  // Progress arc
  const ratio = remaining / TIMER_TOTAL;
  const startAngle = -Math.PI / 2;
  const endAngle = startAngle + (Math.PI * 2 * ratio);

  // Color transitions: green → yellow → red
  let color;
  if (ratio > 0.5) color = '#27AE60';
  else if (ratio > 0.25) color = '#F39C12';
  else color = '#E74C3C';

  ctx.beginPath();
  ctx.arc(CX, CY, RADIUS, startAngle, endAngle);
  ctx.strokeStyle = color;
  ctx.lineWidth = STROKE;
  ctx.lineCap = 'round';
  ctx.stroke();

  // Update display
  const display = document.getElementById('timerDisplay');
  if (display) {
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    display.textContent = `${m}:${s.toString().padStart(2, '0')}`;

    // Color the text too
    display.style.color = color;
  }
}

function startTimer() {
  if (timerRunning) return;
  timerRunning = true;

  const startBtn = document.getElementById('startBtn');
  if (startBtn) {
    startBtn.innerHTML = '<i class="bi bi-pause-fill me-1"></i>進行中';
    startBtn.disabled = true;
  }

  timerInterval = setInterval(() => {
    timerSeconds--;
    drawTimer(timerSeconds);

    if (timerSeconds <= 0) {
      clearInterval(timerInterval);
      timerRunning = false;
      const startBtn = document.getElementById('startBtn');
      if (startBtn) {
        startBtn.innerHTML = '<i class="bi bi-alarm me-1"></i>時間到！';
        startBtn.classList.remove('btn-success');
        startBtn.classList.add('btn-danger');
        startBtn.disabled = true;
      }
      // Vibrate if supported
      if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    }
  }, 1000);
}

function resetTimer() {
  clearInterval(timerInterval);
  timerRunning = false;
  timerSeconds = TIMER_TOTAL;
  drawTimer(timerSeconds);

  const startBtn = document.getElementById('startBtn');
  if (startBtn) {
    startBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i>開始計時';
    startBtn.classList.remove('btn-danger');
    startBtn.classList.add('btn-success');
    startBtn.disabled = false;
  }
}

// Initialize on load
if (canvas) {
  drawTimer(TIMER_TOTAL);
}
