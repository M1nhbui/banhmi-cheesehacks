async function main() {
  const res = await fetch("/map-data");
  const data = await res.json();

  if (data.error) {
    document.getElementById("subtitle").textContent = data.error;
    return;
  }

  const meta = data.meta;
  document.getElementById("subtitle").textContent =
    `${meta.city} • grid ${meta.grid.rows}x${meta.grid.cols} • generated ${meta.generated_at}`;

  // Create map
  const map = L.map("map").setView([43.0731, -89.4012], 12);

  // Basemap tiles (needs internet)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  // Fit bounds to the demo bbox
  const b = meta.bounds;
  const southWest = L.latLng(b.min_lat, b.min_lon);
  const northEast = L.latLng(b.max_lat, b.max_lon);
  map.fitBounds(L.latLngBounds(southWest, northEast));

  // Color scale: blue -> red
  function colorForScore(score) {
    // score in [0,1]
    const t = Math.max(0, Math.min(1, score));
    // start (blue-ish) and end (red-ish)
    const start = { r: 50, g: 90, b: 200 };
    const end = { r: 220, g: 60, b: 60 };
    const r = Math.round(start.r + (end.r - start.r) * t);
    const g = Math.round(start.g + (end.g - start.g) * t);
    const b = Math.round(start.b + (end.b - start.b) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // Draw heatmap cells as polygons
  // This can be a lot of polygons (3600). It’s okay for a demo.
  data.cells.forEach((cell) => {
    const coords = cell.polygon.coordinates[0].map(([lon, lat]) => [lat, lon]);

    const poly = L.polygon(coords, {
      stroke: false,
      fillOpacity: 0.35,
      fillColor: colorForScore(cell.score)
    });

    poly.bindTooltip(
      `Cell ${cell.cell_id}<br>score: ${cell.score}<br>places used: ${cell.place_count_used}`,
      { sticky: true }
    );

    poly.addTo(map);
  });

  // Add top place markers
  data.top_places.forEach((p) => {
    const marker = L.circleMarker([p.lat, p.lon], {
      radius: 6,
      weight: 1,
      fillOpacity: 0.9
    });

    const popupHtml = `
      <div style="min-width:220px">
        <b>${p.name}</b><br/>
        <div>score: <b>${p.score}</b></div>
        <div>categories: ${p.categories.join(", ")}</div>
        <div>rating: ${p.rating} (${p.review_count} reviews)</div>
        <hr/>
        <div><b>breakdown</b></div>
        <div>pref: ${p.score_breakdown.pref}</div>
        <div>popularity: ${p.score_breakdown.popularity}</div>
        <div>event: ${p.score_breakdown.event}</div>
        <div>weather: ${p.score_breakdown.weather}</div>
      </div>
    `;

    marker.bindPopup(popupHtml);
    marker.addTo(map);
  });
}

main().catch((err) => {
  console.error(err);
  document.getElementById("subtitle").textContent = "Error loading map data. Check console.";
});