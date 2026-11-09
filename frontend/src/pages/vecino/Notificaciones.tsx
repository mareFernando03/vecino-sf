import { IonButton, IonCheckbox, IonItem, IonLabel, IonList, IonListHeader, IonNote, IonSegment, IonSegmentButton, IonSelect, IonSelectOption, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { api, fecha, put, useEventos } from '../../api';
import { Pagina } from '../../components/Pagina';
import { activarPush, pushDisponible } from '../../push';

type Aviso = { id: number; tipo: string; titulo: string; cuerpo: string; enlace?: string; barrio?: string; fecha: string; usuario_id?: number };
type Prefs = { tipos: string[]; barrios: string[]; frecuencia: string };

const TIPOS: Record<string, string> = {
  corte: 'Cortes de servicio', obra: 'Obras públicas', evento: 'Eventos', emergencia: 'Emergencias',
  residuos: 'Residuos y reciclaje', alarma: 'Alarmas comunitarias', tributaria: 'Vencimientos',
  reclamo: 'Mis reclamos', estacionamiento: 'Estacionamiento',
};
const ZONAS = ['Centro', 'Norte', 'Sur', 'Este', 'Oeste'];

export default function Notificaciones() {
  const [vista, setVista] = useState<'historial' | 'preferencias'>('historial');
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [msg, setMsg] = useState('');

  const cargar = () => api('/notificaciones').then(setAvisos);
  useIonViewWillEnter(() => { cargar(); api('/notificaciones/preferencias').then(setPrefs); });
  useEventos((e) => { if (e.tipo === 'notificacion') cargar(); });

  async function guardar(p: Prefs) {
    setPrefs(await put('/notificaciones/preferencias', p));
  }
  const alternar = (lista: string[], x: string, si: boolean) => (si ? [...new Set([...lista, x])] : lista.filter((y) => y !== x));

  return (
    <Pagina titulo="Notificaciones" volver="/vecino">
      <IonSegment value={vista} onIonChange={(e) => setVista(e.detail.value as 'historial' | 'preferencias')}>
        <IonSegmentButton value="historial">Historial</IonSegmentButton>
        <IonSegmentButton value="preferencias">Preferencias</IonSegmentButton>
      </IonSegment>
      {vista === 'historial' ? (
        <IonList>
          {avisos.map((a) => (
            <IonItem key={a.id} routerLink={a.enlace ?? undefined} detail={!!a.enlace}>
              <IonLabel className="ion-text-wrap">
                <h3>{a.titulo}</h3>
                <p>{a.cuerpo}</p>
                <IonNote>{TIPOS[a.tipo]} · {a.barrio ?? 'toda la ciudad'} · {fecha(a.fecha)}</IonNote>
              </IonLabel>
            </IonItem>
          ))}
        </IonList>
      ) : prefs && (
        <IonList>
          <IonItem lines="none">
            <IonButton disabled={!pushDisponible()} onClick={async () => setMsg(await activarPush())}>Activar notificaciones push</IonButton>
          </IonItem>
          <IonListHeader>Qué avisos recibir</IonListHeader>
          {Object.entries(TIPOS).map(([k, v]) => (
            <IonItem key={k}>
              <IonCheckbox checked={k === 'emergencia' || prefs.tipos.includes(k)} disabled={k === 'emergencia'}
                onIonChange={(e) => guardar({ ...prefs, tipos: alternar(prefs.tipos, k, e.detail.checked) })}>
                {v}{k === 'emergencia' && ' (siempre)'}
              </IonCheckbox>
            </IonItem>
          ))}
          <IonListHeader>Zonas de interés</IonListHeader>
          {ZONAS.map((z) => (
            <IonItem key={z}>
              <IonCheckbox checked={prefs.barrios.includes(z)} onIonChange={(e) => guardar({ ...prefs, barrios: alternar(prefs.barrios, z, e.detail.checked) })}>{z}</IonCheckbox>
            </IonItem>
          ))}
          <IonItem lines="none"><IonNote>Sin zonas marcadas recibís los avisos de toda la ciudad.</IonNote></IonItem>
          <IonItem>
            <IonSelect label="Frecuencia de los push" labelPlacement="stacked" value={prefs.frecuencia} onIonChange={(e) => guardar({ ...prefs, frecuencia: e.detail.value })}>
              <IonSelectOption value="inmediata">Al instante</IonSelectOption>
              <IonSelectOption value="resumen_diario">Sólo en el historial (sin push, salvo emergencias)</IonSelectOption>
            </IonSelect>
          </IonItem>
        </IonList>
      )}
      <IonToast isOpen={!!msg} message={msg} duration={3500} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
