import type { CapacitorConfig } from '@capacitor/cli';

// La misma web empaquetada como app Android/iOS: `npx cap add android` y `npx cap sync`.
const config: CapacitorConfig = {
  appId: 'ar.vecinosf.app',
  appName: 'Vecino SF',
  webDir: 'dist',
  server: { androidScheme: 'https' },
};
export default config;
