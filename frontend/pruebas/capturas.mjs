// Recorrido de punta a punta por las tres aplicaciones, con capturas para los informes.
// Es también la prueba funcional de la interfaz: si un paso no encuentra lo que espera, falla.
//
//   (backend en :8000 y `npx vite preview` en :4173)
//   node pruebas/capturas.mjs
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE ?? 'http://localhost:4173';
const SALIDA = process.env.SALIDA ?? '../docs/capturas';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
mkdirSync(SALIDA, { recursive: true });

// Con CDP=http://127.0.0.1:9333 se conecta a un Edge ya abierto con --remote-debugging-port
// (en algunas máquinas Edge no arranca por el canal que usa launch()).
const navegador = process.env.CDP
  ? await chromium.connectOverCDP(process.env.CDP)
  : await chromium.launch({ executablePath: EDGE, headless: false, args: ['--headless=new'] });
const log = (...a) => console.log('·', ...a);
const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

async function contexto(movil = true) {
  return navegador.newContext({
    viewport: movil ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    deviceScaleFactor: movil ? 2 : 1,
    isMobile: movil, hasTouch: movil,
    geolocation: { latitude: -31.4170, longitude: -62.0850 },   // un vecino en la zona Norte
    permissions: ['geolocation', 'notifications'],
    locale: 'es-AR', timezoneId: 'America/Argentina/Cordoba',
  });
}

async function foto(page, nombre, esperar = 900) {
  await pausa(esperar);                 // teselas del mapa y animaciones de Ionic
  await page.screenshot({ path: `${SALIDA}/${nombre}.png` });
  log(nombre);
}

async function ingresar(page, rol) {
  await page.goto(BASE);
  await page.getByRole('button', { name: rol }).click();
  await page.locator('ion-button[type=submit]').click();
  await page.waitForURL(/\/(vecino|autoridad|recolector)/);
}

async function api(page, ruta, opciones = {}, token = null) {
  return page.evaluate(async ([ruta, opciones, token]) => {
    const r = await fetch(`/api${ruta}`, { ...opciones, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token ?? localStorage.getItem('token')}` } });
    if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
    return r.json();
  }, [ruta, opciones, token]);
}

// Token de la central (rol autoridad), para los pasos que un vecino no puede hacer.
const tokenCentral = (page) => api(page, '/auth/login', { method: 'POST', body: JSON.stringify({ usuario: 'autoridad', clave: 'autoridad123' }) }).then((r) => r.token);

const visible = (page, texto) => page.locator('.ion-page:not(.ion-page-hidden)').getByText(texto).first().waitFor();

// ─── Vecino ──────────────────────────────────────────────────────────────────
{
  const ctx = await contexto();
  const page = await ctx.newPage();
  await page.goto(BASE);
  await foto(page, '01-login', 300);
  await ingresar(page, 'Vecino');
  await visible(page, 'Bicicletas públicas');
  await foto(page, '02-inicio');

  // Push: suscripción real del navegador contra el servicio de push del fabricante.
  const push = await page.evaluate(async () => {
    try {
      const reg = await navigator.serviceWorker.ready;
      const { clave } = await (await fetch('/api/push/clave-publica')).json();
      const b = Uint8Array.from(atob(clave.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - clave.length % 4) % 4)), (c) => c.charCodeAt(0));
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b });
      return new URL(sub.endpoint).host;
    } catch (e) { return `sin push: ${e.message}`; }
  });
  log('push:', push);

  await page.goto(`${BASE}/vecino/bicis`);
  await visible(page, 'Estaciones cerca mío');
  await page.getByText('Estaciones cerca mío').click();
  await visible(page, 'a 0.');
  await foto(page, '03-bicis', 1800);

  await page.goto(`${BASE}/vecino/tributaria`);
  await visible(page, 'Deuda a la fecha');
  await foto(page, '04-tributaria');
  await page.locator('ion-item').filter({ hasText: 'Tasa a la propiedad' }).getByText('Pagar').first().click();
  await visible(page, 'Confirmar pago');
  await foto(page, '05-tributaria-pago', 700);
  await page.getByText('Confirmar pago').click();
  await visible(page, 'Pago aprobado');
  await foto(page, '06-tributaria-pagado', 400);
  const cuenta = await api(page, '/tributaria/cedulones');
  const ced = cuenta.cedulones.find((c) => c.estado === 'pendiente');
  const html = await page.evaluate(async (id) => (await fetch(`/api/tributaria/cedulones/${id}/emitir`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })).text(), ced.id);
  const p2 = await ctx.newPage();
  await p2.setContent(html.replace(/<script>.*<\/script>/, ''));
  await foto(p2, '07-cedulon', 200);
  await p2.close();

  await page.goto(`${BASE}/vecino/reclamos`);
  await visible(page, 'Nuevo reclamo');
  await page.getByText('Nuevo reclamo').first().click();
  await visible(page, 'Enviar reclamo');
  const modal = page.locator('ion-modal');
  await modal.locator('ion-select').click();
  await page.locator('ion-alert button, ion-popover ion-item, ion-action-sheet button').filter({ hasText: 'Bache o calle' }).first().click();
  const ok = page.locator('ion-alert button').filter({ hasText: /OK|Aceptar/i });
  if (await ok.count()) await ok.first().click();
  await modal.locator('ion-textarea textarea').fill('Pozo profundo en la calzada, frente a la escuela. Peligroso de noche.');
  await modal.locator('ion-input input').fill('Frente a la escuela del barrio');
  await modal.locator('.leaflet-container').click({ position: { x: 190, y: 110 } });
  await modal.locator('input[type=file]').setInputFiles({ name: 'pozo.png', mimeType: 'image/png', buffer: Buffer.from('89504e470d0a1a0a0000000d4948445200000001000000010806000000', 'hex') });
  await foto(page, '08-reclamo-nuevo', 1500);
  await modal.getByText('Enviar reclamo').click();
  await visible(page, 'registrado');
  await foto(page, '09-reclamos', 600);
  const mios = await api(page, '/reclamos');
  await page.goto(`${BASE}/vecino/reclamos/${mios[1].id}`);
  await visible(page, 'Seguimiento');
  await foto(page, '10-reclamo-detalle', 1500);

  await page.goto(`${BASE}/vecino/contactos`);
  await visible(page, 'Guardia urbana');
  await foto(page, '11-contactos');

  await page.goto(`${BASE}/vecino/alarmas`);
  await visible(page, 'Recibir alertas');
  const alarmas = await api(page, '/alarmas');
  const norte = alarmas.find((a) => a.barrio === 'Norte');
  const central = await tokenCentral(page);            // la alarma la activa la central, no el vecino
  await api(page, `/alarmas/${norte.id}`, { method: 'PATCH', body: JSON.stringify({ activa: true }) }, central);
  await visible(page, 'activadas');
  await foto(page, '12-alarmas', 1500);
  await api(page, `/alarmas/${norte.id}`, { method: 'PATCH', body: JSON.stringify({ activa: false }) }, central);

  await page.goto(`${BASE}/vecino/estacionamiento`);
  await visible(page, 'Pagar e iniciar');
  await page.locator('ion-input input').fill('AB123CD');
  await foto(page, '13-estacionamiento', 1200);
  await page.getByText('Pagar e iniciar').click();
  await visible(page, 'Extender 30 minutos');
  await visible(page, 'pasarela simulada');
  await foto(page, '14-estacionamiento-activo', 1500);

  await page.goto(`${BASE}/vecino/notificaciones`);
  await visible(page, 'Historial');
  await foto(page, '15-notificaciones');
  await page.getByText('Preferencias').click();
  await visible(page, 'Zonas de interés');
  await foto(page, '16-preferencias');

  await page.goto(`${BASE}/vecino/residuos`);
  await visible(page, 'Tus últimos 30 días');
  await page.locator('ion-input input').fill('4');
  await page.getByText('Registrar', { exact: true }).last().click();
  await visible(page, 'Gracias por separar');
  await foto(page, '17-residuos-registro', 600);
  await page.getByText('Retiro especial').click();
  await visible(page, 'Solicitar retiro');
  await page.locator('ion-textarea textarea').fill('Sillón de tres cuerpos y un colchón');
  await page.locator('ion-input input').last().fill('Domicilio del vecino');
  await page.getByText('usar mi ubicación').click();
  await pausa(600);
  await foto(page, '18-residuos-solicitud', 1200);
  await page.getByText('Solicitar retiro').click();
  await visible(page, 'Te avisamos');
  await page.getByText('Puntos y horarios').click();
  await visible(page, 'Horarios de recolección');
  await foto(page, '19-residuos-puntos', 1500);
  await ctx.close();
}

// ─── Autoridad ───────────────────────────────────────────────────────────────
{
  const ctx = await contexto(false);
  const page = await ctx.newPage();
  await ingresar(page, 'Autoridad');
  await visible(page, 'Planificar ruta');
  await foto(page, '20-autoridad-panel', 2500);
  await page.getByText('Optimizar y asignar').click();
  await visible(page, 'asignada a');
  await foto(page, '21-autoridad-ruta', 3000);
  await page.getByRole('button', { name: 'QR' }).click();
  await visible(page, 'SF-C-001');
  await foto(page, '22-autoridad-qr', 600);
  await ctx.close();
}

// ─── Recolector ──────────────────────────────────────────────────────────────
{
  const ctx = await contexto();
  const page = await ctx.newPage();
  await ingresar(page, 'Recolector');
  await visible(page, 'Paradas en orden');
  await foto(page, '23-recolector-ruta', 2500);
  const ruta = await api(page, '/residuos/mi-ruta');
  for (const p of ruta.paradas.slice(0, 2)) {
    await page.locator('ion-input input').fill(p.codigo);
    await page.getByText('Registrar', { exact: true }).click();
    await visible(page, 'registrado');
    await pausa(500);
  }
  await foto(page, '24-recolector-escaneo', 1200);
  await page.getByText('Reportar incidente').click();
  await visible(page, 'Enviar');
  await page.locator('ion-modal ion-textarea textarea').fill('Tapa rota, no cierra');
  await foto(page, '25-recolector-incidente', 700);
  await page.locator('ion-modal').getByText('Enviar').click();
  await visible(page, 'reportado');
  await ctx.close();
}

await navegador.close();
log('listo');
