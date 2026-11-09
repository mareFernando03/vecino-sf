import { IonBackButton, IonButton, IonButtons, IonContent, IonHeader, IonIcon, IonPage, IonTitle, IonToolbar } from '@ionic/react';
import { logOutOutline } from 'ionicons/icons';
import { ReactNode } from 'react';
import { useSesion } from '../sesion';

export function Pagina({ titulo, volver, children, acciones }: { titulo: string; volver?: string; children: ReactNode; acciones?: ReactNode }) {
  const { salir } = useSesion();
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="primary">
          {volver && <IonButtons slot="start"><IonBackButton defaultHref={volver} text="" /></IonButtons>}
          <IonTitle>{titulo}</IonTitle>
          <IonButtons slot="end">
            {acciones}
            <IonButton onClick={salir} aria-label="Cerrar sesión"><IonIcon icon={logOutOutline} /></IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent>{children}</IonContent>
    </IonPage>
  );
}
