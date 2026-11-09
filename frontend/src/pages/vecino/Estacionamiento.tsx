import { IonButton, IonCard, IonCardContent, IonInput, IonItem, IonList, IonSelect, IonSelectOption, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useEffect, useState } from 'react';
import { Polygon, Popup } from 'react-leaflet';
import { api, pesos, post } from '../../api';
import { Mapa } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';
import { mostrarLocal } from '../../push';

type Zona = { id: number; nombre: string; tarifa_hora: number; horario: string; poligono: [number, number][] };
type Activo = { id: number; zona_id: number; patente: string; inicio: string; fin: string; importe: number; medio: string; comprobante: string };
const MEDIOS: Record<string, string> = { tarjeta: 'Tarjeta de crédito', debito: 'Débito', transferencia: 'Transferencia' };

export default function Estacionamiento() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [activo, setActivo] = useState<Activo | null>(null);
  const [zona, setZona] = useState<number>();
  const [patente, setPatente] = useState(localStorage.getItem('patente') ?? '');
  const [minutos, setMinutos] = useState(60);
  const [medio, setMedio] = useState('tarjeta');
  const [resta, setResta] = useState(0);
  const [msg, setMsg] = useState('');

  useIonViewWillEnter(() => {
    api<Zona[]>('/estacionamiento/zonas').then((z) => { setZonas(z); setZona(z[0]?.id); });
    api<Activo | null>('/estacionamiento/activo').then(setActivo);
  });

  // Temporizador local. El aviso a los 10 minutos también llega por push desde el servidor,
  // por si la app está cerrada.
  useEffect(() => {
    if (!activo) return;
    let avisado = false;
    const t = setInterval(() => {
      const s = Math.max(0, Math.round((new Date(activo.fin).getTime() - Date.now()) / 1000));
      setResta(s);
      if (s <= 600 && s > 0 && !avisado) { avisado = true; setMsg('Faltan 10 minutos: podés extender el tiempo.'); mostrarLocal('Estacionamiento', 'Faltan 10 minutos'); }
      if (s === 0) setActivo(null);
    }, 1000);
    return () => clearInterval(t);
  }, [activo]);

  const z = zonas.find((x) => x.id === (activo?.zona_id ?? zona));

  async function iniciar() {
    try {
      localStorage.setItem('patente', patente.toUpperCase());
      const e = await post<Activo>('/estacionamiento', { zona_id: zona, patente: patente.toUpperCase().replace(/\s/g, ''), minutos, medio });
      setActivo(e);
      setMsg(`Pago simulado aprobado · comprobante ${e.comprobante}`);
    } catch (e) { setMsg((e as Error).message); }
  }

  async function extender(m: number) {
    try {
      const e = await post<Activo>('/estacionamiento/extender', { minutos: m, medio: activo?.medio ?? medio });
      setActivo(e);
      setMsg(`Extendido ${m} minutos · comprobante ${e.comprobante}`);
    }
    catch (e) { setMsg((e as Error).message); }
  }

  const hh = String(Math.floor(resta / 3600)).padStart(2, '0');
  const mm = String(Math.floor((resta % 3600) / 60)).padStart(2, '0');
  const ss = String(resta % 60).padStart(2, '0');

  return (
    <Pagina titulo="Estacionamiento medido" volver="/vecino">
      <Mapa zoom={15} alto="32vh" centro={[-31.428, -62.0835]}>
        {zonas.map((x) => (
          <Polygon key={x.id} positions={x.poligono} pathOptions={{ color: x.id === z?.id ? '#1f6f4a' : '#555', fillOpacity: 0.25 }}>
            <Popup><b>{x.nombre}</b><br />{pesos(x.tarifa_hora)} por hora<br />{x.horario}</Popup>
          </Polygon>
        ))}
      </Mapa>
      {activo ? (
        <IonCard>
          <IonCardContent>
            <p>Patente <b>{activo.patente}</b> · {z?.nombre}</p>
            <div className="temporizador" aria-live="polite">{hh}:{mm}:{ss}</div>
            <p style={{ textAlign: 'center' }}>Vence a las {new Date(activo.fin).toLocaleTimeString('es-AR', { timeStyle: 'short' })} · pagado {pesos(activo.importe)}</p>
            <p style={{ textAlign: 'center' }}><small>{MEDIOS[activo.medio]} · comprobante {activo.comprobante} (pasarela simulada)</small></p>
            <IonButton expand="block" onClick={() => extender(30)}>Extender 30 minutos</IonButton>
            <IonButton expand="block" fill="outline" onClick={() => extender(60)}>Extender 1 hora</IonButton>
          </IonCardContent>
        </IonCard>
      ) : (
        <IonList>
          <IonItem>
            <IonSelect label="Zona" labelPlacement="stacked" value={zona} onIonChange={(e) => setZona(e.detail.value)}>
              {zonas.map((x) => <IonSelectOption key={x.id} value={x.id}>{x.nombre} · {pesos(x.tarifa_hora)}/h</IonSelectOption>)}
            </IonSelect>
          </IonItem>
          <IonItem><IonInput label="Patente" labelPlacement="stacked" placeholder="AB123CD o ABC123" value={patente} onIonInput={(e) => setPatente(e.detail.value ?? '')} /></IonItem>
          <IonItem>
            <IonSelect label="Tiempo" labelPlacement="stacked" value={minutos} onIonChange={(e) => setMinutos(e.detail.value)}>
              {[30, 60, 90, 120, 180].map((m) => <IonSelectOption key={m} value={m}>{m} minutos</IonSelectOption>)}
            </IonSelect>
          </IonItem>
          <IonItem>
            <IonSelect label="Medio de pago (simulado)" labelPlacement="stacked" value={medio} onIonChange={(e) => setMedio(e.detail.value)}>
              {Object.entries(MEDIOS).map(([k, v]) => <IonSelectOption key={k} value={k}>{v}</IonSelectOption>)}
            </IonSelect>
          </IonItem>
          <p className="ion-padding-horizontal">{z?.horario}. Total: <b>{z && pesos((z.tarifa_hora * minutos) / 60)}</b></p>
          <IonButton expand="block" className="ion-margin" disabled={!zona || patente.trim().length < 6} onClick={iniciar}>Pagar e iniciar</IonButton>
        </IonList>
      )}
      <IonToast isOpen={!!msg} message={msg} duration={3500} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
