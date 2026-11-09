// Capturas de Grafana y Prometheus mientras corre una prueba de carga (docker compose arriba).
//   CDP=http://127.0.0.1:9333 node pruebas/capturas-monitoreo.mjs
import { chromium } from 'playwright-core';

const SALIDA = process.env.SALIDA ?? '../docs/capturas';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const nav = process.env.CDP
  ? await chromium.connectOverCDP(process.env.CDP)
  : await chromium.launch({ executablePath: EDGE, headless: false, args: ['--headless=new'] });
const ctx = await nav.newContext({ viewport: { width: 1440, height: 820 } });
const page = await ctx.newPage();

await page.goto('http://localhost:9090/targets');
await page.getByText(/UP/).first().waitFor();
await new Promise((r) => setTimeout(r, 1500));
await page.screenshot({ path: `${SALIDA}/26-prometheus-targets.png` });

await page.goto(`http://localhost:3000/d/vecino-api?orgId=1&kiosk&refresh=5s&from=${process.env.DESDE ?? 'now-5m'}&to=now`);
await page.getByText('Pedidos por segundo').first().waitFor({ timeout: 30000 });
await new Promise((r) => setTimeout(r, 8000));
await page.screenshot({ path: `${SALIDA}/27-grafana.png` });
await ctx.close();
await nav.close();
console.log('listo');
