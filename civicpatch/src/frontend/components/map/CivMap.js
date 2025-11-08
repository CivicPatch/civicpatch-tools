import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import { useEffect, useState, component } from "haunted";

import { Map, TileLayer, Marker, Icon, Control } from "leaflet";
import { LocateControl } from "leaflet.locatecontrol";
import { Geocoder, geocoders } from "leaflet-control-geocoder";

import leafletStyles from "leaflet/dist/leaflet.css";
import locateStyles from "leaflet.locatecontrol/dist/L.Control.Locate.min.css";
import geocoderStyles from "leaflet-control-geocoder/dist/Control.Geocoder.css";

import markerIconPng from "leaflet/dist/images/marker-icon.png";

const DEFAULT_LOCATION = {
  lat: 30.24171,
  lng: -91.991044,
};

// https://leafletjs.com/reference.html#latlng
function CivMap({ latlng }) {
  const [mapInstance, setMapInstance] = useState(null);
  const [homeLatlng, setHomeLatlng] = useState(latlng || DEFAULT_LOCATION);
  const [currentLatlng, setCurrentLatlng] = useState(null);
  const [marker, setMarker] = useState(null);
  const [controls, setControls] = useState({ gc: null });

  useEffect(() => {
    if (!mapInstance) return;

    mapInstance.on("locationerror", handleLocationError);
    mapInstance.on("locationfound", handleLocationFound);
    mapInstance.on("locationactivate", handleLocationFound);
    mapInstance.on("click", handleClick);

    return () => {
      mapInstance.off("locationerror", handleLocationError);
      mapInstance.off("locationfound", handleLocationFound);
      mapInstance.off("locationactivate", handleLocationFound);
      mapInstance.off("click", handleClick);

      if (controls.gc) {
        controls.gc.off("markgeocode", handleAddressResult);
      }
      mapInstance.remove();
    };
  }, [mapInstance]);

  useEffect(() => {
    if (!currentLatlng || !mapInstance) return;

    if (controls.lc) {
      controls.lc.stop();
    }
    moveMarker(currentLatlng);
  }, [currentLatlng, mapInstance]);

  const handleLocationError = (event) => {
    console.error("Location error occurred:", event.message);
    setCurrentLatlng(homeLatlng);
  };

  const handleLocationFound = (event) => {
    setCurrentLatlng(event.latlng);
    setHomeLatlng(event.latlng);
  };

  const handleAddressResult = (event) => {
    if (event?.geocode?.center) {
      if (event.geocode.center.lat && event.geocode.center.lng) {
        setCurrentLatlng(event.geocode.center);
      }
    }
  };

  const setupMap = (el) => {
    if (!el || mapInstance) return;

    let newMapInstance = new Map(el, { zoomControl: false }); // .setView([51.505, -0.09], 13);

    let urlTemplate = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    newMapInstance.addLayer(new TileLayer(urlTemplate, { minZoom: 3 }));

    if (latlng) {
      setCurrentLatlng(latlng);
    } else {
      newMapInstance.locate();
    }

    let _gc = new Geocoder({
      geocoder: new geocoders.Nominatim({
        geocodingQueryParams: {
          countrycodes: "US",
        },
      }),
      defaultMarkGeocode: false,
      position: "topleft",
    })
      .on("markgeocode", handleAddressResult)
      .addTo(newMapInstance);

    let _lc = new LocateControl({
      keepCurrentZoomLevel: true,
      drawMarker: false,
      drawCircle: false,
      position: "bottomright",
      setView: false,
      clickBehavior: {
        inView: "stop",
        outOfView: "stop",
        inViewNotFollowing: "stop",
      },
    }).addTo(newMapInstance);

    let _zoom = new Control.Zoom({
      position: "bottomright",
    }).addTo(newMapInstance);

    setMapInstance(newMapInstance);
    setControls({ gc: _gc, lc: _lc });
  };

  const handleClick = (e) => {
    setCurrentLatlng(e.latlng);
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
    <style>
      ${leafletStyles} ${locateStyles} ${geocoderStyles} .map-container {
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
