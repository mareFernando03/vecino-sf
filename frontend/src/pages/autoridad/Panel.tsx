// Panel de la autoridad: mapa en tiempo real, planificación de rutas, incidentes y campañas.
// Pensado para escritorio (en pantallas anchas el mapa y la columna lateral van lado a lado).
import { IonBadge, IonButton, IonCard, IonCardContent, IonCardHeader, IonCardTitle, IonInput, IonItem, IonLabel, IonList, IonModal, IonNote, IonRange, IonSelect, IonSelectOption, IonTextarea, IonToast, useIonViewWillEnter } from '@ionic/react';
import { QRCodeSVG } from 'qrcode.react';
import { useState } from 'react';
import { Polyline, Popup } from 'react-leaflet';
import { api, fecha, patch, post, useEventos } from '../../api';
import { colorLlenado, Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';

type Contenedor = { id: number; codigo: string; barrio: string; tipo: string; lat: number; lng: number; llenado: number; estado: string; actualizado: string };
type Parada = { tipo: string; id: number; codigo: string; lat: number; lng: number; hecha: boolean; detalle?: string };
type Ruta = { id: number; recolector: string; recolector_id: number; estado: string; paradas: Parada[]; distancia_km: number; geometria: [number, number][]; hechas: number };
type Solicitud = { id: number; tipo: string; descripcion: string; direccion: string; lat: number; lng: number; estado: string };
type Incidente = { id: number; tipo: string; descripcion: string; contenedor_id?: number; fecha: string; estado: string };
type MapaDatos = { base: [number, number]; contenedores: Contenedor[]; solicitudes: Solicitud[]; rutas: Ruta[]; incidentes: Incidente[] };

const COLORES_RUTA = ['#1565c0', '#6a1b9a', '#00838f', '#ef6c00'];
const ZONAS = ['Centro', 'Norte', 'Sur', 'Este', 'Oeste'];

export default function Panel() {
  const [m, setM] = useState<MapaDatos | null>(null);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [recs, setRecs] = useState<{ id: number; nombre: string }[]>([]);
  const [plan, setPlan] = useState({ recolector_id: 0, umbral_llenado: 70, barrios: [] as string[], incluir_solicitudes: true });
  const [campania, setCampania] = useState({ titulo: '', cuerpo: '' });
  const [qrs, setQrs] = useState(false);
  const [msg, setMsg] = useState('');

  const cargar = () => { api('/residuos/mapa').then(setM); api('/residuos/estadisticas').then(setStats); };
  useIonViewWillEnter(() => {
    cargar();
    api('/residuos/recolectores').then((r) => { setRecs(r); setPlan((p) => ({ ...p, recolector_id: r[0]?.id })); });
  });

  // Cada evento actualiza sólo lo que cambió, sin recargar el mapa entero.
  useEventos((e) => {
    setM((prev) => {
      if (!prev) return prev;
      if (e.tipo === 'contenedor') return { ...prev, contenedores: prev.contenedores.map((c) => (c.id === e.datos.id ? e.datos : c)) };
      if (e.tipo === 'ruta') {
        const otras = prev.rutas.filter((r) => r.id !== e.datos.id);
        return { ...prev, rutas: e.datos.estado === 'completada' ? otras : [...otras, e.datos] };
      }
      return prev;
    });
    if (['solicitud', 'incidente', 'ruta'].includes(e.tipo)) cargar();
  });

  async function planificar() {
    try {
      const r = await post('/residuos/rutas', plan);
      setMsg(`Ruta #${r.id} asignada a ${r.recolector}: ${r.paradas.length} paradas, ${r.distancia_km} km (trazado ${r.trazado === 'osrm' ? 'por calles' : 'en línea recta'})`);
      cargar();
    } catch (e) { setMsg((e as Error).message); }
  }

  async function resolver(i: Incidente) {
    await patch(`/residuos/incidentes/${i.id}`, {});
    cargar();
  }

  async function enviarCampania() {
    await post('/notificaciones/enviar', { tipo: 'residuos', ...campania, enlace: '/vecino/residuos' });
    setMsg('Campaña enviada a los vecinos');
    setCampania({ titulo: '', cuerpo: '' });
  }

  const cont = (id?: number) => m?.contenedores.find((c) => c.id === id);
  const candidatos = m?.contenedores.filter((c) => c.llenado >= plan.umbral_llenado && (!plan.barrios.length || plan.barrios.includes(c.barrio))).length ?? 0;

  return (
    <Pagina titulo="Panel de residuos · Autoridad" acciones={<IonButton onClick={() => setQrs(true)}>QR</IonButton>}>
      <div style={{ display: 'flex', gap: 8, padding: 8, flexWrap: 'wrap' }}>
        <IonBadge color="medium">{stats.contenedores} contenedores</IonBadge>
        <IonBadge color="danger">{stats.contenedores_llenos} llenos (≥80 %)</IonBadge>
        <IonBadge color="warning">{stats.solicitudes_pendientes} solicitudes pendientes</IonBadge>
        <IonBadge color="success">{stats.recolecciones_hoy} recolecciones hoy</IonBadge>
        <IonBadge color="danger">{stats.incidentes_abiertos} incidentes</IonBadge>
      </div>
      <div className="panel">
        <div>
          {m && (
            <Mapa alto="62vh" zoom={14}>
              <Punto pos={m.base} color="#000" radio={6}><Popup>Base operativa</Popup></Punto>
              {m.rutas.map((r, i) => (
                <Polyline key={r.id} positions={r.geometria} pathOptions={{ color: COLORES_RUTA[i % 4], weight: 4, opacity: 0.8 }}>
                  <Popup>Ruta #{r.id} · {r.recolector} · {r.hechas}/{r.paradas.length} paradas</Popup>
                </Polyline>
              ))}
              {m.contenedores.map((c) => (
                <Punto key={c.id} pos={[c.lat, c.lng]} color={c.estado !== 'ok' ? '#000' : colorLlenado(c.llenado)} radio={7}>
                  <Popup><b>{c.codigo}</b> · {c.tipo}<br />Llenado {c.llenado} % · {c.estado}<br />{fecha(c.actualizado)}</Popup>
                </Punto>
              ))}
              {m.solicitudes.map((s) => (
                <Punto key={`s${s.id}`} pos={[s.lat, s.lng]} color="#1565c0" radio={8}>
                  <Popup><b>Solicitud #{s.id}</b> · {s.tipo}<br />{s.descripcion}<br />{s.direccion} · {s.estado}</Popup>
                </Punto>
              ))}
            </Mapa>
          )}
          <div className="leyenda">
            <span style={{ ['--c' as string]: '#2e7d32' }}>&lt;60 %</span>
            <span style={{ ['--c' as string]: '#f9a825' }}>60-79 %</span>
            <span style={{ ['--c' as string]: '#d32f2f' }}>≥80 %</span>
            <span style={{ ['--c' as string]: '#000' }}>dañado/bloqueado</span>
            <span style={{ ['--c' as string]: '#1565c0' }}>solicitud especial</span>
          </div>
        </div>
        <div>
          <IonCard>
            <IonCardHeader><IonCardTitle style={{ fontSize: 17 }}>Planificar ruta</IonCardTitle></IonCardHeader>
            <IonCardContent>
              <IonSelect label="Recolector" labelPlacement="stacked" value={plan.recolector_id} onIonChange={(e) => setPlan({ ...plan, recolector_id: e.detail.value })}>
                {recs.map((r) => <IonSelectOption key={r.id} value={r.id}>{r.nombre}</IonSelectOption>)}
              </IonSelect>
              <IonSelect label="Zonas (vacío = todas)" labelPlacement="stacked" multiple value={plan.barrios} onIonChange={(e) => setPlan({ ...plan, barrios: e.detail.value })}>
                {ZONAS.map((z) => <IonSelectOption key={z} value={z}>{z}</IonSelectOption>)}
              </IonSelect>
              <IonRange label={`Contenedores desde ${plan.umbral_llenado} %`} labelPlacement="stacked" min={30} max={100} step={5} value={plan.umbral_llenado}
                onIonChange={(e) => setPlan({ ...plan, umbral_llenado: e.detail.value as number })} />
              <IonNote>{candidatos} contenedores cumplen el criterio, más las solicitudes especiales pendientes.</IonNote>
              <IonButton expand="block" onClick={planificar}>Optimizar y asignar</IonButton>
            </IonCardContent>
          </IonCard>
          <IonCard>
            <IonCardHeader><IonCardTitle style={{ fontSize: 17 }}>Rutas activas</IonCardTitle></IonCardHeader>
            <IonList>
              {m?.rutas.map((r) => (
                <IonItem key={r.id}><IonLabel><h3>#{r.id} · {r.recolector}</h3><p>{r.hechas}/{r.paradas.length} paradas · {r.distancia_km} km · {r.estado}</p></IonLabel></IonItem>
              ))}
              {!m?.rutas.length && <IonItem><IonLabel>Sin rutas activas.</IonLabel></IonItem>}
            </IonList>
          </IonCard>
          <IonCard>
            <IonCardHeader><IonCardTitle style={{ fontSize: 17 }}>Incidentes</IonCardTitle></IonCardHeader>
            <IonList>
              {m?.incidentes.map((i) => (
                <IonItem key={i.id}>
                  <IonLabel className="ion-text-wrap"><h3>{i.tipo.replace('_', ' ')} {cont(i.contenedor_id)?.codigo}</h3><p>{i.descripcion} · {fecha(i.fecha)}</p></IonLabel>
                  <IonButton slot="end" size="small" onClick={() => resolver(i)}>Resuelto</IonButton>
                </IonItem>
              ))}
              {!m?.incidentes.length && <IonItem><IonLabel>Sin incidentes abiertos.</IonLabel></IonItem>}
            </IonList>
          </IonCard>
          <IonCard>
            <IonCardHeader><IonCardTitle style={{ fontSize: 17 }}>Campaña o evento de limpieza</IonCardTitle></IonCardHeader>
            <IonCardContent>
              <IonInput label="Título" labelPlacement="stacked" value={campania.titulo} onIonInput={(e) => setCampania({ ...campania, titulo: e.detail.value ?? '' })} />
              <IonTextarea label="Mensaje" labelPlacement="stacked" rows={2} value={campania.cuerpo} onIonInput={(e) => setCampania({ ...campania, cuerpo: e.detail.value ?? '' })} />
              <IonButton expand="block" disabled={!campania.titulo || !campania.cuerpo} onClick={enviarCampania}>Enviar a los vecinos</IonButton>
            </IonCardContent>
          </IonCard>
        </div>
      </div>
      <IonModal isOpen={qrs} onDidDismiss={() => setQrs(false)}>
        <Pagina titulo="QR de contenedores" acciones={<><IonButton onClick={() => window.print()}>Imprimir</IonButton><IonButton onClick={() => setQrs(false)}>Cerrar</IonButton></>}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, padding: 16 }}>
            {m?.contenedores.map((c) => (
              <div key={c.id} style={{ textAlign: 'center', width: 130 }}>
                <QRCodeSVG value={c.codigo} size={110} /><div><b>{c.codigo}</b></div><small>{c.barrio}</small>
              </div>
            ))}
          </div>
        </Pagina>
      </IonModal>
      <IonToast isOpen={!!msg} message={msg} duration={4500} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
