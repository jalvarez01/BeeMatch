# Imagen de producción del frontend: compila con Vite y sirve el resultado con
# Caddy, que además hace de proxy hacia la API y gestiona el HTTPS.
# Se construye desde la raíz del repositorio (ver docker-compose.prod.yml).

FROM node:22-alpine AS compilar
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
# La API cuelga de /api en el mismo dominio (ver deploy/Caddyfile), así que el
# navegador no necesita CORS y la URL no queda fija en el código.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM caddy:2-alpine
COPY --from=compilar /app/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
