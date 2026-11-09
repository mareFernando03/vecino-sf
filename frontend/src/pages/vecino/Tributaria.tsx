import { IonBadge, IonButton, IonCard, IonCardContent, IonCardHeader, IonCardSubtitle, IonCardTitle, IonItem, IonLabel, IonList, IonListHeader, IonModal, IonRadio, IonRadioGroup, IonToast, useIonViewWillEnter } from '@ionic/react';
import { useState } from 'react';
import { api, fecha, pesos, post, token } from '../../api';
import { Pagina } from '../../components/Pagina';

type Cedulon = { id: number; tributo: string; partida: string; periodo: string; importe: number; vencimiento: string; estado: string; vencido: boolean; comprobante?: string; pagado_en?: string; medio?: string };

export default function Tributaria() {
  const [datos, setDatos] = useState<{ cedulones: Cedulon[]; deuda_total: number }>({ cedulones: [], deuda_total: 0 });
  const [pagando, setPagando] = useState<Cedulon | null>(null);
  const [medio, setMedio] = useState('tarjeta');
  const [msg, setMsg] = useState('');

  const cargar = () => api('/tributaria/cedulones').then(setDatos);
  useIonViewWillEnter(() => { cargar(); });

  // El cedulón se abre en otra pestaña para imprimirlo o guardarlo como PDF.
  async function emitir(c: Cedulon) {
    const r = await fetch(`/api/tributaria/cedulones/${c.id}/emitir`, { headers: { Authorization: `Bearer ${token()}` } });
    const url = URL.createObjectURL(new Blob([await r.text()], { type: 'text/html' }));
    window.open(url, '_blank');
  }

  async function pagar() {
    try {
      const r = await post<Cedulon>(`/tributaria/cedulones/${pagando!.id}/pagar`, { medio });
      setMsg(`Pago aprobado. Comprobante ${r.comprobante}`);
      setPagando(null);
      cargar();
    } catch (e) { setMsg((e as Error).message); }
  }

  const pendientes = datos.cedulones.filter((c) => c.estado === 'pendiente');
  const pagados = datos.cedulones.filter((c) => c.estado === 'pagado');

  return (
    <Pagina titulo="Tributaria" volver="/vecino">
      <IonCard>
        <IonCardHeader>
          <IonCardSubtitle>Deuda a la fecha</IonCardSubtitle>
          <IonCardTitle>{pesos(datos.deuda_total)}</IonCardTitle>
        </IonCardHeader>
        <IonCardContent>Recibís un aviso 3 días antes de cada vencimiento.</IonCardContent>
      </IonCard>
      <IonList>
        <IonListHeader>Obligaciones pendientes</IonListHeader>
        {pendientes.map((c) => (
          <IonItem key={c.id}>
            <IonLabel>
              <h3>{c.tributo} · {c.periodo}</h3>
              <p>Partida {c.partida} · vence {new Date(c.vencimiento + 'T00:00').toLocaleDateString('es-AR')}</p>
              <p><b>{pesos(c.importe)}</b> {c.vencido && <IonBadge color="danger">Vencido</IonBadge>}</p>
            </IonLabel>
            <IonButton slot="end" fill="outline" size="small" onClick={() => emitir(c)}>Cedulón</IonButton>
            <IonButton slot="end" size="small" onClick={() => setPagando(c)}>Pagar</IonButton>
          </IonItem>
        ))}
        <IonListHeader>Historial de pagos</IonListHeader>
        {pagados.map((c) => (
          <IonItem key={c.id}>
            <IonLabel>
              <h3>{c.tributo} · {c.periodo}</h3>
              <p>{pesos(c.importe)} · {c.medio} · comprobante {c.comprobante}{c.pagado_en && ` · ${fecha(c.pagado_en)}`}</p>
            </IonLabel>
          </IonItem>
        ))}
      </IonList>
      <IonModal isOpen={!!pagando} onDidDismiss={() => setPagando(null)} initialBreakpoint={0.6} breakpoints={[0, 0.6]}>
        <div className="ion-padding">
          <h3>Pagar {pagando?.tributo}</h3>
          <p>{pagando && pesos(pagando.importe)} · período {pagando?.periodo}</p>
          <IonRadioGroup value={medio} onIonChange={(e) => setMedio(e.detail.value)}>
            <IonItem><IonRadio value="tarjeta">Tarjeta de crédito</IonRadio></IonItem>
            <IonItem><IonRadio value="debito">Tarjeta de débito</IonRadio></IonItem>
            <IonItem><IonRadio value="transferencia">Transferencia</IonRadio></IonItem>
          </IonRadioGroup>
          <p><small>Pasarela simulada: en producción se redirige al checkout seguro de la pasarela de pagos.</small></p>
          <IonButton expand="block" onClick={pagar}>Confirmar pago</IonButton>
        </div>
      </IonModal>
      <IonToast isOpen={!!msg} message={msg} duration={3500} onDidDismiss={() => setMsg('')} />
    </Pagina>
  );
}
