import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import { useEffect, useState, component } from "haunted";

import {
  Map,
  TileLayer,
  Marker,
  Icon,
  Control,
  geoJSON,
  FeatureGroup,
} from "leaflet";
import { LocateControl } from "leaflet.locatecontrol";
import { Geocoder, geocoders } from "leaflet-control-geocoder";

import leafletStyles from "leaflet/dist/leaflet.css";
import locateStyles from "leaflet.locatecontrol/dist/L.Control.Locate.min.css";
import geocoderStyles from "leaflet-control-geocoder/dist/Control.Geocoder.css";

import markerIconPng from "leaflet/dist/images/marker-icon.png";

const DEFAULT_LOCATION = { lat: 47.60813, lng: -122.335167 }; // Seattle, WA

// https://leafletjs.com/reference.html#latlng
function CivMap({ latlng, canmove = true, geojson = null }) {
  const canMove = canmove === "true" || canmove === true;

  const [mapInstance, setMapInstance] = useState(null);
  const [homeLatlng, setHomeLatlng] = useState(latlng || DEFAULT_LOCATION);
  const [currentLatlng, setCurrentLatlng] = useState(latlng);
  const [marker, setMarker] = useState(null);
  const [controls, setControls] = useState({ gc: null });
  const [zoom, setZoom] = useState(null);
  const [geo, setGeo] = useState({ data: null, featureGroup: null });
  const [selectedFeature, setSelectedFeature] = useState(null);
  const [prevSelectedJurisdictionOcdid, setPrevSelectedJurisdictionOcdid] = useState(null);

  useEffect(() => {
    if (!mapInstance) return;
    if (!canMove) return;

    mapInstance.on("locationerror", handleLocationError);
    mapInstance.on("locationfound", handleLocationFound);
    mapInstance.on("locationactivate", handleLocationFound);
    mapInstance.on("zoomend", handleZoomChange);
    mapInstance.on("click", handleClick);
    geo.data.on("click", handleFeatureClick);

    return () => {
      mapInstance.off("locationerror", handleLocationError);
      mapInstance.off("locationfound", handleLocationFound);
      mapInstance.off("locationactivate", handleLocationFound);
      mapInstance.off("zoomend", handleZoomChange);
      mapInstance.off("click", handleClick);
      geo.data.off("click", handleFeatureClick);

      if (controls.gc) {
        controls.gc.off("markgeocode", handleAddressResult);
      }
    };
  }, [mapInstance, canmove]);

  useEffect(() => {
    return () => {
      if (mapInstance) {
        mapInstance.remove();
      }
    }

  }, [mapInstance])

  useEffect(() => {
    if ((!latlng && !homeLatlng && !currentLatlng) || !mapInstance) return;

    if (controls.lc) {
      controls.lc.stop();
    }

    const latlngToUse = latlng || currentLatlng || homeLatlng;

    moveMarker(latlngToUse);

    // Debounce the event dispatch to avoid excessive firing
    const timer = setTimeout(() => {
      this.dispatchEvent(
        new CustomEvent("on-map-change", {
          detail: {
            zoom: mapInstance.getZoom(),
            latlng: latlngToUse,
          },
          bubbles: true,
          composed: true,
        }),
      );
    }, 100);

    return () => clearTimeout(timer);
  }, [latlng, geo, homeLatlng, currentLatlng, zoom, mapInstance]);

  useEffect(() => {
    if (!geo.data || !geojson) return;

    geo.data.clearLayers();
    geo.data.addData(geojson);
    
    // handleGeojsonChange({ geoData: geo.data });
  }, [geo, geojson]);

  useEffect(() => {
    const jurisdictionOcdid = selectedFeature?.jurisdiction_ocdid || null;

    if (jurisdictionOcdid === prevSelectedJurisdictionOcdid) return;

    setPrevSelectedJurisdictionOcdid(jurisdictionOcdid);

    const event = new CustomEvent("on-jurisdiction-change", {
      detail: {
        jurisdiction_ocdid: jurisdictionOcdid,
      },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }, [selectedFeature]);

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

  const handleZoomChange = (e) => {
    setZoom(e.target.getZoom());
  };

  const setupMap = (el) => {
    if (!el || mapInstance) return;
    let _gc, _lc;

    let newMapInstance = new Map(el, {
      zoomControl: false,
      zoom: 12,
    });

    let urlTemplate = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    newMapInstance.addLayer(new TileLayer(urlTemplate));

    if (!currentLatlng) {
      newMapInstance.locate();
    }

    if (canMove) {
      _gc = new Geocoder({
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

      _lc = new LocateControl({
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
    }

    let _geoData = new geoJSON();

    let _geoLayer = new FeatureGroup([_geoData]).addTo(newMapInstance);

    let _zoom = new Control.Zoom({
      position: "bottomright",
    }).addTo(newMapInstance);

    setMapInstance(newMapInstance);
    setControls({ gc: _gc, lc: _lc });
    setGeo({ data: _geoData, featureGroup: _geoLayer });
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
    
    mapInstance.panTo(markerLatlng);
  };

  const handleGeojsonChange = ({ geoData }) => {
    if (!geoData) return;

    // Check if latlong is within any geo layer
    // let foundFeature = null;
    // geoData.eachLayer((layer) => {
    //   if (layer.getBounds && layer.getBounds().contains(currentLatlng)) {
    //     foundFeature = layer.feature.properties;
    //   }
    // });
    // setSelectedFeature(foundFeature);
  }
//
const handleFeatureClick = (e) => {
  setSelectedFeature(e.layer.feature.properties);
}

  return html`
    <style>
      ${leafletStyles} ${locateStyles} ${geocoderStyles} .map-container {
        height: 30rem;
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

export function registerCivMap() {
  if (!customElements.get("civ-map")) {
    customElements.define(
      "civ-map",
      component(CivMap, {observedAttributes: ["canmove"] }),
    );
  }
}