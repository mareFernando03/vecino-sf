// Una sola aplicación web, tres experiencias según el rol del usuario que ingresa.
import { IonApp, IonRouterOutlet, IonSpinner } from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import { lazy, Suspense } from 'react';
import { Redirect, Route } from 'react-router-dom';
import Login from './pages/Login';
import { ProveedorSesion, useSesion } from './sesion';

// Cada pantalla se descarga recién cuando se abre: el vecino no baja el código del panel de
// la autoridad ni el lector de QR, y la primera carga es más liviana.
const PanelAutoridad = lazy(() => import('./pages/autoridad/Panel'));
const RutaRecolector = lazy(() => import('./pages/recolector/Ruta'));
const Alarmas = lazy(() => import('./pages/vecino/Alarmas'));
const Bicis = lazy(() => import('./pages/vecino/Bicis'));
const Contactos = lazy(() => import('./pages/vecino/Contactos'));
const Estacionamiento = lazy(() => import('./pages/vecino/Estacionamiento'));
const Inicio = lazy(() => import('./pages/vecino/Inicio'));
const Notificaciones = lazy(() => import('./pages/vecino/Notificaciones'));
const Reclamos = lazy(() => import('./pages/vecino/Reclamos').then((m) => ({ default: m.Reclamos })));
const DetalleReclamo = lazy(() => import('./pages/vecino/Reclamos').then((m) => ({ default: m.DetalleReclamo })));
const Residuos = lazy(() => import('./pages/vecino/Residuos'));
const Tributaria = lazy(() => import('./pages/vecino/Tributaria'));

const INICIO = { vecino: '/vecino', autoridad: '/autoridad', recolector: '/recolector' };

// IonRouterOutlet necesita <Route> como hijos directos (sin fragmentos ni condicionales),
// así que cada rol tiene su lista de rutas.
const RUTAS: Record<string, [string, React.ComponentType][]> = {
  vecino: [
    ['/vecino', Inicio], ['/vecino/bicis', Bicis], ['/vecino/tributaria', Tributaria],
    ['/vecino/reclamos', Reclamos], ['/vecino/reclamos/:id', DetalleReclamo], ['/vecino/contactos', Contactos],
    ['/vecino/alarmas', Alarmas], ['/vecino/estacionamiento', Estacionamiento],
    ['/vecino/notificaciones', Notificaciones], ['/vecino/residuos', Residuos],
  ],
  autoridad: [['/autoridad', PanelAutoridad]],
  recolector: [['/recolector', RutaRecolector]],
};

function Rutas() {
  const { usuario, cargando } = useSesion();
  if (cargando) return <IonSpinner style={{ margin: '40vh auto', display: 'block' }} />;
  if (!usuario) return <Login />;
  const rol = usuario.rol;
  return (
    <Suspense fallback={<IonSpinner style={{ margin: '40vh auto', display: 'block' }} />}>
      <IonRouterOutlet>
        {RUTAS[rol].map(([ruta, Pantalla]) => <Route key={ruta} exact path={ruta} component={Pantalla} />)}
        <Route render={() => <Redirect to={INICIO[rol]} />} />
      </IonRouterOutlet>
    </Suspense>
  );
}

export default function App() {
  return (
    <IonApp>
      <ProveedorSesion>
        <IonReactRouter>
          <Rutas />
        </IonReactRouter>
      </ProveedorSesion>
    </IonApp>
  );
}
