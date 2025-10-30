import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import { useEffect, useState, component } from "haunted";

import { Map, TileLayer, Marker, Icon } from "leaflet";
import { LocateControl } from "leaflet.locatecontrol";

import markerIconPng from "leaflet/dist/images/marker-icon.png";

const DEFAULT_LOCATION = {
  lat: 30.24171,
  lng: -91.991044,
};

// https://leafletjs.com/reference.html#latlng
function CivMap({ latlng }) {
  const [mapInstance, setMapInstance] = useState(null);
  const [homeLatlng, setHomeLatlng] = useState(
    latlng ? latlng : DEFAULT_LOCATION,
  );
  const [currentLatlng, setCurrentLatlng] = useState(null);
  const [marker, setMarker] = useState(null);

  useEffect(() => {
    if (!mapInstance) return;

    mapInstance.addEventListener("locationerror", handleLocationError);
    mapInstance.addEventListener("locationfound", handleLocationFound);

    return () => {
      mapInstance.removeEventListener("locationerror", handleLocationError);
      mapInstance.removeEventListener("locationfound", handleLocationFound);
    };
  }, [mapInstance]);

  useEffect(() => {
    console.log("what is", currentLatlng, mapInstance);
    if (!currentLatlng || !mapInstance) return;

    moveMarker(currentLatlng);
    // mapInstance.flyTo(currentLatlng, 4);
  }, [currentLatlng, mapInstance]);

  const handleLocationError = (event) => {
    console.error("Location error occurred:", event.message);
    setCurrentLatlng(homeLatlng);
  };

  const handleLocationFound = (event) => {
    console.info("Found location: ", event.latlng);
    setCurrentLatlng(event.latlng);
    setHomeLatlng(event.latlng);
  };

  const setupMap = (el) => {
    if (!el || mapInstance) return;

    let newMapInstance = new Map(el); // .setView([51.505, -0.09], 13);

    let urlTemplate = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    newMapInstance.addLayer(new TileLayer(urlTemplate, { minZoom: 3 }));

    if (latlng) {
      setCurrentLatlng(latlng);
    } else {
      newMapInstance.locate();
    }

    let _lc = new LocateControl({
      keepCurrentZoomLevel: true,
      drawMarker: false,
      drawCircle: false,
    }).addTo(newMapInstance);

    setMapInstance(newMapInstance);
    // Fix issue with stylesheet not loading
    // https://stackoverflow.com/questions/21405189/leaflet-map-shows-up-grey
    window.dispatchEvent(new Event("resize"));
  };

  const moveMarker = (markerLatlng) => {
    if (!mapInstance) return;

    if (!marker) {
      let newMarker = new Marker(markerLatlng, {
        icon: new Icon({
          iconUrl: markerIconPng,
        }),
      });
      newMarker.addTo(mapInstance);
      setMarker(newMarker);
    } else {
      marker.setLatLng(markerLatlng);
    }

    mapInstance.setView(currentLatlng, 12);
  };

  return html`
    <link
      rel="stylesheet"
      href="https://cdn.skypack.dev/leaflet/dist/leaflet.css"
    />
    <link
      rel="stylesheet"
      href="https://cdn.skypack.dev/leaflet.locatecontrol/dist/L.Control.Locate.min.css"
    />
    <style>
      .map-container {
        height: 400px;
      }

      .map-container .map {
        height: 100%;
      }
    </style>
    <div class="map-container">
      <div class="map" ${ref(setupMap)}></div>
    </div>
  `;
}
customElements.define(
  "civ-map",
  component(CivMap, { observedAttributes: ["latlng"] }),
);
