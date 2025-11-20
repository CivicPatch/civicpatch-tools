import { component, useEffect, useState, useCallback } from 'haunted';
import { html } from 'lit-html';

const DEFAULT_CENTER = "30.24171,-91.991044";

function JurisdictionDashboard({ jurisdiction_ocdid, jurisdiction_ocdid_slug }) {
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
            fetchPeopleData(jurisdiction_ocdid),
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
        const response = await fetch(
          `/api/api_proxy/jurisdictions/${ocdid}?with_geom=true`);
        const result = await response.json();
        return {
          data: result.data,
          geo_center: result.geo_center
        };
    }

    const fetchPeopleData = async (ocdid) => {
      const encodedOcdid = encodeURIComponent(ocdid);
      const response = await fetch(`/api/api_proxy/people?jurisdiction_ocdid=${encodedOcdid}`);
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
        "name": data.data.name,
        "jurisdiction_id": data.data.id,
        "url": data.data.url
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

    const scrapeStatus = data?.data?.updated_at ?
        `Scraped` :
        `Unscraped`;

    console.log('Rendering with pipelineStatus: wooot', pipelineStatus);

    return html`
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="grid">
              <div>
                  <civ-map
                    canmove="false"
                    .latlng=${data && data.geo_center ? { lat: data.geo_center.lat, lng: data.geo_center.lng } : null}
                  ></civ-map>
              </div>

              <div> 
              ${
                data ? html`
                      <header>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                          <h2 style="margin-bottom: 0">${data.data.name}</h2>
                          <span style="font-size: 1.75rem">Status: ${scrapeStatus}</span>
                        </div>
                      </header>
                      <hr />

                      <p>
                        <strong>Jurisdiction ID:</strong> ${data.data.id} <br/>
                        <strong>Website:</strong> ${data.data.url} <br/>
                        <strong>Geoid:</strong> ${data.data.geoid} <br/>
                        <small>Population: ${data.data.population.toLocaleString()}</small> <br />
                      </p>

                      <h3>Scrape History</h3>
                      <hr/>
                      <civ-scrape-history
                        .jurisdiction_ocdid_slug=${jurisdiction_ocdid_slug}
                      ></civ-scrape-history>


                      <p>Last Scraped: ${data.data.updated_at ? new Date(data.data.updated_at).toLocaleString() : 'N/A'}</p>

                      <button 
                        @click=${handleScrapeClick}
                        ?disabled=${!canStartScrape()}
                        class="primary">Scrape Data for Jurisdiction</button>
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
          
          <h2>Elected Representatives</h2>
          <civ-people-list
            .local=${people} 
          ></civ-people-list>
        </div>
    `
}

customElements.define(
    'civ-jurisdiction-dashboard', 
    component(JurisdictionDashboard, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid', 'jurisdiction_ocdid_slug'] })
);