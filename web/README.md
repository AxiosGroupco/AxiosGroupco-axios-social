# Sitio web corporativo — Axios Group S.A.S.

Sitio estático (HTML + CSS + JS, sin dependencias ni paso de compilación) para
`www.axiosgroupco.com`. Incluye el acceso **Ingresar** a la plataforma Axios
(`app-axios`), donde el usuario se autentica con su correo y contraseña.

```
web/
  index.html            página principal (servicios, plataforma, método, contacto)
  404.html              página de error
  _headers              cabeceras de seguridad (CSP, HSTS, etc.) para Cloudflare Pages
  _redirects            accesos cortos: /ingresar, /app y /login -> login de la plataforma
  robots.txt, sitemap.xml
  favicon.ico
  assets/css/styles.css
  assets/js/main.js     menú móvil, sombra de cabecera, año del pie
  assets/fonts/         Poppins autoalojada (licencia OFL, ver OFL.txt)
  assets/img/           logo, íconos y imagen para compartir en redes (og-axios.png)
```

## Cómo funciona el acceso a la plataforma

Todos los botones **Ingresar** llevan a `https://app-axios.pages.dev/login`,
el login real de la app (FastAPI `POST /api/v1/auth/login`). El sitio **no
recibe ni procesa contraseñas**: las credenciales se escriben solo en el
dominio de la app. Así no hay que tocar la app en producción ni ampliar CORS.

Los usuarios los crea un administrador desde la app (Configuración → usuarios).
La app no tiene "olvidé mi contraseña", así que el sitio remite a
`administracion@axiosgroupco.com` para crear o restablecer accesos.

### Si la app cambia de dominio (p. ej. `app.axiosgroupco.com`)

Reemplazar `https://app-axios.pages.dev` en `index.html`, `404.html` y
`_redirects`. Antes de hacerlo, ese dominio debe estar activo en el proyecto
de Cloudflare Pages de la app y en `CORS_ORIGINS` del backend en Fly.io.

## Vista local

```bash
python3 -m http.server 8080 --directory web
# abrir http://localhost:8080
```

## Publicación en Cloudflare Pages (gratis)

1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**.
2. Repositorio `AxiosGroupco/AxiosGroupco-axios-social`, rama `main`.
3. Framework preset: **None** · Build command: *(vacío; si lo exige, `exit 0`)* ·
   Build output directory: **`web`**.
4. Al terminar, el sitio queda en `https://<proyecto>.pages.dev`.

### Dominio `axiosgroupco.com`

Estado al 18-oct-2026: el DNS está en Squarespace Domains (antes Google
Domains) y apunta a un sitio de Squarespace **que fue eliminado** (muestra
"Sitio eliminado").

1. En el proyecto de Pages: **Custom domains** → agregar `www.axiosgroupco.com`.
2. En Squarespace Domains → DNS:
   - Cambiar el CNAME `www` (hoy `ext-sq.squarespace.com`) por `<proyecto>.pages.dev`.
   - Para el dominio raíz, quitar los 4 registros A de Squarespace
     (`198.185.159.144/145`, `198.49.23.144/145`) y configurar
     **reenvío de dominio** `axiosgroupco.com` → `https://www.axiosgroupco.com`.
3. **No tocar** los registros del correo (Google Workspace):
   MX `smtp.google.com` (prioridad 1), TXT SPF `v=spf1 include:_spf.google.com ~all`,
   DKIM `google._domainkey` y DMARC `_dmarc`.

Alternativa a mediano plazo: mover los nameservers a Cloudflare (permite el
dominio raíz directo en Pages y gestionar `app.axiosgroupco.com` en el mismo
panel). Si se hace, copiar primero **todos** los registros MX/TXT anteriores.

## Pendientes de contenido

- NIT, ciudad y dirección física (no se publicaron por no tener el dato).
- Enlace a la Política de Tratamiento de Datos Personales cuando el abogado
  la apruebe (en la app sigue detrás de `VITE_FEATURE_LEGAL_PUBLICO=false`).
  El sitio no usa cookies, analítica ni formularios: no recolecta datos personales.
