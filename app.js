// RECURZ UI Logic - Coffee Cream & Black Theme

// Initialize Chart.js with coffee cream theme defaults
Chart.defaults.color = '#a39688'; 
Chart.defaults.borderColor = '#2a2622'; 
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

let trajectoryChart, participationChart, priceChart;

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  
  document.getElementById('btn-simulate').addEventListener('click', handleSimulation);
  document.getElementById('btn-benchmark').addEventListener('click', handleBenchmark);
});

function initCharts() {
  const ctxTraj = document.getElementById('trajectoryChart').getContext('2d');
  trajectoryChart = new Chart(ctxTraj, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Quantity Filled',
          data: [],
          borderColor: '#dcc4ab', // Coffee cream
          backgroundColor: 'rgba(220, 196, 171, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Target Schedule',
          data: [],
          borderColor: '#70655b', // Darker brown
          borderDash: [5, 5],
          fill: false,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end', labels: { boxWidth: 12 } } },
      scales: {
        y: { beginAtZero: true },
        x: { grid: { display: false } }
      }
    }
  });

  const ctxPart = document.getElementById('participationChart').getContext('2d');
  participationChart = new Chart(ctxPart, {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Participation %', data: [], backgroundColor: '#a39688', borderRadius: 4 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100 },
        x: { grid: { display: false } }
      }
    }
  });

  const ctxPrice = document.getElementById('priceChart').getContext('2d');
  priceChart = new Chart(ctxPrice, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Exec Price', data: [], borderColor: '#f4ebe1', tension: 0.4, fill: false }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } }
      }
    }
  });
}

function updateCharts(data) {
  const labels = data.map((_, i) => `T+${i}`);
  
  trajectoryChart.data.labels = labels;
  trajectoryChart.data.datasets[0].data = data.map(d => d.filled);
  trajectoryChart.data.datasets[1].data = data.map(d => d.target);
  trajectoryChart.update();

  participationChart.data.labels = labels;
  participationChart.data.datasets[0].data = data.map(d => d.participation);
  participationChart.update();

  priceChart.data.labels = labels;
  priceChart.data.datasets[0].data = data.map(d => d.price);
  priceChart.update();
}

async function handleSimulation() {
  const btn = document.getElementById('btn-simulate');
  btn.innerHTML = '<span class="animate-pulse text-[#141210]">Running...</span>';
  btn.disabled = true;
  
  document.getElementById('status-text').innerText = 'Simulating trajectory...';
  document.getElementById('event-log-container').classList.remove('hidden');

  try {
    // Simulate network delay
    await new Promise(r => setTimeout(r, 800));

    // Generate mock data representing a successful execution
    const steps = 15;
    let filled = 0;
    const total = parseFloat(document.querySelector('input[name="quantity"]').value) || 10000;
    let latestEvent = "Phase 1: Normal market conditions. Strategy executing along target schedule.";
    
    let basePrice = 150.00;
    
    const mockData = Array.from({ length: steps }).map((_, i) => {
      // Simulate market shock midway through
      let vol = 1.0;
      if (i === Math.floor(steps/2)) {
        latestEvent = `Interval T+${i}: WARNING - Market shock detected. Volatility increased by 300%. Liquidity reduced. Strategy dynamically slowing down execution to manage market impact.`;
      }
      
      if (i >= Math.floor(steps/2)) {
         vol = 3.0; // Higher volatility
      }
      
      let stepFill = (total / steps) * (0.8 + Math.random() * 0.4);
      
      // If adaptive strategy, slow down during shock
      if (i >= Math.floor(steps/2) && i < steps - 2) {
         stepFill *= 0.5; 
      } else if (i >= steps - 2) {
         stepFill *= 2.0; // Catch up at the end
      }
      
      filled = Math.min(total, filled + stepFill);
      if (i === steps - 1) filled = total; // ensure completion
      
      basePrice += (Math.random() * 2 - 1) * vol;
      
      return {
        filled: parseFloat(filled.toFixed(2)),
        target: parseFloat(((i + 1) * (total / steps)).toFixed(2)),
        participation: parseFloat((10 + (Math.random() * 5 * vol)).toFixed(1)),
        price: parseFloat(basePrice.toFixed(2))
      };
    });

    updateCharts(mockData);
    
    // Update metric cards
    document.getElementById('metric-filled').innerText = total.toLocaleString();
    document.getElementById('metric-price').innerText = "150.25";
    document.getElementById('metric-is').innerText = "-1.2 bps";
    document.getElementById('metric-cost').innerText = "145.50";
    
    document.getElementById('latest-event').innerText = latestEvent;
    document.getElementById('status-text').innerText = 'Simulation Complete';

  } catch (err) {
    console.error(err);
    alert('Simulation failed.');
  } finally {
    btn.innerHTML = 'Start Simulation';
    btn.disabled = false;
  }
}

async function handleBenchmark() {
  const btn = document.getElementById('btn-benchmark');
  btn.innerHTML = '<span class="animate-pulse">Running...</span>';
  btn.disabled = true;

  try {
    await new Promise(r => setTimeout(r, 1200));

    const tbody = document.getElementById('benchmark-body');
    tbody.innerHTML = `
      <tr class="border-b border-[#2a2622] hover:bg-[#1f1b18] transition-colors text-[#f4ebe1]">
        <td class="py-4 px-6 font-semibold flex items-center space-x-2">
          <div class="w-2.5 h-2.5 rounded-full bg-[#70655b]"></div><span>TWAP</span>
        </td>
        <td class="py-4 px-6">100.0%</td>
        <td class="py-4 px-6 text-[#ff8080] font-medium">8.5</td>
        <td class="py-4 px-6 text-[#ff8080] font-medium">8.5</td>
        <td class="py-4 px-6">450.00</td>
      </tr>
      <tr class="border-b border-[#2a2622] hover:bg-[#1f1b18] transition-colors text-[#f4ebe1]">
        <td class="py-4 px-6 font-semibold flex items-center space-x-2">
          <div class="w-2.5 h-2.5 rounded-full bg-[#a39688]"></div><span>Volume-Aware</span>
        </td>
        <td class="py-4 px-6">100.0%</td>
        <td class="py-4 px-6 text-[#ff8080] font-medium">5.2</td>
        <td class="py-4 px-6 text-[#ff8080] font-medium">5.2</td>
        <td class="py-4 px-6">325.50</td>
      </tr>
      <tr class="hover:bg-[#1f1b18] transition-colors bg-[#1f1b18]/50 text-[#f4ebe1]">
        <td class="py-4 px-6 font-bold flex items-center space-x-2">
          <div class="w-2.5 h-2.5 rounded-full bg-[#f4ebe1] shadow-[0_0_8px_rgba(244,235,225,0.6)]"></div><span>Adaptive (Dynamic)</span>
        </td>
        <td class="py-4 px-6 font-bold">100.0%</td>
        <td class="py-4 px-6 font-bold text-[#86efac]">-1.8</td>
        <td class="py-4 px-6 font-bold text-[#86efac]">-1.8</td>
        <td class="py-4 px-6 font-bold">182.20</td>
      </tr>
    `;

  } catch (err) {
    console.error(err);
  } finally {
    btn.innerHTML = 'Run Comparison';
    btn.disabled = false;
  }
}
