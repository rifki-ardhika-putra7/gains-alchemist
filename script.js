const API_URL = "http://127.0.0.1:5000/api";
let myChart = null;
let anatomyChart = null;

async function init() {
  document.getElementById("inputDate").valueAsDate = new Date();
  await loadBodyWeight(); // Load BB dulu

  const res = await fetch(`${API_URL}/exercises`);
  const exercises = await res.json();

  const mainSel = document.getElementById("exerciseSelector");
  const inputSel = document.getElementById("inputExercise");
  mainSel.innerHTML = "";
  inputSel.innerHTML = "";

  if (exercises.length === 0) {
    mainSel.innerHTML = "<option>Upload Data Dulu!</option>";
    return;
  }

  exercises.forEach((ex) => {
    let opt1 = document.createElement("option");
    opt1.value = ex;
    opt1.text = ex;
    mainSel.appendChild(opt1);
    let opt2 = document.createElement("option");
    opt2.value = ex;
    opt2.text = ex;
    inputSel.appendChild(opt2);
  });

  updateData(exercises[0]);
  mainSel.addEventListener("change", (e) => updateData(e.target.value));
  loadAnatomy();
}

async function loadBodyWeight() {
  const res = await fetch(`${API_URL}/settings`);
  const data = await res.json();
  document.getElementById("bodyWeight").value = data.bodyweight;
}

async function saveWeight() {
  const bw = document.getElementById("bodyWeight").value;
  if (!bw) return;
  await fetch(`${API_URL}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bodyweight: bw }),
  });
  alert("✅ Berat Badan Disimpan! Rank diupdate.");
  updateData(document.getElementById("exerciseSelector").value);
}

async function uploadData() {
  const input = document.getElementById("csvFile");
  const status = document.getElementById("uploadStatus");
  if (input.files.length === 0) return;

  const formData = new FormData();
  formData.append("file", input.files[0]);
  status.innerText = "⏳ Processing...";

  try {
    const res = await fetch(`${API_URL}/upload`, {
      method: "POST",
      body: formData,
    });
    const d = await res.json();
    if (d.error) {
      alert(d.error);
      status.innerText = "Error";
    } else {
      alert("✅ Data Sukses!");
      status.innerText = "Ready";
      init();
    }
  } catch (e) {
    console.error(e);
    alert("Error Server");
  }
}

async function updateData(exName) {
  if (!exName) return;
  const res = await fetch(`${API_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ exercise: exName }),
  });
  const data = await res.json();
  if (data.error) return;

  document.getElementById("currentPr").innerText = `${data.current_pr} kg`;
  document.getElementById("targetPr").innerText = `${data.next_week_pr} kg`;
  document.getElementById("userRank").innerText = data.rank;
  document.getElementById("recHeavy").innerText = data.recs.heavy;
  document.getElementById("recHyper").innerText = data.recs.hyper;
  document.getElementById("inputExercise").value = exName;

  renderChart(data);
}

function renderChart(data) {
  const ctx = document.getElementById("gainsChart").getContext("2d");
  const labels = [...data.history.dates, ...data.prediction.dates];
  const hData = data.history.values;
  const pData = new Array(hData.length - 1).fill(null);
  pData.push(hData[hData.length - 1]);
  pData.push(...data.prediction.values);

  if (myChart) myChart.destroy();
  myChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "History",
          data: hData,
          borderColor: "#00ffff",
          backgroundColor: "#00ffff",
          borderWidth: 3,
          tension: 0.3,
          pointRadius: 4,
        },
        {
          label: "AI Target",
          data: pData,
          borderColor: "#3fb950",
          borderWidth: 3,
          borderDash: [5, 5],
          tension: 0.3,
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "white" } } },
      scales: {
        y: { grid: { color: "#30363d" }, ticks: { color: "#8b949e" } },
        x: {
          grid: { color: "#30363d" },
          ticks: { color: "#8b949e", maxRotation: 45 },
        },
      },
    },
  });
}

async function loadAnatomy() {
  const res = await fetch(`${API_URL}/anatomy`);
  const data = await res.json();
  const ctx = document.getElementById("anatomyChart").getContext("2d");
  if (anatomyChart) anatomyChart.destroy();
  anatomyChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.labels,
      datasets: [
        {
          data: data.data,
          backgroundColor: [
            "#ff0055",
            "#00ffff",
            "#ffcc00",
            "#cc00ff",
            "#00ff99",
            "#0072ff",
            "#ffffff",
          ],
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { color: "white" } } },
      cutout: "65%",
    },
  });
}

async function submitData() {
  const payload = {
    date: document.getElementById("inputDate").value,
    exercise: document.getElementById("inputExercise").value,
    weight: document.getElementById("inputWeight").value,
    reps: document.getElementById("inputReps").value,
  };
  if (!payload.weight) return alert("Isi data dulu!");

  const res = await fetch(`${API_URL}/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const d = await res.json();
  if (d.message === "Success") {
    updateData(payload.exercise);
    loadAnatomy();
    document.getElementById("inputWeight").value = "";
    document.getElementById("inputReps").value = "";
    alert(`✅ Data Masuk! 1RM Baru: ${d.new_pr} kg`);
  }
}

init();
