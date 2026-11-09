import { setupIonicReact } from '@ionic/react';
import '@ionic/react/css/core.css';
import '@ionic/react/css/normalize.css';
import '@ionic/react/css/structure.css';
import '@ionic/react/css/typography.css';
import '@ionic/react/css/padding.css';
import '@ionic/react/css/flex-utils.css';
import '@ionic/react/css/display.css';
import { createRoot } from 'react-dom/client';
import App from './App';
import { registrarSW } from './push';
import './tema.css';

setupIonicReact({ mode: 'md' });
registrarSW();
createRoot(document.getElementById('root')!).render(<App />);
