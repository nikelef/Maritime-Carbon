"use strict";
(() => {
  const element = document.getElementById("chart-data");
  const canvas = document.getElementById("annual-chart");
  if (!element || !canvas) return;
  const data = JSON.parse(element.textContent);
  const context = canvas.getContext("2d");
  const tooltip = document.getElementById("chart-tooltip");
  const euro = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  let positions = [];
  function draw() {
    const width = canvas.parentElement.clientWidth;
    const height = canvas.parentElement.clientHeight;
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    const left = 65, right = width - 19, top = 20, bottom = height - 36;
    const maximum = Math.max(1, ...data.annual.map(r => r.total_cost), ...data.baseline.map(r => r.total_cost)) * 1.14;
    const y = value => bottom - value / maximum * (bottom - top);
    const x = index => left + (right - left) * (data.annual.length === 1 ? .5 : index / (data.annual.length - 1));
    context.font = "10px Segoe UI, Arial, sans-serif";
    context.textAlign = "right"; context.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const value = maximum * i / 4;
      const point = y(value);
      context.strokeStyle = "#e7eeea"; context.lineWidth = 1; context.beginPath(); context.moveTo(left, point); context.lineTo(right, point); context.stroke();
      context.fillStyle = "#73877d";
      const label = value >= 1e6 ? `€${(value / 1e6).toFixed(1)}m` : value >= 1000 ? `€${(value / 1000).toFixed(0)}k` : `€${value.toFixed(0)}`;
      context.fillText(label, left - 10, point);
    }
    context.textAlign = "center";
    const stride = Math.max(1, Math.ceil(data.annual.length / Math.max(2, (width - 60) / 55)));
    data.annual.forEach((row, index) => { if (index % stride === 0 || index === data.annual.length - 1) context.fillText(String(row.year), x(index), bottom + 20); });
    // Under-curve wash gives a visible cost trajectory without hiding exact table values.
    context.beginPath(); context.moveTo(x(0), bottom);
    data.annual.forEach((row, index) => context.lineTo(x(index), y(row.total_cost)));
    context.lineTo(x(data.annual.length - 1), bottom); context.closePath();
    const gradient = context.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, "#16887520"); gradient.addColorStop(1, "#16887500"); context.fillStyle = gradient; context.fill();
    function line(rows, color, dashed) {
      context.strokeStyle = color; context.lineWidth = dashed ? 2 : 2.5; context.setLineDash(dashed ? [5, 5] : []);
      context.beginPath(); rows.forEach((row, index) => { if (index === 0) context.moveTo(x(index), y(row.total_cost)); else context.lineTo(x(index), y(row.total_cost)); }); context.stroke(); context.setLineDash([]);
      if (rows.length <= 10) rows.forEach((row, index) => { context.fillStyle = "white"; context.beginPath(); context.arc(x(index), y(row.total_cost), 3.5, 0, Math.PI * 2); context.fill(); context.stroke(); });
    }
    line(data.baseline, "#a3b6ab", true); line(data.annual, "#087f72", false);
    positions = data.annual.map((row, index) => ({ x: x(index), y: y(row.total_cost), row, baseline: data.baseline[index] }));
  }
  canvas.addEventListener("mousemove", event => {
    const rect = canvas.getBoundingClientRect();
    const pointer = event.clientX - rect.left;
    const nearest = positions.reduce((a, b) => Math.abs(a.x - pointer) < Math.abs(b.x - pointer) ? a : b, positions[0]);
    if (!nearest) return;
    tooltip.textContent = `${nearest.row.year}\nSelected: ${euro.format(nearest.row.total_cost)}\nReference: ${euro.format(nearest.baseline.total_cost)}`;
    tooltip.hidden = false; tooltip.style.left = `${Math.max(0, Math.min(nearest.x + 8, rect.width - 205))}px`; tooltip.style.top = `${Math.max(0, nearest.y - 85)}px`;
  });
  canvas.addEventListener("mouseleave", () => { tooltip.hidden = true; });
  new ResizeObserver(draw).observe(canvas.parentElement);
  window.addEventListener("beforeprint", draw);
  window.addEventListener("afterprint", draw);
  draw();
})();
