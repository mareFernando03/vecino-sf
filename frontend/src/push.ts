// Notificaciones push web: registra el service worker y suscribe el navegador con la clave
// VAPID del servidor. En la app empaquetada con Capacitor se usaría FCM nativo.
import { api, post } from './api';

function aBytes(b64: string) {
  const relleno = '='.repeat((4 - (b64.length % 4)) % 4);
  const s = atob((b64 + relleno).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...s].map((c) => c.charCodeAt(0)));
}

export async function registrarSW() {
  if ('serviceWorker' in navigator) return navigator.serviceWorker.register('/sw.js');
}

export function pushDisponible() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

export async function activarPush(): Promise<string> {
  if (!pushDisponible()) return 'Este navegador no admite notificaciones push.';
  const permiso = await Notification.requestPermission();
  if (permiso !== 'granted') return 'No diste permiso para notificaciones.';
  const reg = await navigator.serviceWorker.ready;
  const { clave } = await api<{ clave: string }>('/push/clave-publica');
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: aBytes(clave) });
  await post('/push/suscribir', sub.toJSON());
  return 'Notificaciones activadas.';
}

// Con la app abierta, el aviso llega por SSE y se muestra igual que un push.
export async function mostrarLocal(titulo: string, cuerpo: string) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const reg = await navigator.serviceWorker?.ready;
  reg?.showNotification(titulo, { body: cuerpo, icon: '/icono-192.png' });
}
