# Etapa 1: compila la app web (Ionic + React) a archivos estáticos.
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npx vite build

# Etapa 2: nginx sirve los estáticos y reenvía /api al backend (mismo origen, sin CORS).
FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
