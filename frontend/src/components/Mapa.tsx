// Mapa base con Leaflet y teselas de OpenStreetMap (sin clave de API).
// Para producción con mucho tráfico conviene un proveedor con SLA (Mapbox, Google Maps).
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { ReactNode, useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, useMap } from 'react-leaflet';
import { CENTRO } from '../api';

function Ajustar() {
  // Ionic monta las páginas con animación: el mapa necesita recalcular su tamaño al aparecer.
  const map = useMap();
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 300);
    return () => clearTimeout(t);
  }, [map]);
  return null;
}

export function Mapa({ children, centro = CENTRO, zoom = 14, alto = '45vh', onClick }: {
  children?: ReactNode; centro?: [number, number]; zoom?: number; alto?: string;
  onClick?: (lat: number, lng: number) => void;
}) {
  return (
    <MapContainer center={centro} zoom={zoom} style={{ height: alto, width: '100%' }}
      ref={(m) => { if (m && onClick) { m.off('click'); m.on('click', (e: L.LeafletMouseEvent) => onClick(e.latlng.lat, e.latlng.lng)); } }}>
      <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Ajustar />
      {children}
    </MapContainer>
  );
}

export function Punto({ pos, color, radio = 9, children }: { pos: [number, number]; color: string; radio?: number; children?: ReactNode }) {
  return (
    <CircleMarker center={pos} radius={radio} pathOptions={{ color: '#222', weight: 1, fillColor: color, fillOpacity: 0.9 }}>
      {children}
    </CircleMarker>
  );
}

export const colorLlenado = (p: number) => (p >= 80 ? '#d32f2f' : p >= 60 ? '#f9a825' : '#2e7d32');
