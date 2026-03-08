import { html } from 'lit-html';
import { useState, useEffect, component } from 'haunted';
// import '../../components/jobs-dashboard/jobs-table.js';
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;

function JobsPage() {
  const [jobs, setJobs] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/jobs/people/pull_requests`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => setJobs(data.data));
  }, []);

  if (!jobs) return html`<div>Loading...</div>`;

  return html`
    <main>
      <section>
        <h2>Current Jobs</h2>
        <jobs-table .jobs=${jobs}></jobs-table>
      </section>
    </main>
  `;
}

customElements.define('jobs-page', component(JobsPage, { useShadowDOM: false }));
export default JobsPage;