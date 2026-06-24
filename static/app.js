let chartInstance = null;
const clusterColors = [
    'rgba(248, 113, 113, 0.8)', // Red
    'rgba(251, 191, 36, 0.8)',  // Amber
    'rgba(52, 211, 153, 0.8)',  // Emerald
    'rgba(129, 140, 248, 0.8)'  // Indigo
];

document.addEventListener('DOMContentLoaded', () => {
    if (typeof Chart === 'undefined') {
        alert("CRITICAL: Chart.js library not loaded!");
    } else {
        console.log("Chart.js is loaded version:", Chart.version);
    }
    fetchHistory(); // Load history list
    fetchData();    // Load current analysis

    // Search Listener
    const searchInput = document.getElementById('studentSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            handleSearch(e.target.value);
        });
    }
});

async function fetchHistory() {
    try {
        const response = await fetch('/api/history');
        const snapshots = await response.json();
        const select = document.getElementById('historySelect');
        select.innerHTML = '<option value="" disabled selected>Select a Snapshot</option>';

        snapshots.forEach(s => {
            // Timestamp is in UTC/Server time string like "2024-10-24 22:30:15"
            const dateStr = s.timestamp;
            const option = document.createElement('option');
            option.value = s.id;
            // E.g., "2024-10-24 22:30:15 - Uploaded Data"
            option.text = `${dateStr} - ${s.description || 'Snapshot'}`;
            select.appendChild(option);
        });

        // If we just uploaded, maybe select the top one? 
        // For now, let user pick explicitly or see "current"
    } catch (e) {
        console.error("Failed to load history", e);
    }
}

async function loadSnapshot(id) {
    if (!id) return;
    try {
        const response = await fetch(`/api/history/${id}`);
        const result = await response.json();
        if (result.data) {
            renderAll(result.data);
            alert(`Loaded: ${result.message}`);
        }
    } catch (e) {
        console.error("Error loading snapshot", e);
        alert("Failed to load snapshot");
    }
}

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();

        if (data.empty) {
            // No data loaded state
            document.querySelector('.loading').innerText = "No Data loaded. Upload CSV to start.";
            clearCharts();
            return;
        }

        if (data.error) {
            console.error(data.error);
            return;
        }

        renderAll(data);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

function renderAll(data) {
    renderStats(data.clusters);
    renderChart(data.students, data.clusters);
    renderRawChart(data.students);
    if (data.class_stats && typeof renderBellCurve === 'function') {
        renderBellCurve(data.students, data.class_stats);
    }
}

function clearCharts() {
    if (chartInstance) chartInstance.destroy();
    if (bellChartInstance) bellChartInstance.destroy();
    if (rawChartInstance) rawChartInstance.destroy();
    document.getElementById('cluster-stats').innerHTML =
        `<div style="color:white; opacity:0.7; font-style:italic;">Upload data to see analysis.</div>`;
}

// Modal Globals
let globalStudents = null;
let globalStats = null;

function renderAll(data) {
    globalStudents = data.students;
    globalStats = data.class_stats;

    renderStats(data.clusters);
    renderChart(data.students, data.clusters);
    renderRawChart(data.students);
    // Bell Curve Logic Removed
}

// ... clearCharts ...

let bellChartInstance = null;

/* BELL CHART FEATURE REMOVED
// Called by Button
function openBellChart() {
    // ... code removed ...
}

function closeBellChart() {
    document.getElementById('bellChartModal').style.display = 'none';
}

function renderBellCurve(students, stats) {
    // ... code removed ...
}
*/

let rawChartInstance = null;

function renderRawChart(students) {
    const ctx = document.getElementById('rawChart').getContext('2d');

    if (rawChartInstance) {
        rawChartInstance.destroy();
    }

    rawChartInstance = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Student',
                data: students.map(s => ({ x: s.x, y: s.y })),
                backgroundColor: 'rgba(255, 255, 255, 0.7)', // Plain White/Cyan
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            scales: {
                x: { display: false }, // Hide axes for cleaner look
                y: { display: false }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Student ID: ${students[ctx.dataIndex].student_id}`
                    }
                }
            },
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function renderStats(clusters) {
    const container = document.getElementById('cluster-stats');
    container.innerHTML = '';

    Object.keys(clusters).forEach((key, index) => {
        const cluster = clusters[key];
        const card = document.createElement('div');
        card.className = 'cluster-card';
        card.style.borderLeftColor = clusterColors[index % clusterColors.length];

        card.innerHTML = `
            <h4>
                ${cluster.name}
                <span class="count-badge">${cluster.count} Students</span>
            </h4>
            <p>${cluster.description}</p>
        `;
        container.appendChild(card);
    });
}

function renderChart(students, clusters) {
    const ctx = document.getElementById('clusterChart').getContext('2d');

    // Group students by cluster for Chart.js
    const datasets = [];

    Object.keys(clusters).forEach((clusterId, index) => {
        const clusterStudents = students.filter(s => s.cluster == clusterId);
        datasets.push({
            label: clusters[clusterId].name,
            data: clusterStudents.map(s => ({
                x: s.x,
                y: s.y,
                studentInfo: s // Store full object for tooltip/click
            })),
            backgroundColor: clusterColors[index % clusterColors.length],
            pointRadius: 6,
            pointHoverRadius: 8
        });
    });

    if (chartInstance) {
        chartInstance.destroy();
    }

    chartInstance = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: false // Hide axis for cleaner look
                },
                y: {
                    display: false
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#94a3b8' }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const student = context.raw.studentInfo;
                            return `ID: ${student.student_id} (Score: ${Math.round(student.exam_score)})`;
                        }
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const datasetIndex = elements[0].datasetIndex;
                    const index = elements[0].index;
                    const student = datasets[datasetIndex].data[index].studentInfo;
                    showStudentDetails(student);
                }
            }
        }
    });
}

function showStudentDetails(student) {
    const container = document.getElementById('student-info');

    // Helper to create progress bar
    const createMetric = (label, value, max = 10) => {
        const percent = (value / max) * 100;
        return `
            <div class="info-item">
                <span class="info-label">${label}</span>
                <div style="display:flex; align-items:center;">
                    <span class="info-value">${Math.round(value * 10) / 10}</span>
                    <div class="score-bar"><div class="score-fill" style="width:${percent}%"></div></div>
                </div>
            </div>
        `;
    };

    container.innerHTML = `
        <div class="info-item" style="background: rgba(255,255,255,0.1);">
            <span class="info-label">Student ID (Refreshed)</span>
            <span class="info-value" style="color:var(--accent);">${student.student_id}</span>
        </div>
        ${createMetric('Exam Score', student.exam_score, 100)}
        ${createMetric('Participation', student.participation_frequency)}
        ${createMetric('Logic Score', student.logical_understanding)}
        ${createMetric('Curiosity', student.curiosity_level)}
        ${createMetric('Self Learning', student.self_learning)}
        ${createMetric('Question Freq.', student.question_frequency)}
        ${createMetric('Doubts Depth', student.depth_of_doubts)}
        ${createMetric('Assignments', student.assignment_completion, 100)}
    `;

    // Show the panel
    document.getElementById('detail-panel').style.opacity = '1';
}

function handleSearch(query) {
    if (!chartInstance) return;

    query = query.toLowerCase();
    const datasets = chartInstance.data.datasets;
    let foundStudent = null;
    let foundIndex = -1;
    let foundDatasetIndex = -1;

    // Reset all point radii
    datasets.forEach((dataset, dIndex) => {
        const originalRadius = 6;
        // We need to update the pointRadius array if we want individual control, 
        // or just rely on finding the student and reacting.
        // Chart.js `pointRadius` can be an array.

        const newRadii = dataset.data.map(p => 6);
        const newColors = dataset.data.map(p => dataset.backgroundColor);

        dataset.pointRadius = newRadii;
        dataset.pointBackgroundColor = newColors;

        // Search logic
        dataset.data.forEach((point, pIndex) => {
            const s = point.studentInfo;
            if (query && s.student_id.toLowerCase().includes(query)) {
                // Found a match!
                // Highlight this point
                newRadii[pIndex] = 12; // Make it big
                foundStudent = s;
                foundIndex = pIndex;
                foundDatasetIndex = dIndex;
            }
        });
    });

    chartInstance.update();

    if (foundStudent) {
        showStudentDetails(foundStudent);
    }
}

// Upload Modal Logic
function openUploadModal() {
    document.getElementById('uploadModal').style.display = 'flex';
    document.getElementById('uploadStatus').innerText = '';
}

function closeUploadModal() {
    document.getElementById('uploadModal').style.display = 'none';
}

async function submitUpload() {
    const batchName = document.getElementById('uploadBatchName').value.trim();
    const label = document.getElementById('uploadLabel').value.trim();
    const fileInput = document.getElementById('fileInputModal');
    const file = fileInput.files[0];

    if (!batchName) {
        alert("Please enter a Batch Name (e.g., 'CS-A').");
        return;
    }
    if (!file) {
        alert("Please select a CSV file.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('batch_name', batchName);
    if (label) formData.append('description', label);

    // Show loading state
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.innerText = "Uploading & Analyzing...";

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            statusDiv.innerText = "Success! Snapshot Saved.";
            setTimeout(() => {
                closeUploadModal();
                // Reload data
                const snapshotId = result.snapshot_id;
                fetchData();
                fetchHistory(); // Update dropdown
            }, 1000);

        } else {
            statusDiv.innerText = 'Error: ' + (result.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Upload failed:', error);
        statusDiv.innerText = 'Upload failed. Check console.';
    }
}

// Trend Modal Logic
let trendChartInstance = null;

async function openTrendModal() {
    document.getElementById('trendModal').style.display = 'flex';

    // Populate Batch Dropdown
    const select = document.getElementById('trendBatchSelect');
    select.innerHTML = '<option value="">Loading Batches...</option>';

    // Fetch unique batches from history
    try {
        const response = await fetch('/api/history');
        const snapshots = await response.json();

        // Extract unique batch names
        const batches = [...new Set(snapshots.map(s => s.batch_name).filter(b => b))];

        select.innerHTML = '<option value="">Select Batch...</option>';
        batches.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b;
            opt.text = b;
            select.appendChild(opt);
        });

        // Auto-select the first one if available
        if (batches.length > 0) {
            select.value = batches[0];
            loadTrendData(batches[0]);
        }

    } catch (e) {
        console.error("Failed to load batches", e);
        select.innerHTML = '<option value="">Error Loading</option>';
    }
}

function closeTrendModal() {
    document.getElementById('trendModal').style.display = 'none';
}

async function loadTrendData(batchName) {
    if (!batchName) {
        // Clear if empty
        if (trendChartInstance) trendChartInstance.destroy();
        document.getElementById('trendSummary').innerHTML = '';
        document.getElementById('snapshotList').innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`/api/trend?batch_name=${encodeURIComponent(batchName)}`);
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        renderTrendChart(data);

    } catch (e) {
        console.error("Trend load failed", e);
        alert("Failed to load trend data.");
    }
}

function renderTrendChart(data) {
    const ctx = document.getElementById('trendChartCanvas').getContext('2d');
    const history = data.history;
    const forecast = data.forecast;
    const summaryDiv = document.getElementById('trendSummary');

    // Labels (Dates)
    const labels = history.map(h => h.label || h.date.split(' ')[0]);
    labels.push("Forecast (Next)"); // Add forecast label

    // Exam Data
    const examData = history.map(h => h.exam_avg);
    // Engagement Data
    const engageData = history.map(h => h.engage_avg);

    // Prepare Forecast Points (Last Real Point -> Forecast Point)
    // We pad with nulls for history
    const forecastExam = Array(history.length - 1).fill(null);
    forecastExam.push(examData[examData.length - 1]); // Start from last actual
    forecastExam.push(forecast.exam_predicted);

    const forecastEngage = Array(history.length - 1).fill(null);
    forecastEngage.push(engageData[engageData.length - 1]);
    forecastEngage.push(forecast.engage_predicted);

    // Update Text Summary
    summaryDiv.innerHTML = `
        <div style="margin-bottom:10px;">
            <strong>Forecast for ${forecast.date}:</strong><br>
            Exam Score: <span style="color:#34d399">${forecast.exam_predicted.toFixed(1)}%</span> (±${forecast.exam_mae.toFixed(1)}%) <br>
            Engagement: <span style="color:#60a5fa">${forecast.engage_predicted.toFixed(1)}%</span> (±${forecast.engage_mae.toFixed(1)}%)
        </div>
    `;

    // Populate Snapshot List
    const listDiv = document.getElementById('snapshotList');
    listDiv.innerHTML = history.map(h => `
        <div style="background:rgba(255,255,255,0.05); padding:4px 8px; border-radius:4px; border:1px solid rgba(255,255,255,0.1);">
            <strong style="color:#fff;">${h.label || 'Snapshot'}</strong>
            <span style="opacity:0.5; font-size:0.7rem; margin-left:5px;">${h.date.split(' ')[0]}</span>
        </div>
    `).join('');

    if (trendChartInstance) {
        trendChartInstance.destroy();
    }

    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Exam Score (History)',
                    data: [...examData, null], // Pad for forecast space
                    borderColor: '#34d399', // Green
                    backgroundColor: '#34d399',
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Exam Forecast',
                    data: forecastExam,
                    borderColor: '#34d399',
                    borderDash: [5, 5], // Dotted
                    backgroundColor: 'rgba(52, 211, 153, 0.2)',
                    pointStyle: 'triangle',
                    pointRadius: 6,
                    tension: 0
                },
                {
                    label: 'Engagement Score (History)',
                    data: [...engageData, null], // Pad
                    borderColor: '#60a5fa', // Blue
                    backgroundColor: '#60a5fa',
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Engagement Forecast',
                    data: forecastEngage,
                    borderColor: '#60a5fa',
                    borderDash: [5, 5],
                    backgroundColor: 'rgba(96, 165, 250, 0.2)',
                    pointStyle: 'triangle',
                    pointRadius: 6,
                    tension: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: 'Score (%)', color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            },
            plugins: {
                legend: { labels: { color: '#ffffff' } },
                tooltip: { mode: 'index', intersect: false }
            }
        }
    });
}

