# Sitio web corporativo — Axios Group S.A.S.

Sitio estático (HTML + CSS + JS, sin dependencias ni paso de compilación) para
`www.axiosgroupco.com`. Incluye el acceso **Ingresar** a la plataforma Axios
(`app-axios`), donde el usuario se autentica con su correo y contraseña.

```
web/
  index.html            página principal (servicios, plataforma, método, contacto)
  404.html              página de error
  ingresar/index.html   acceso corto /ingresar -> login de la plataforma
  .nojekyll             GitHub Pages sirve los archivos tal cual (sin Jekyll)
  _headers, _redirects  equivalentes para Cloudflare Pages (si se migra allí)
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

Reemplazar `https://app-axios.pages.dev` en `index.html`, `404.html`,
`ingresar/index.html` y `_redirects`. Antes de hacerlo, ese dominio debe estar activo en el proyecto
de Cloudflare Pages de la app y en `CORS_ORIGINS` del backend en Fly.io.

## Vista local

```bash
python3 -m http.server 8080 --directory web
# abrir http://localhost:8080
```

## Publicación (GitHub Pages, automática)

`.github/workflows/sitio-web.yml` publica `web/` en la rama `gh-pages` cada vez
que algo de `web/` cambia en `main`. GitHub Pages sirve esa rama en:

- Vista previa: `https://axiosgroupco.github.io/AxiosGroupco-axios-social/`
- Definitivo: `https://www.axiosgroupco.com/` (cuando el DNS apunte a GitHub)

Si la vista previa responde 404, GitHub Pages no está activado aún:
**Settings → Pages → Build and deployment → Deploy from a branch →
`gh-pages` / `(root)` → Save** (una sola vez).

### Dominio `axiosgroupco.com`

Estado al 18-oct-2026: el DNS está en Squarespace Domains (antes Google
Domains) y apunta a un sitio de Squarespace **que fue eliminado** (muestra
"Sitio eliminado").

1. En Squarespace Domains → `axiosgroupco.com` → DNS:
   - Borrar los 4 registros **A** de Squarespace
     (`198.185.159.144`, `198.185.159.145`, `198.49.23.144`, `198.49.23.145`)
     y crear 4 registros **A** `@` hacia GitHub Pages:
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - Cambiar el **CNAME** `www` (hoy `ext-sq.squarespace.com`) por
     `axiosgroupco.github.io`.
2. **No tocar** los registros del correo (Google Workspace):
   MX `smtp.google.com` (prioridad 1), TXT SPF `v=spf1 include:_spf.google.com ~all`,
   DKIM `google._domainkey` y DMARC `_dmarc`.
3. Cuando el DNS propague (minutos a pocas horas), crear `web/CNAME` con una
   sola línea `www.axiosgroupco.com` y hacer push a `main`. **No** configurar
   el dominio solo desde Settings: la publicación reescribe `gh-pages` y lo
   borraría. GitHub emite el certificado HTTPS y redirige
   `axiosgroupco.com` → `www.axiosgroupco.com` automáticamente; luego activar
   **Enforce HTTPS** en Settings → Pages.

### Alternativa: Cloudflare Pages

`_headers` y `_redirects` ya están listos para Cloudflare Pages (cabeceras de
seguridad completas y `/ingresar`, `/app`, `/login` como redirecciones HTTP).
Proyecto con Framework preset **None**, sin build command y
Build output directory **`web`**. Para el dominio raíz, Cloudflare exige mover
los nameservers (copiar antes **todos** los registros MX/TXT del correo).

## Pendientes de contenido

- NIT, ciudad y dirección física (no se publicaron por no tener el dato).
- Enlace a la Política de Tratamiento de Datos Personales cuando el abogado
  la apruebe (en la app sigue detrás de `VITE_FEATURE_LEGAL_PUBLICO=false`).
  El sitio no usa cookies, analítica ni formularios: no recolecta datos personales.
