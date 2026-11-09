import { createContext, ReactNode, useContext, useEffect, useState } from 'react';
import { api, post, Usuario } from './api';

type Sesion = { usuario: Usuario | null; cargando: boolean; ingresar: (u: string, c: string) => Promise<Usuario>; salir: () => void };
const Ctx = createContext<Sesion>(null as unknown as Sesion);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem('token')) { setCargando(false); return; }
    api<Usuario>('/auth/yo').then(setUsuario).catch(() => localStorage.removeItem('token')).finally(() => setCargando(false));
  }, []);

  async function ingresar(u: string, c: string) {
    const r = await post<{ token: string; usuario: Usuario }>('/auth/login', { usuario: u, clave: c });
    localStorage.setItem('token', r.token);
    setUsuario(r.usuario);
    return r.usuario;
  }

  function salir() {
    localStorage.removeItem('token');
    setUsuario(null);
    window.location.href = '/';
  }

  return <Ctx.Provider value={{ usuario, cargando, ingresar, salir }}>{children}</Ctx.Provider>;
}

export const useSesion = () => useContext(Ctx);
