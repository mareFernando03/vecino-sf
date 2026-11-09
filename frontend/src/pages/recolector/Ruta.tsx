// App del personal de recolección: su ruta en orden, escaneo del QR de cada contenedor
// (o el código tipeado si la cámara falla) y reporte de incidentes.
import { IonButton, IonCard, IonCardContent, IonCheckbox, IonInput, IonItem, IonLabel, IonList, IonListHeader, IonModal, IonNote, IonSelect, IonSelectOption, IonTextarea, IonToast, useIonViewWillEnter } from '@ionic/react';
import { Html5Qrcode } from 'html5-qrcode';
import { useEffect, useRef, useState } from 'react';
import { Polyline, Popup } from 'react-leaflet';
import { api, post, useEventos } from '../../api';
import { Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';
import { activarPush, pushDisponible } from '../../push';
import { useSesion } from '../../sesion';

type Parada = { tipo: string; id: number; codigo: string; lat: number; lng: number; hecha: boolean; detalle?: string };
type Ruta = { id: number; estado: string; paradas: Parada[]; distancia_km: number; geometria: [number, number][]; hechas: number; recolector_id: number };

function Lector({ alLeer }: { alLeer: (texto: string) => void }) {
  const cb = useRef(alLeer);
  cb.current = alLeer;
  const [error, setError] = useState('');
  useEffect(() => {
    const lector = new Html5Qrcode('lector-qr');
    lector.start({ facingMode: 'environment' }, { fps: 10, qrbox: 220 }, (t) => { lector.stop().catch(() => {}); cb.current(t); }, () => {})
      .catch(() => setError('No se pudo abrir la cámara: ingresá el código a mano.'));
    return () => { if (lector.isScanning) lector.stop().catch(() => {}); };
  }, []);
  return <><div id="lector-qr" className="lector-qr" />{error && <p className="ion-padding">{error}</p>}</>;
}

export default function RutaRecolector() {
  const { usuario } = useSesion();
  const [ruta, setRuta] = useState<Ruta | null>(null);
  const [escanear, setEscanear] = useState(false);
  const [codigo, setCodigo] = useState('');
  const [inc, setInc] = useState({ abierto: false, tipo: 'contenedor_danado', descripcion: '', codigo: '' });
  const [msg, setMsg] = useState('');

  const cargar = () => api<Ruta | null>('/residuos/mi-ruta').then(setRuta);
  useIonViewWillEnter(() => { cargar(); });
  useEventos((e) => { if (e.tipo === 'ruta' && e.datos.recolector_id === usuario?.id) cargar(); });

  async function registrar(texto: string) {
    setEscanear(false);
    try {
      const r = await post<Ruta>('/residuos/recolecciones', { codigo: texto });
      setMsg(`${texto.toUpperCase()} registrado (${r.hechas}/${r.paradas.length})`);
      setCodigo('');
      setRuta(r.estado === 'completada' ? null : r);
      if (r.estado === 'completada') setMsg('¡Ruta completada!');
    } catch (e) { setMsg((e as Error).message); }
  }

  async function reportar() {
    try {
      await post('/residuos/incidentes', { tipo: inc.tipo, descripcion: inc.descripcion, codigo: inc.codigo || null });
      setMsg('Incidente reportado a la central');
      setInc({ abierto: false, tipo: 'contenedor_danado', descripcion: '', codigo: '' });
    } catch (e) { setMsg((e as Error).message); }
  }

  const siguiente = ruta?.paradas.find((p) => !p.hecha);

  return (
    <Pagina titulo="Mi ruta">
      {!ruta ? (
        <IonCard><IonCardContent>No tenés una ruta asignada. Cuando la central te asigne una, aparece acá y te llega un aviso.</IonCardContent></IonCard>
      ) : (
        <>
          <Mapa alto="38vh" centro={siguiente ? [siguiente.lat, siguiente.lng] : undefined} zoom={14}>
            <Polyline positions={ruta.geometria} pathOptions={{ color: '#1565c0', weight: 4 }} />
            {ruta.paradas.map((p, i) => (
              <Punto key={p.codigo} pos={[p.lat, p.lng]} color={p.hecha ? '#9e9e9e' : p === siguiente ? '#d32f2f' : p.tipo === 'solicitud' ? '#1565c0' : '#2e7d32'}>
                <Popup>{i + 1}. {p.codigo}{p.detalle && <><br />{p.detalle}</>}</Popup>
              </Punto>
            ))}
          </Mapa>
          <IonCard>
            <IonCardContent>
              <b>{ruta.hechas}/{ruta.paradas.length}</b> paradas · {ruta.distancia_km} km
              {siguiente && <> · próxima: <b>{siguiente.codigo}</b>{' '}
                <a href={`https://www.google.com/maps/dir/?api=1&destination=${siguiente.lat},${siguiente.lng}`} target="_blank" rel="noreferrer">navegar</a></>}
              <IonButton expand="block" onClick={() => setEscanear(true)}>Escanear QR</IonButton>
              <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
                <IonInput label="o ingresar el código" labelPlacement="stacked" placeholder="SF-C-001" value={codigo} onIonInput={(e) => setCodigo(e.detail.value ?? '')} />
                <IonButton disabled={codigo.trim().length < 3} onClick={() => registrar(codigo)}>Registrar</IonButton>
              </div>
            </IonCardContent>
          </IonCard>
          <IonList>
            <IonListHeader>Paradas en orden</IonListHeader>
            {ruta.paradas.map((p, i) => (
              <IonItem key={p.codigo}>
                <IonCheckbox slot="start" checked={p.hecha} disabled />
                <IonLabel className="ion-text-wrap"><h3>{i + 1}. {p.codigo}</h3>{p.detalle && <p>{p.detalle}</p>}</IonLabel>
              </IonItem>
            ))}
          </IonList>
        </>
      )}
      {/* El aviso de "ruta asignada" llega por push aunque la app esté cerrada. */}
      {pushDisponible() && Notification.permission !== 'granted' && (
        <IonButton expand="block" fill="clear" className="ion-margin" onClick={async () => setMsg(await activarPush())}>Activar avisos de rutas nuevas</IonButton>
      )}
      <IonButton expand="block" color="danger" fill="outline" className="ion-margin" onClick={() => setInc({ ...inc, abierto: true, codigo: siguiente?.tipo === 'contenedor' ? siguiente.codigo : '' })}>Reportar incidente</IonButton>

      <IonModal isOpen={escanear} onDidDismiss={() => setEscanear(false)}>
        <Pagina titulo="Escanear contenedor" acciones={<IonButton onClick={() => setEscanear(false)}>Cerrar</IonButton>}>
          {escanear && <Lector alLeer={registrar} />}
        </Pagina>
      </IonModal>
      <IonModal isOpen={inc.abierto} onDidDismiss={() => setInc({ ...inc, abierto: false })} initialBreakpoint={0.75} breakpoints={[0, 0.75]}>
        <div className="ion-padding">
          <h3>Reportar incidente</h3>
          <IonSelect label="Tipo" labelPlacement="stacked" value={inc.tipo} onIonChange={(e) => setInc({ ...inc, tipo: e.detail.value })}>
            <IonSelectOption value="contenedor_danado">Contenedor dañado</IonSelectOption>
            <IonSelectOption value="acceso_bloqueado">Acceso bloqueado</IonSelectOption>
            <IonSelectOption value="desborde">Desborde</IonSelectOption>
            <IonSelectOption value="derrame">Derrame</IonSelectOption>
            <IonSelectOption value="otro">Otro</IonSelectOption>
          </IonSelect>
          <IonInput label="Contenedor (opcional)" labelPlacement="stacked" value={inc.codigo} onIonInput={(e) => setInc({ ...inc, codigo: e.detail.value ?? '' })} />
          <IonTextarea label="Descripción" labelPlacement="stacked" rows={3} value={inc.descripcion} onIonInput={(e) => setInc({ ...inc, descripcion: e.detail.value ?? '' })} />
          <IonNote>Un contenedor dañado o bloqueado sale de las próximas rutas hasta que la central lo resuelva.</IonNote>
          <IonButton expand="block" disabled={inc.descripcion.trim().length < 3} onClick={reportar}>Enviar</IonButton>
        </div>
      </IonModal>
      <IonToast isOpen={!!msg} message={msg} duration={3000} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
