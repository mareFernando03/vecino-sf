import { IonButton, IonCard, IonCardContent, IonContent, IonInput, IonItem, IonNote, IonPage, IonText } from '@ionic/react';
import { FormEvent, useState } from 'react';
import { useSesion } from '../sesion';

const DEMO = [
  ['Vecino', '30111222', 'vecino123'],
  ['Autoridad', 'autoridad', 'autoridad123'],
  ['Recolector', 'recolector1', 'recolector123'],
];

export default function Login() {
  const { ingresar } = useSesion();
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState('');

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await ingresar(usuario, clave);
      window.history.replaceState(null, '', '/');
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <IonPage>
      <IonContent className="ion-padding">
        <div style={{ maxWidth: 420, margin: '6vh auto 0', textAlign: 'center' }}>
          <img src="/icono.svg" alt="" width={72} />
          <h1 style={{ margin: '8px 0 0' }}>Vecino SF</h1>
          <p>Los servicios de la Municipalidad de San Francisco en el celular.</p>
          <form onSubmit={enviar}>
            <IonItem><IonInput label="DNI o usuario" labelPlacement="stacked" value={usuario} onIonInput={(e) => setUsuario(e.detail.value ?? '')} autocomplete="username" /></IonItem>
            <IonItem><IonInput label="Clave" labelPlacement="stacked" type="password" value={clave} onIonInput={(e) => setClave(e.detail.value ?? '')} autocomplete="current-password" /></IonItem>
            {error && <IonText color="danger"><p role="alert">{error}</p></IonText>}
            <IonButton expand="block" type="submit" className="ion-margin-top">Ingresar</IonButton>
          </form>
          <IonCard>
            <IonCardContent>
              <IonNote>Prototipo con datos simulados. Usuarios de prueba:</IonNote>
              {DEMO.map(([rol, u, c]) => (
                <IonButton key={u} size="small" fill="outline" onClick={() => { setUsuario(u); setClave(c); }}>{rol}</IonButton>
              ))}
            </IonCardContent>
          </IonCard>
        </div>
      </IonContent>
    </IonPage>
  );
}
