// Cliente de la API: agrega el token y convierte los errores en mensajes legibles.
import { useEffect, useRef } from 'react';

export type Usuario = { id: number; usuario: string; nombre: string; rol: 'vecino' | 'autoridad' | 'recolector'; barrio?: string };

export function token(): string | null {
  return localStorage.getItem('token');
}

export async function api<T = any>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const headers = new Headers(opciones.headers);
  const t = token();
  if (t) headers.set('Authorization', `Bearer ${t}`);
  if (opciones.body && !(opciones.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const r = await fetch(`/api${ruta}`, { ...opciones, headers });
  if (r.status === 401 && t) {
    localStorage.removeItem('token');
    window.location.href = '/';
  }
  if (!r.ok) {
    let msg = `Error ${r.status}`;
    try {
      const d = await r.json();
      msg = typeof d.detail === 'string' ? d.detail : 'Revisá los datos ingresados';
    } catch { /* sin cuerpo */ }
    throw new Error(msg);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

export const post = <T = any>(ruta: string, cuerpo: unknown) =>
  api<T>(ruta, { method: 'POST', body: cuerpo instanceof FormData ? cuerpo : JSON.stringify(cuerpo) });
export const patch = <T = any>(ruta: string, cuerpo: unknown) => api<T>(ruta, { method: 'PATCH', body: JSON.stringify(cuerpo) });
export const put = <T = any>(ruta: string, cuerpo: unknown) => api<T>(ruta, { method: 'PUT', body: JSON.stringify(cuerpo) });

export type Evento = { tipo: string; datos: any };

// Tiempo real: una conexión SSE por pantalla abierta. EventSource se reconecta solo.
export function useEventos(alRecibir: (e: Evento) => void) {
  const cb = useRef(alRecibir);
  cb.current = alRecibir;
  useEffect(() => {
    const t = token();
    if (!t) return;
    // EventSource no permite encabezados: el token va en la URL y el servidor filtra por usuario.
    const es = new EventSource(`/api/eventos?token=${encodeURIComponent(t)}`);
    es.onmessage = (m) => cb.current(JSON.parse(m.data));
    return () => es.close();
  }, []);
}

export const pesos = (n: number) => n.toLocaleString('es-AR', { style: 'currency', currency: 'ARS' });
export const fecha = (s: string) => new Date(s).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' });

export function distanciaKm(a: [number, number], b: [number, number]) {
  const r = (x: number) => (x * Math.PI) / 180;
  const h = Math.sin(r(b[0] - a[0]) / 2) ** 2 + Math.cos(r(a[0])) * Math.cos(r(b[0])) * Math.sin(r(b[1] - a[1]) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

export const CENTRO: [number, number] = [-31.4283, -62.0833];
