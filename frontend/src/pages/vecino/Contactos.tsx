import { IonButton, IonCard, IonCardContent, IonCardHeader, IonCardSubtitle, IonCardTitle, IonIcon, useIonViewWillEnter } from '@ionic/react';
import { callOutline, logoWhatsapp, mailOutline } from 'ionicons/icons';
import { useState } from 'react';
import { api } from '../../api';
import { Pagina } from '../../components/Pagina';

type Contacto = { area: string; telefono: string; email: string; whatsapp: string; horario: string };

// Llamar, escribir un mail o abrir WhatsApp: el sistema operativo resuelve cada enlace con
// la app correspondiente, igual en Android, iOS o escritorio.
export default function Contactos() {
  const [lista, setLista] = useState<Contacto[]>([]);
  useIonViewWillEnter(() => { api('/contactos').then(setLista); });
  return (
    <Pagina titulo="Líneas de atención" volver="/vecino">
      {lista.map((c) => (
        <IonCard key={c.area}>
          <IonCardHeader>
            <IonCardTitle style={{ fontSize: 18 }}>{c.area}</IonCardTitle>
            <IonCardSubtitle>{c.horario}</IonCardSubtitle>
          </IonCardHeader>
          <IonCardContent>
            <IonButton size="small" href={`tel:${c.telefono}`}><IonIcon slot="start" icon={callOutline} />Llamar</IonButton>
            <IonButton size="small" fill="outline" href={`mailto:${c.email}`}><IonIcon slot="start" icon={mailOutline} />Mail</IonButton>
            <IonButton size="small" fill="outline" color="success" href={`https://wa.me/${c.whatsapp}`} target="_blank"><IonIcon slot="start" icon={logoWhatsapp} />WhatsApp</IonButton>
          </IonCardContent>
        </IonCard>
      ))}
      <p className="ion-padding" style={{ fontSize: 12 }}>Números y casillas de ejemplo (prototipo).</p>
    </Pagina>
  );
}
