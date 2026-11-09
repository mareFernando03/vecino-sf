import { IonButton, IonItem, IonLabel, IonList, IonModal, IonNote, IonSegment, IonSegmentButton, IonTextarea, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { Popup } from 'react-leaflet';
import { api, post, useEventos } from '../../api';
import { Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';

type Estacion = { id: number; nombre: string; lat: number; lng: number; bicis: number; capacidad: number; anclajes_libres: number; distancia_km?: number };

export default function Bicis() {
  const [estaciones, setEstaciones] = useState<Estacion[]>([]);
  const [yo, setYo] = useState<[number, number] | null>(null);
  const [reporte, setReporte] = useState<Estacion | null>(null);
  const [tipo, setTipo] = useState<'bici' | 'estacion'>('bici');
  const [texto, setTexto] = useState('');
  const [msg, setMsg] = useState('');

  const cargar = (pos?: [number, number]) =>
    api<Estacion[]>(`/bicis/estaciones${pos ? `?lat=${pos[0]}&lng=${pos[1]}` : ''}`).then(setEstaciones);
  useIonViewWillEnter(() => { cargar(); });

  // Disponibilidad en tiempo real: cada cambio de una estación llega por SSE.
  useEventos((e) => {
    if (e.tipo === 'estacion') setEstaciones((xs) => xs.map((x) => (x.id === e.datos.id ? { ...x, ...e.datos } : x)));
  });

  function cercanas() {
    navigator.geolocation.getCurrentPosition(
      (p) => { const pos: [number, number] = [p.coords.latitude, p.coords.longitude]; setYo(pos); cargar(pos); },
      () => setMsg('No se pudo obtener tu ubicación. Activá el GPS o el permiso del navegador.'),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  async function enviarReporte() {
    try {
      await post('/bicis/reportes', { estacion_id: reporte!.id, tipo, descripcion: texto });
      setMsg('Reporte enviado. ¡Gracias!');
      setReporte(null); setTexto('');
    } catch (e) { setMsg((e as Error).message); }
  }

  const color = (e: Estacion) => (e.bicis === 0 ? '#d32f2f' : e.bicis <= 2 ? '#f9a825' : '#2e7d32');

  return (
    <Pagina titulo="Bicicletas públicas" volver="/vecino">
      <Mapa centro={yo ?? undefined}>
        {yo && <Punto pos={yo} color="#1565c0" radio={7} />}
        {estaciones.map((e) => (
          <Punto key={e.id} pos={[e.lat, e.lng]} color={color(e)}>
            <Popup><b>{e.nombre}</b><br />{e.bicis} bicis · {e.anclajes_libres} anclajes libres</Popup>
          </Punto>
        ))}
      </Mapa>
      <div className="leyenda">
        <span style={{ ['--c' as string]: '#2e7d32' }}>3 o más bicis</span>
        <span style={{ ['--c' as string]: '#f9a825' }}>1-2</span>
        <span style={{ ['--c' as string]: '#d32f2f' }}>sin bicis</span>
      </div>
      <IonButton expand="block" className="ion-margin-horizontal" onClick={cercanas}>Estaciones cerca mío</IonButton>
      <IonList>
        {estaciones.map((e) => (
          <IonItem key={e.id}>
            <IonLabel>
              <h3>{e.nombre}</h3>
              <p>{e.bicis} bicis disponibles · {e.anclajes_libres} anclajes libres{e.distancia_km != null && ` · a ${e.distancia_km} km`}</p>
            </IonLabel>
            <IonButton slot="end" fill="clear" size="small" onClick={() => setReporte(e)}>Reportar</IonButton>
          </IonItem>
        ))}
      </IonList>
      <IonModal isOpen={!!reporte} onDidDismiss={() => setReporte(null)} initialBreakpoint={0.6} breakpoints={[0, 0.6]}>
        <div className="ion-padding">
          <h3>Reportar un problema</h3>
          <IonNote>{reporte?.nombre}</IonNote>
          <IonSegment value={tipo} onIonChange={(e) => setTipo(e.detail.value as 'bici' | 'estacion')}>
            <IonSegmentButton value="bici">Bicicleta</IonSegmentButton>
            <IonSegmentButton value="estacion">Estación</IonSegmentButton>
          </IonSegment>
          <IonTextarea label="¿Qué pasa?" labelPlacement="stacked" value={texto} onIonInput={(e) => setTexto(e.detail.value ?? '')} rows={3} />
          <IonButton expand="block" disabled={texto.trim().length < 5} onClick={enviarReporte}>Enviar</IonButton>
        </div>
      </IonModal>
      <IonToast isOpen={!!msg} message={msg} duration={3000} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
