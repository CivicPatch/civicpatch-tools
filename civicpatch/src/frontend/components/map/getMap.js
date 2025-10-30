import "leaflet";

let mapInstance;
export const getMap = () => {
  if (!mapInstance) {
    mapInstance = L.map('map')
      .setView([51.505, -0.09], 13);
    let urlTemplate = 'http://{s}.tile.osm.org/{z}/{x}/{y}.png';
    mapInstance.addLayer(L.tileLayer(urlTemplate, {minZoom: 4}));
  }
  return mapInstance;
}

