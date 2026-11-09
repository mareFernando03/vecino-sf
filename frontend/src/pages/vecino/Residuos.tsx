import { IonBadge, IonButton, IonInput, IonItem, IonLabel, IonList, IonListHeader, IonNote, IonSegment, IonSegmentButton, IonSelect, IonSelectOption, IonTextarea, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { Popup } from 'react-leaflet';
import { api, fecha, post } from '../../api';
import { Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';

type Punto_ = { id: number; nombre: string; lat: number; lng: number; materiales: string[]; horario: string };
type Solicitud = { id: number; tipo: string; descripcion: string; direccion: string; estado: string; creada: string };
const CATS = { organico: 'Orgánico', reciclable: 'Reciclable', voluminoso: 'Voluminoso', peligroso: 'Peligroso', otros: 'Otros' };

export default function Residuos() {
  const [vista, setVista] = useState('registrar');
  const [reg, setReg] = useState({ categoria: 'reciclable', cantidad: 1, unidad: 'kg' });
  const [resumen, setResumen] = useState<Record<string, number>>({});
  const [sol, setSol] = useState({ tipo: 'voluminoso', descripcion: '', direccion: '' });
  const [pos, setPos] = useState<[number, number] | null>(null);
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [puntos, setPuntos] = useState<Punto_[]>([]);
  const [horarios, setHorarios] = useState<{ barrio: string; domiciliaria: string; reciclables: string }[]>([]);
  const [msg, setMsg] = useState('');

  const cargar = () => {
    api('/residuos/registros').then((d) => setResumen(d.ultimos_30_dias));
    api('/residuos/solicitudes').then(setSolicitudes);
  };
  useIonViewWillEnter(() => { cargar(); api('/residuos/puntos-reciclaje').then(setPuntos); api('/residuos/horarios').then(setHorarios); });

  async function registrar() {
    try { await post('/residuos/registros', reg); setMsg('Registrado. ¡Gracias por separar!'); cargar(); }
    catch (e) { setMsg((e as Error).message); }
  }

  async function solicitar() {
    try {
      const r = await post<Solicitud>('/residuos/solicitudes', { ...sol, lat: pos![0], lng: pos![1] });
      setMsg(`Solicitud #${r.id} registrada. Te avisamos cuando la retiremos.`);
      setSol({ tipo: 'voluminoso', descripcion: '', direccion: '' }); setPos(null); cargar();
    } catch (e) { setMsg((e as Error).message); }
  }

  function miUbicacion() {
    navigator.geolocation.getCurrentPosition((p) => setPos([p.coords.latitude, p.coords.longitude]),
      () => setMsg('No se pudo obtener tu ubicación: marcala en el mapa.'));
  }

  return (
    <Pagina titulo="Residuos y reciclaje" volver="/vecino">
      <IonSegment value={vista} onIonChange={(e) => setVista(String(e.detail.value))} scrollable>
        <IonSegmentButton value="registrar">Registrar</IonSegmentButton>
        <IonSegmentButton value="solicitar">Retiro especial</IonSegmentButton>
        <IonSegmentButton value="puntos">Puntos y horarios</IonSegmentButton>
      </IonSegment>

      {vista === 'registrar' && (
        <IonList>
          <IonItem>
            <IonSelect label="Categoría" labelPlacement="stacked" value={reg.categoria} onIonChange={(e) => setReg({ ...reg, categoria: e.detail.value })}>
              {Object.entries(CATS).map(([k, v]) => <IonSelectOption key={k} value={k}>{v}</IonSelectOption>)}
            </IonSelect>
          </IonItem>
          <IonItem><IonInput type="number" label="Cantidad" labelPlacement="stacked" min="0.1" value={reg.cantidad} onIonInput={(e) => setReg({ ...reg, cantidad: Number(e.detail.value) })} /></IonItem>
          <IonItem>
            <IonSelect label="Unidad" labelPlacement="stacked" value={reg.unidad} onIonChange={(e) => setReg({ ...reg, unidad: e.detail.value })}>
              <IonSelectOption value="kg">kg</IonSelectOption><IonSelectOption value="bolsas">bolsas</IonSelectOption><IonSelectOption value="unidades">unidades</IonSelectOption>
            </IonSelect>
          </IonItem>
          <IonButton expand="block" className="ion-margin" disabled={!(reg.cantidad > 0)} onClick={registrar}>Registrar</IonButton>
          <IonListHeader>Tus últimos 30 días</IonListHeader>
          {Object.entries(resumen).map(([k, v]) => <IonItem key={k}><IonLabel>{k}</IonLabel><IonNote slot="end">{v}</IonNote></IonItem>)}
          {!Object.keys(resumen).length && <IonItem><IonLabel>Todavía no registraste residuos.</IonLabel></IonItem>}
        </IonList>
      )}

      {vista === 'solicitar' && (
        <>
          <IonList>
            <IonItem>
              <IonSelect label="Tipo de residuo" labelPlacement="stacked" value={sol.tipo} onIonChange={(e) => setSol({ ...sol, tipo: e.detail.value })}>
                <IonSelectOption value="voluminoso">Voluminoso (muebles, colchones)</IonSelectOption>
                <IonSelectOption value="reciclable">Reciclable en cantidad</IonSelectOption>
                <IonSelectOption value="peligroso">Peligroso (pinturas, baterías, aceites)</IonSelectOption>
              </IonSelect>
            </IonItem>
            <IonItem><IonTextarea label="Qué hay que retirar" labelPlacement="stacked" rows={2} value={sol.descripcion} onIonInput={(e) => setSol({ ...sol, descripcion: e.detail.value ?? '' })} /></IonItem>
            <IonItem><IonInput label="Dirección" labelPlacement="stacked" value={sol.direccion} onIonInput={(e) => setSol({ ...sol, direccion: e.detail.value ?? '' })} /></IonItem>
            <IonItem lines="none"><IonNote>Marcá el lugar en el mapa o</IonNote><IonButton slot="end" size="small" fill="clear" onClick={miUbicacion}>usar mi ubicación</IonButton></IonItem>
          </IonList>
          <Mapa alto="30vh" onClick={(lat, lng) => setPos([lat, lng])}>{pos && <Punto pos={pos} color="#1565c0" />}</Mapa>
          <IonButton expand="block" className="ion-margin" disabled={!pos || sol.descripcion.trim().length < 5 || sol.direccion.trim().length < 3} onClick={solicitar}>Solicitar retiro</IonButton>
          <IonList>
            <IonListHeader>Mis solicitudes</IonListHeader>
            {solicitudes.map((s) => (
              <IonItem key={s.id}>
                <IonLabel><h3>#{s.id} · {s.tipo}</h3><p>{s.descripcion} · {fecha(s.creada)}</p></IonLabel>
                <IonBadge color={s.estado === 'recolectada' ? 'success' : s.estado === 'asignada' ? 'warning' : 'medium'}>{s.estado}</IonBadge>
              </IonItem>
            ))}
          </IonList>
        </>
      )}

      {vista === 'puntos' && (
        <>
          <Mapa alto="38vh">
            {puntos.map((p) => (
              <Punto key={p.id} pos={[p.lat, p.lng]} color="#2e7d32">
                <Popup>
                  <b>{p.nombre}</b><br />{p.materiales.join(', ')}<br />{p.horario}<br />
                  <a href={`https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`} target="_blank" rel="noreferrer">Cómo llegar</a>
                </Popup>
              </Punto>
            ))}
          </Mapa>
          <IonList>
            <IonListHeader>Horarios de recolección</IonListHeader>
            {horarios.map((h) => (
              <IonItem key={h.barrio}><IonLabel><h3>Zona {h.barrio}</h3><p>Domiciliaria: {h.domiciliaria}</p><p>Reciclables: {h.reciclables}</p></IonLabel></IonItem>
            ))}
          </IonList>
        </>
      )}
      <IonToast isOpen={!!msg} message={msg} duration={3500} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
