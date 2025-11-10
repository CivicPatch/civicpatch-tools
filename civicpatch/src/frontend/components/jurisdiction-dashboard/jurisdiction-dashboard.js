import { component, useEffect, useState, useCallback } from 'haunted';
import { html } from 'lit-html';

function JurisdictionDashboard({ jurisdiction_ocdid_slug }) {
    const [data, setData] = useState(null);
    const [people, setPeople] = useState([]);

    const [pipelineStatus, setPipelineStatus] = useState({});
    const [pipelineStatusIsLoading, setPipelineStatusIsLoading] = useState(false);
    const [eventSource, setEventSource] = useState(null);
    const [isConnected, setIsConnected] = useState(false);

    const [error, setError] = useState(null);

    useEffect(() => {
        if (!jurisdiction_ocdid_slug) return;

        fetchData();
    }, [])

    const fetchData = async () => {
        const [pipelineStatusData, jurisdictionData, peopleData] = await Promise.all([
            fetchPipelineStatus(jurisdiction_ocdid_slug),
            fetchJurisdictionData(jurisdiction_ocdid_slug),
            fetchPeopleData(jurisdiction_ocdid_slug),
        ]);
        setData(jurisdictionData);
        setPeople(peopleData);
        setPipelineStatus(pipelineStatusData);
    } 

    const connectStream = useCallback(() => {
        console.log('Attempting to connect to SSE stream...');
        if (eventSource) {
            console.log('Stream is already active or being closed.');
            return;
        }

        const sseUrl = `/api/sse/pipelines/${jurisdiction_ocdid_slug}/status`;
        
        try {
            const newEventSource = new EventSource(sseUrl);
            setEventSource(newEventSource); // Store the instance in state
            setError(null);

            newEventSource.onopen = () => {
                console.log('✅ SSE connection established.');
                setIsConnected(true);
                setPipelineStatus(prev => ({ ...prev, status: 'CONNECTED', message: 'Waiting for updates...' }));
            };

            newEventSource.onmessage = (event) => {
                try {
                    const update = JSON.parse(event.data);
                    
                    // Update the state with the new status
                    setPipelineStatus(update.data); 

                    if (update.data.status === 'DONE') {
                        // Close if the pipeline is finished
                        newEventSource.close();
                        setEventSource(null); 
                        setIsConnected(false);
                        console.log('Stream closed: Pipeline finished.');
                    }
                } catch (e) {
                    console.error('Error parsing JSON from SSE stream:', e);
                    setError('Error processing update.');
                }
            };

            newEventSource.onerror = (e) => {
                console.error('❌ SSE Error occurred.', e);
                setIsConnected(false);
                setError('Connection lost or failed.');
                // Note: EventSource will attempt to reconnect automatically
            };

        } catch (e) {
            console.error('Failed to initialize EventSource:', e);
            setError('Failed to initialize connection.');
        }
    }, [eventSource, setEventSource]); // Dependency on eventSource to avoid multiple connections

    // --- 2. Disconnect Handler Function ---
    //const disconnectStream = useCallback(() => {
    //    if (eventSource) {
    //        eventSource.close();
    //        setEventSource(null);
    //        setIsConnected(false);
    //        setPipelineStatus({ status: 'DISCONNECTED', message: 'Monitoring manually stopped.' });
    //        console.log('Stream manually closed.');
    //    }
    //}, [eventSource]);


    useEffect(() => {
        return () => {
            if (eventSource) {
                eventSource.close();
                console.log('Stream closed on component unmount.');
            }
        };
    }, [eventSource]);

    const fetchJurisdictionData = async (ocdid) => {
        const response = await fetch(`/api/crudder/jurisdictions/${ocdid}`);
        const result = await response.json();
        return result.data;
    }

    const fetchPeopleData = async (ocdid) => {
        const response = await fetch(`/api/crudder/jurisdictions/${ocdid}/people`);
        const result = await response.json();
        return result.data;
    }

    const fetchPipelineStatus = async (ocdid_slug) => {
        const response = await fetch(`/api/pipelines/${ocdid_slug}/status`);
        if (!response.ok) {
          return null
        }

        const result = await response.json();
        return result.data;

    }

    const handleScrapeClick = async () => {
      setPipelineStatusIsLoading(true);
      const body = {
        "name": data.name,
        "jurisdiction_id": data.id,
        "url": data.url
      }
      const response = await fetch(
        `/api/pipelines/${jurisdiction_ocdid_slug}`, 
        { 
          headers: { 'Content-Type': 'application/json' },
          method: 'POST', 
          body: JSON.stringify(body) 
        }
      );
      connectStream()
    }

    const canStartScrape = () => {
      if (
        !pipelineStatus || 
        !pipelineStatusIsLoading) {
        return true;
      }

      return false;
    }

    console.log('Rendering with pipelineStatus:', pipelineStatus);

    return html`
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="grid">
              <div>
                  <civ-map
                    canmove="false"
                    latlngstring="30.24171,-91.991044"
                  ></civ-map>
              </div>

              <div> 
              ${
                data ? html`
                      <header>
                        <h2>${data.name}</h2>
                        <small>Population: ${data.population.toLocaleString()}</small>
                      </header>

                      <p>
                        <strong>Jurisdiction ID:</strong> ${data.id} <br/>
                        <strong>Website:</strong> ${data.url}
                      </p>

                      <a href="${data.url}" target="_blank" role="button" class="secondary">
                        Visit Official Website
                      </a>

                      <hr/>

                      <p>Last Updated: ${data.updated_at ? new Date(data.updated_at).toLocaleString() : 'N/A'}</p>
                      <button 
                        @click=${handleScrapeClick}
                        ?disabled=${!canStartScrape()}
                        class="primary">Start Scrape</button>
                ` : html`
                  <p>Loading jurisdiction data...</p>
                `
              }
              </div>
          </div>

          ${
            isConnected ? html`
              <div class="status-banner success">
                <strong>Pipeline Status:</strong> ${pipelineStatus?.status} <br/>
                <small>${pipelineStatus.message || ''}</small>
              </div>
            ` : null
          }
           
          <civ-people-list
            .local=${people} 
          ></civ-people-list>
        </div>
    `
}

customElements.define(
    'civ-jurisdiction-dashboard', 
    component(JurisdictionDashboard, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid_slug'] })
);