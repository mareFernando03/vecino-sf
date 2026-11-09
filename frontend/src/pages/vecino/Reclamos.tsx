import { IonBadge, IonButton, IonInput, IonItem, IonLabel, IonList, IonListHeader, IonModal, IonNote, IonSearchbar, IonSelect, IonSelectOption, IonTextarea, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, fecha, post } from '../../api';
import { Mapa, Punto } from '../../components/Mapa';
import { Pagina } from '../../components/Pagina';

type Reclamo = { id: number; categoria: string; descripcion: string; direccion: string; estado: string; creado: string; lat?: number; lng?: number;
  adjuntos: { nombre: string; url: string }[]; eventos: { estado: string; nota: string; fecha: string }[] };

const COLOR: Record<string, string> = { recibido: 'medium', en_curso: 'warning', resuelto: 'success' };
const Estado = ({ e }: { e: string }) => <IonBadge color={COLOR[e]}>{e.replace('_', ' ')}</IonBadge>;

export function Reclamos() {
  const [lista, setLista] = useState<Reclamo[]>([]);
  const [q, setQ] = useState('');
  const [nuevo, setNuevo] = useState(false);
  const [cats, setCats] = useState<string[]>([]);
  const [form, setForm] = useState({ categoria: '', descripcion: '', direccion: '' });
  const [pos, setPos] = useState<[number, number] | null>(null);
  const [fotos, setFotos] = useState<FileList | null>(null);
  const [msg, setMsg] = useState('');

  const cargar = (texto = q) => api<Reclamo[]>(`/reclamos${texto ? `?q=${encodeURIComponent(texto)}` : ''}`).then(setLista);
  useIonViewWillEnter(() => { cargar(); api('/reclamos/categorias').then(setCats); });

  async function enviar() {
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    if (pos) { fd.append('lat', String(pos[0])); fd.append('lng', String(pos[1])); }
    Array.from(fotos ?? []).forEach((f) => fd.append('archivos', f));
    try {
      const r = await post<Reclamo>('/reclamos', fd);
      setMsg(`Reclamo #${r.id} registrado`);
      setNuevo(false); setForm({ categoria: '', descripcion: '', direccion: '' }); setFotos(null); setPos(null);
      cargar();
    } catch (e) { setMsg((e as Error).message); }
  }

  return (
    <Pagina titulo="Centro de reclamos" volver="/vecino">
      <IonButton expand="block" className="ion-margin" onClick={() => setNuevo(true)}>Nuevo reclamo</IonButton>
      <IonSearchbar placeholder="Buscar en mis reclamos" value={q} debounce={300} onIonInput={(e) => { setQ(e.detail.value ?? ''); cargar(e.detail.value ?? ''); }} />
      <IonList>
        {lista.map((r) => (
          <IonItem key={r.id} routerLink={`/vecino/reclamos/${r.id}`} detail>
            <IonLabel>
              <h3>#{r.id} · {r.categoria}</h3>
              <p>{r.descripcion}</p>
              <p>{fecha(r.creado)} · {r.direccion}</p>
            </IonLabel>
            <Estado e={r.estado} />
          </IonItem>
        ))}
        {!lista.length && <IonItem><IonLabel>No hay reclamos.</IonLabel></IonItem>}
      </IonList>
      <IonModal isOpen={nuevo} onDidDismiss={() => setNuevo(false)}>
        <Pagina titulo="Nuevo reclamo" acciones={<IonButton onClick={() => setNuevo(false)}>Cerrar</IonButton>}>
          <IonList>
            <IonItem>
              <IonSelect label="Categoría" labelPlacement="stacked" value={form.categoria} onIonChange={(e) => setForm({ ...form, categoria: e.detail.value })}>
                {cats.map((c) => <IonSelectOption key={c} value={c}>{c}</IonSelectOption>)}
              </IonSelect>
            </IonItem>
            <IonItem><IonTextarea label="Descripción" labelPlacement="stacked" rows={3} value={form.descripcion} onIonInput={(e) => setForm({ ...form, descripcion: e.detail.value ?? '' })} /></IonItem>
            <IonItem><IonInput label="Dirección o referencia" labelPlacement="stacked" value={form.direccion} onIonInput={(e) => setForm({ ...form, direccion: e.detail.value ?? '' })} /></IonItem>
            <IonItem lines="none"><IonNote>Tocá el mapa para marcar el lugar exacto (opcional).</IonNote></IonItem>
          </IonList>
          <Mapa alto="28vh" onClick={(lat, lng) => setPos([lat, lng])}>{pos && <Punto pos={pos} color="#1565c0" />}</Mapa>
          <IonItem>
            <IonLabel position="stacked">Fotos o documentos (hasta 4)</IonLabel>
            <input type="file" accept="image/*,application/pdf" capture="environment" multiple onChange={(e) => setFotos(e.target.files)} />
          </IonItem>
          <IonButton expand="block" className="ion-margin" onClick={enviar}
            disabled={!form.categoria || form.descripcion.trim().length < 10 || !form.direccion.trim()}>Enviar reclamo</IonButton>
        </Pagina>
      </IonModal>
      <IonToast isOpen={!!msg} message={msg} duration={3000} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}

export function DetalleReclamo() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Reclamo | null>(null);
  useIonViewWillEnter(() => { api<Reclamo>(`/reclamos/${id}`).then(setR); });
  if (!r) return <Pagina titulo="Reclamo" volver="/vecino/reclamos"><p className="ion-padding">Cargando…</p></Pagina>;
  return (
    <Pagina titulo={`Reclamo #${r.id}`} volver="/vecino/reclamos">
      <div className="ion-padding">
        <h2>{r.categoria} <Estado e={r.estado} /></h2>
        <p>{r.descripcion}</p>
        <IonNote>{r.direccion} · {fecha(r.creado)}</IonNote>
        {r.adjuntos.map((a) => (
          <p key={a.url}><a href={a.url} target="_blank" rel="noreferrer">{a.nombre}</a></p>
        ))}
      </div>
      {r.lat != null && r.lng != null && <Mapa centro={[r.lat, r.lng]} zoom={16} alto="25vh"><Punto pos={[r.lat, r.lng]} color="#1565c0" /></Mapa>}
      <IonList>
        <IonListHeader>Seguimiento</IonListHeader>
        {r.eventos.map((e, i) => (
          <IonItem key={i}><IonLabel><h3><Estado e={e.estado} /> {fecha(e.fecha)}</h3><p>{e.nota}</p></IonLabel></IonItem>
        ))}
      </IonList>
    </Pagina>
  );
}
