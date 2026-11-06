fetch("/api/metrics").then(r => r.json()).then(m => {
  const C = ["#1f4e79", "#2f80c9", "#e0a100", "#1a7f4b", "#c0392b", "#8e6bbf"];
  const mk = (id, type, labels, sets, opts = {}) =>
    new Chart(document.getElementById(id), { type, data: { labels, datasets: sets }, options: { responsive: true, ...opts } });
  mk("trend", "line", m.trend.map(x => x.month), [
    { label: "Created", data: m.trend.map(x => x.created), borderColor: C[0], tension: .3 },
    { label: "Completed", data: m.trend.map(x => x.completed), borderColor: C[3], tension: .3 }]);
  mk("status", "doughnut", m.by_status.map(x => x.status), [{ data: m.by_status.map(x => x.count), backgroundColor: C }]);
  mk("cat", "bar", m.by_category.map(x => x.category), [
    { label: "Open", data: m.by_category.map(x => x.open_count), backgroundColor: C[2] },
    { label: "Completed", data: m.by_category.map(x => x.completed), backgroundColor: C[3] }],
    { scales: { x: { stacked: true }, y: { stacked: true } } });
  mk("load", "bar", m.workload.map(x => x.assignee), [
    { label: "Done", data: m.workload.map(x => x.done), backgroundColor: C[3] },
    { label: "Pending", data: m.workload.map(x => x.pending), backgroundColor: C[4] }],
    { indexAxis: "y", scales: { x: { stacked: true }, y: { stacked: true } } });
});
