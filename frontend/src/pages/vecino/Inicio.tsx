import { IonBadge, IonCard, IonIcon, IonToast } from '@ionic/react';
import { bicycleOutline, callOutline, carOutline, chatbubblesOutline, leafOutline, megaphoneOutline, notificationsOutline, receiptOutline } from 'ionicons/icons';
import { useState } from 'react';
import { useEventos } from '../../api';
import { Pagina } from '../../components/Pagina';
import { mostrarLocal } from '../../push';
import { useSesion } from '../../sesion';

const SERVICIOS = [
  { ruta: 'bicis', titulo: 'Bicicletas públicas', icono: bicycleOutline },
  { ruta: 'tributaria', titulo: 'Tributaria y pagos', icono: receiptOutline },
  { ruta: 'reclamos', titulo: 'Centro de reclamos', icono: chatbubblesOutline },
  { ruta: 'contactos', titulo: 'Líneas de atención', icono: callOutline },
  { ruta: 'alarmas', titulo: 'Alarmas comunitarias', icono: megaphoneOutline },
  { ruta: 'estacionamiento', titulo: 'Estacionamiento medido', icono: carOutline },
  { ruta: 'notificaciones', titulo: 'Notificaciones', icono: notificationsOutline },
  { ruta: 'residuos', titulo: 'Residuos y reciclaje', icono: leafOutline },
];

export default function Inicio() {
  const { usuario } = useSesion();
  const [nuevos, setNuevos] = useState(0);
  const [aviso, setAviso] = useState('');

  // Avisos en vivo: el servidor sólo manda los de este vecino y los de toda la ciudad.
  useEventos((e) => {
    if (e.tipo !== 'notificacion') return;
    const d = e.datos;
    setNuevos((n) => n + 1);
    setAviso(d.titulo);
    mostrarLocal(d.titulo, d.cuerpo);
  });

  return (
    <Pagina titulo="Vecino SF">
      <p className="ion-padding-horizontal">Hola, {usuario?.nombre.split(' ')[0]}. ¿Qué necesitás hoy?</p>
      <div className="grilla-servicios">
        {SERVICIOS.map((s) => (
          <IonCard key={s.ruta} button routerLink={`/vecino/${s.ruta}`}>
            <IonIcon icon={s.icono} />
            <h3>{s.titulo}</h3>
            {s.ruta === 'notificaciones' && nuevos > 0 && <IonBadge color="danger">{nuevos}</IonBadge>}
          </IonCard>
        ))}
      </div>
      <IonToast isOpen={!!aviso} message={aviso} duration={4000} onDidDismiss={() => setAviso('')} position="top" />
    </Pagina>
  );
}
