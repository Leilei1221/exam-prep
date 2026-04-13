// dashboard.js — Chart.js 圖表

function initCharts(last7, catStats) {
  // ─── 近7天作答量 Bar Chart ───
  const weekCtx = document.getElementById('weekChart');
  if (weekCtx) {
    new Chart(weekCtx, {
      type: 'bar',
      data: {
        labels: last7.map(d => d.date),
        datasets: [
          {
            label: '作答題數',
            data: last7.map(d => d.done),
            backgroundColor: 'rgba(43,127,191,.7)',
            borderRadius: 6,
            borderSkipped: false,
          },
          {
            label: '答對題數',
            data: last7.map(d => d.correct),
            backgroundColor: 'rgba(39,174,96,.7)',
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'top',
            labels: { boxWidth: 12, font: { size: 12 } },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: 'rgba(0,0,0,.06)' },
          },
          x: {
            grid: { display: false },
          },
        },
      },
    });
  }

  // ─── 各分類題庫統計 Horizontal Bar ───
  const catCtx = document.getElementById('catChart');
  if (catCtx && catStats.length > 0) {
    new Chart(catCtx, {
      type: 'bar',
      data: {
        labels: catStats.map(c => c.name.substring(0, 8)),
        datasets: [
          {
            label: '題庫數量',
            data: catStats.map(c => c.question_count),
            backgroundColor: 'rgba(43,127,191,.6)',
            borderRadius: 4,
          },
          {
            label: '已作答',
            data: catStats.map(c => c.total),
            backgroundColor: 'rgba(22,160,133,.6)',
            borderRadius: 4,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: {
          legend: {
            position: 'top',
            labels: { boxWidth: 12, font: { size: 12 } },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: 'rgba(0,0,0,.06)' },
          },
          y: {
            grid: { display: false },
          },
        },
      },
    });
  }
}
