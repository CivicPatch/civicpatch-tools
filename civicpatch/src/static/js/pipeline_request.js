const POLL_DELAY_MS = 30000; // 30 seconds

async function fetchContext(jurisdiction_id_url) {
  const resp = await fetch(`/pipelines/${jurisdiction_id_url}/context`);
  if (resp.ok) {
    const ctx = await resp.json();
    // Format JSON as HTML
    document.getElementById("pipeline-content").innerHTML = `
      <ul>
        <li><strong>Request ID:</strong> ${ctx.request_id}</li>
        <li><strong>Name:</strong> ${ctx.name}</li>
        <li><strong>Jurisdiction ID:</strong> ${ctx.jurisdiction_id}</li>
        <li><strong>URL:</strong> <a href="${ctx.url}" target="_blank">${ctx.url}</a></li>
        <li><strong>Progress:</strong>
          <ul>
            <li>Required Data: ${ctx.progress.required_data}</li>
            <li>Current Data: ${ctx.progress.current_data}</li>
            <li>Has Target Role: ${ctx.progress.has_target_role}</li>
            <li>Has Target Divisions: ${ctx.progress.has_target_divisions}</li>
          </ul>
        </li>
        <li><strong>Names:</strong>
          <ul>
            ${Object.entries(ctx.names).map(([canonical, names]) =>
              `<li>${canonical}: ${names.join(', ')}</li>`
            ).join('')}
          </ul>
        </li>
        <li><strong>Links:</strong>
          <ul>
            ${ctx.links.map(link =>
              `<li><a href="${link.url}" target="_blank">${link.url}</a> (Status: ${link.status})</li>`
            ).join('')}
          </ul>
        </li>
        <li><strong>Steps:</strong>
          <ul>
            ${Object.entries(ctx.steps).map(([stepName, stepData]) => {
              return `<li>
                <strong>${stepName}</strong>
                <pre>${JSON.stringify(stepData, null, 2)}</pre>
              </li>`;
            }).join('')}
          </ul>
        </li>
      </ul>
    `;
  }
}

function startContextPolling(jurisdiction_id_url, intervalMs = POLL_DELAY_MS) {
  fetchContext(jurisdiction_id_url);
  setInterval(() => fetchContext(jurisdiction_id_url), intervalMs);
}