// Tiempo de carga en un celular de gama media simulado (CPU 4x más lenta, red 4G de 9 Mbps
// y 170 ms de latencia). Mide la primera visita y la segunda (con la caché del service worker).
//   CDP=http://127.0.0.1:9333 node pruebas/rendimiento.mjs
import { chromium } from 'playwright-core';

const BASE = process.env.BASE ?? 'http://localhost:4173';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const nav = process.env.CDP
  ? await chromium.connectOverCDP(process.env.CDP)
  : await chromium.launch({ executablePath: EDGE, headless: false, args: ['--headless=new'] });

async function medir(page) {
  const t0 = Date.now();
  await page.goto(BASE, { waitUntil: 'load' });
  await page.getByText('Ingresar').first().waitFor();
  const visible = Date.now() - t0;
  const nt = await page.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0];
    const fcp = performance.getEntriesByName('first-contentful-paint')[0];
    const bytes = performance.getEntriesByType('resource').reduce((s, r) => s + (r.transferSize || 0), n.transferSize || 0);
    return { load: Math.round(n.loadEventEnd), fcp: Math.round(fcp?.startTime ?? 0), kb: Math.round(bytes / 1024) };
  });
  return { ...nt, visible };
}

const ctx = await nav.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Network.enable');
await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 170, downloadThroughput: 9e6 / 8, uploadThroughput: 1.5e6 / 8 });
await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });

const primera = await medir(page);
await page.waitForTimeout(1500);           // el service worker termina de instalarse
const segunda = await medir(page);
console.log(`primera visita : primer contenido ${primera.fcp} ms · pantalla de ingreso lista ${primera.visible} ms · ${primera.kb} KB transferidos`);
console.log(`segunda visita : primer contenido ${segunda.fcp} ms · pantalla de ingreso lista ${segunda.visible} ms · ${segunda.kb} KB transferidos`);
await ctx.close();
await nav.close();
