import { IonBadge, IonButton, IonCheckbox, IonItem, IonLabel, IonList, IonListHeader, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { Popup } from 'react-leaflet';
import { api, distanciaKm, fecha, put, useEventos } from '../../api';
import { Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';
import { mostrarLocal } from '../../push';

type Alarma = { id: number; nombre: string; barrio: string; lat: number; lng: number; activa: boolean; actualizada: string };
type Prefs = { tipos: string[]; barrios: string[]; frecuencia: string };
const ZONAS = ['Centro', 'Norte', 'Sur', 'Este', 'Oeste'];

export default function Alarmas() {
  const [alarmas, setAlarmas] = useState<Alarma[]>([]);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [yo, setYo] = useState<[number, number] | null>(null);
  const [msg, setMsg] = useState('');

  useIonViewWillEnter(() => {
    api('/alarmas').then(setAlarmas);
    api('/notificaciones/preferencias').then(setPrefs);
    navigator.geolocation?.getCurrentPosition((p) => setYo([p.coords.latitude, p.coords.longitude]), () => {});
  });

  // Estado en tiempo real. Si se activa una alarma a menos de 1 km, aviso aunque la zona
  // no esté suscripta: la cercanía se calcula en el teléfono, sin mandar la ubicación al servidor.
  useEventos((e) => {
    if (e.tipo !== 'alarma') return;
    const a: Alarma = e.datos;
    setAlarmas((xs) => xs.map((x) => (x.id === a.id ? a : x)));
    if (a.activa && yo && distanciaKm(yo, [a.lat, a.lng]) < 1) {
      setMsg(`¡Alarma activada cerca tuyo! ${a.nombre}`);
      mostrarLocal('Alarma cerca tuyo', a.nombre);
    }
  });

  async function suscribir(zona: string, si: boolean) {
    if (!prefs) return;
    const actuales = prefs.barrios.length ? prefs.barrios : ZONAS;   // vacío = todas
    const barrios = si ? [...new Set([...actuales, zona])] : actuales.filter((b) => b !== zona);
    const tipos = prefs.tipos.includes('alarma') ? prefs.tipos : [...prefs.tipos, 'alarma'];
    setPrefs(await put('/notificaciones/preferencias', { ...prefs, barrios, tipos }));
  }

  const activas = alarmas.filter((a) => a.activa).length;
  return (
    <Pagina titulo="Alarmas comunitarias" volver="/vecino">
      <Mapa centro={yo ?? undefined}>
        {yo && <Punto pos={yo} color="#1565c0" radio={7} />}
        {alarmas.map((a) => (
          <Punto key={a.id} pos={[a.lat, a.lng]} color={a.activa ? '#d32f2f' : '#9e9e9e'} radio={a.activa ? 12 : 8}>
            <Popup><b>{a.nombre}</b><br />{a.activa ? 'ACTIVADA' : 'En reposo'} · {fecha(a.actualizada)}</Popup>
          </Punto>
        ))}
      </Mapa>
      <p className="ion-padding-horizontal">{activas ? <IonBadge color="danger">{activas} activadas</IonBadge> : 'Todas las alarmas en reposo.'}</p>
      <IonList>
        <IonListHeader>Recibir alertas de estas zonas</IonListHeader>
        {ZONAS.map((z) => (
          <IonItem key={z}>
            <IonCheckbox checked={!prefs?.barrios.length || prefs.barrios.includes(z)} disabled={!prefs}
              onIonChange={(e) => suscribir(z, e.detail.checked)}>{z}</IonCheckbox>
          </IonItem>
        ))}
        <IonItem lines="none"><IonLabel><p>Sin ninguna zona marcada a mano, recibís las de toda la ciudad.</p></IonLabel></IonItem>
        <IonListHeader>Estado</IonListHeader>
        {alarmas.map((a) => (
          <IonItem key={a.id}>
            <IonLabel><h3>{a.nombre}</h3><p>{a.activa ? 'Activada' : 'En reposo'} · {fecha(a.actualizada)}</p></IonLabel>
          </IonItem>
        ))}
      </IonList>
      <IonToast isOpen={!!msg} message={msg} duration={5000} color="danger" position="top" onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
