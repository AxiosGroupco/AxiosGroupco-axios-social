"""Mascotas de Axios en Blender: tres personajes en bloques detallados, uno por socio.

Uso (sin interfaz):
  blender -b -P mascotas.py -- --salida equipo.png [--retrato 0|1|2] [--muestras 96] [--blend mascotas.blend]

Estilo: cuerpo en bloques con bisel, pelo en mechones curvos y suavizados, ropa con detalles
(capucha y cordones, cuello y bolsillo con lapicero, blazer con corbata), materiales físicos
e iluminación de estudio con Cycles. Los rasgos de cada socio se toman de fotos de
referencia que no se guardan en el repositorio.
"""
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

AQUI = Path(__file__).resolve().parent
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(nombre, defecto=None):
    return args[args.index(nombre) + 1] if nombre in args else defecto

SALIDA = arg('--salida', str(AQUI / 'equipo.png'))
RETRATO = arg('--retrato')
MUESTRAS = int(arg('--muestras', 96))
BLEND = arg('--blend')

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- utilidades
def hex2rgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1,)

_mats = {}
def mat(nombre, color, rough=0.6, sss=0.0, sheen=0.0, metal=0.0, emision=0.0, ruido=0.0, factor=1.0):
    if nombre in _mats:
        return _mats[nombre]
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    p = n['Principled BSDF']
    base = tuple(c * factor for c in hex2rgb(color)[:3]) + (1,)
    p.inputs['Base Color'].default_value = base
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
        p.inputs['Subsurface Scale'].default_value = 0.08
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen
    if emision:
        p.inputs['Emission Color'].default_value = base
        p.inputs['Emission Strength'].default_value = emision
    if ruido:
        # Variación sutil de tono y relieve (tela, jean, pelo) para que no se vea plástico
        tex = n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 40; tex.inputs['Detail'].default_value = 8
        mx = n.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
        mx.inputs['Factor'].default_value = ruido; mx.inputs['A'].default_value = base
        l.new(tex.outputs['Fac'], mx.inputs['B']); l.new(mx.outputs['Result'], p.inputs['Base Color'])
        bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08
        l.new(tex.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs['Normal'], p.inputs['Normal'])
    _mats[nombre] = m
    return m

def mat_imagen(nombre, archivo):
    """Material con una imagen PNG con transparencia (logos estampados)."""
    if nombre in _mats:
        return _mats[nombre]
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    p = n['Principled BSDF']; p.inputs['Roughness'].default_value = 0.7
    img = n.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(str(archivo), check_existing=True)
    img.interpolation = 'Cubic'
    l.new(img.outputs['Color'], p.inputs['Base Color']); l.new(img.outputs['Alpha'], p.inputs['Alpha'])
    _mats[nombre] = m
    return m

def vacio(nombre, loc=(0, 0, 0), padre=None):
    e = bpy.data.objects.new(nombre, None); scene.collection.objects.link(e)
    e.parent = padre; e.location = loc
    return e

def _malla_caja(nombre, tam, desplaza=(0, 0, 0)):
    me = bpy.data.meshes.new(nombre); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    me.transform(Matrix.Translation(desplaza) @ Matrix.Diagonal((tam[0], tam[1], tam[2], 1)))
    for f in me.polygons: f.use_smooth = True
    return me

def caja(nombre, tam, loc, material, padre=None, rot=(0, 0, 0), bisel=None):
    """Caja con medidas reales (escala aplicada) y bisel proporcional."""
    ob = bpy.data.objects.new(nombre, _malla_caja(nombre, tam)); scene.collection.objects.link(ob)
    ob.parent = padre; ob.location = loc; ob.rotation_euler = rot
    ob.data.materials.append(material)
    b = ob.modifiers.new('bisel', 'BEVEL'); b.width = bisel if bisel is not None else min(0.06, min(tam) * 0.18)
    b.segments = 3; b.limit_method = 'NONE'
    return ob

def cilindro(nombre, r, largo, loc, material, padre=None, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(nombre); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=r, radius2=r, depth=largo); bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    ob = bpy.data.objects.new(nombre, me); scene.collection.objects.link(ob)
    ob.parent = padre; ob.location = loc; ob.rotation_euler = rot; ob.data.materials.append(material)
    return ob

def plano_imagen(nombre, ancho, alto, loc, material, padre=None):
    me = bpy.data.meshes.new(nombre); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); bm.to_mesh(me); bm.free()
    me.uv_layers.new(name='UV')
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            me.uv_layers['UV'].data[li].uv = (v.x + 0.5, v.y + 0.5)
    me.transform(Matrix.Diagonal((ancho, alto, 1, 1)))
    ob = bpy.data.objects.new(nombre, me); scene.collection.objects.link(ob)
    ob.parent = padre; ob.location = loc; ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.data.materials.append(material)
    return ob

def mechon(nombre, largo, ancho, grosor, base, direccion, normal, material, padre, curva=0.4, giro=0.0):
    """Mechón de pelo: bloque alargado, muy biselado y suavizado, curvado a lo largo.
    Nace en `base`, crece hacia `direccion` y su cara ancha mira hacia `normal`."""
    me = _malla_caja(nombre, (ancho, largo, grosor), (0, largo / 2, 0))
    ob = bpy.data.objects.new(nombre, me); scene.collection.objects.link(ob)
    ob.data.materials.append(material); ob.parent = padre
    y = Vector(direccion).normalized()
    x = y.cross(Vector(normal)).normalized()
    if x.length < 1e-4:
        x = Vector((1, 0, 0))
    z = x.cross(y).normalized()
    rot = Matrix((x, y, z)).transposed() @ Matrix.Rotation(giro, 3, 'Y')
    ob.matrix_basis = Matrix.Translation(base) @ rot.to_4x4()
    b = ob.modifiers.new('bisel', 'BEVEL'); b.width = min(ancho, grosor) * 0.45; b.segments = 2; b.limit_method = 'NONE'
    d = ob.modifiers.new('curva', 'SIMPLE_DEFORM'); d.deform_method = 'BEND'; d.deform_axis = 'X'; d.angle = curva
    s = ob.modifiers.new('suave', 'SUBSURF'); s.levels = 1; s.render_levels = 2
    return ob

# ---------------------------------------------------------------- materiales comunes
BLANCO = mat('blanco', '#f4f5f7', 0.35)
SUELA = mat('suela', '#2b2f36', 0.6)
OJO_B = mat('ojo_blanco', '#fbfbfb', 0.25)
PUPILA = mat('pupila', '#0a0c10', 0.15)
BRILLO = mat('brillo', '#ffffff', 0.1, emision=2.0)
BOCA = mat('boca', '#3a0c14', 0.6)
DIENTES = mat('dientes', '#ffffff', 0.3)
LENGUA = mat('lengua', '#d45b6b', 0.5, sss=0.2)
ORO = mat('oro', '#e2b44f', 0.2, metal=1.0)
PLATA = mat('plata', '#d6dbe2', 0.2, metal=1.0)
MONTURA = mat('montura', '#0d1117', 0.2)
CINTURON = mat('cinturon', '#3a2618', 0.45)
HEBILLA = mat('hebilla', '#c9ced6', 0.25, metal=1.0)
TEAL = mat('teal_axios', '#13808a', 0.45)
TEAL_BRILLO = mat('teal_brillo', '#4fc3cf', 0.3, emision=4.0)
CALC = mat('calculadora', '#1f2733', 0.4)
PANTALLA = mat('pantalla', '#9fe3e9', 0.2, emision=1.2)
LOGO = mat_imagen('logo_ax', AQUI / 'ax-simbolo.png')

PANTALONES = {
    'jean': (mat('jean', '#3f6596', 0.85, ruido=0.25), mat('jean_osc', '#2f4f7a', 0.85, ruido=0.2), mat('costura', '#c9a25a', 0.6)),
    'chino': (mat('chino', '#22304d', 0.8, ruido=0.15), mat('chino_osc', '#1a2540', 0.8), None),
    'gris': (mat('gris', '#3a3f4a', 0.75, ruido=0.12), mat('gris_osc', '#2d313a', 0.75), None),
    'negro': (mat('negro', '#1c1d21', 0.7, ruido=0.1), mat('negro_osc', '#141518', 0.7), None),
    'caqui': (mat('caqui', '#a88c62', 0.8, ruido=0.12), mat('caqui_osc', '#8f7652', 0.8), None),
}
ZAPATOS = {
    'tenis': (BLANCO, SUELA),
    'cuero_cafe': (mat('cuero_cafe', '#5b3520', 0.35), mat('suela_cafe', '#2a1a10', 0.5)),
    'cuero_negro': (mat('cuero_negro', '#16181c', 0.3), mat('suela_negra', '#0c0d10', 0.5)),
}

# ---------------------------------------------------------------- personajes
SOCIOS = [
    # Centro: camisa de vestir blanca con símbolo AX y lapicero dorado, copete, barba de candado
    dict(nombre='socio1', piel='#c8753d', pelo='#2a140a', ojos='#000000', atuendo='camisa_vestir', pantalon='chino',
         zapato='cuero_cafe', peinado='copete', barba=True, ancho=1.1, ceja=0.2, semilla=11),
    # Izquierda: rizos, gafas, blazer negro con camisa negra, cadena con cruz, pantalón cargo caqui
    dict(nombre='socio2', piel='#b56a34', pelo='#140d09', ojos='#000000', atuendo='blazer', saco='#0b0b0c', camisa='#111214', panuelo=False,
         pantalon='caqui', zapato='tenis', peinado='rizado', gafas=True, cadena='plata', cruz=True, cargo=True,
         ancho=0.98, ceja=0.16, semilla=5),
    # Derecha: pelo texturizado, blazer azul con camisa blanca, pantalón caqui
    dict(nombre='socio3', piel='#c97a42', pelo='#2b170b', ojos='#000000', atuendo='blazer', saco='#1d2f57', camisa='#f1f3f6',
         pantalon='caqui', zapato='cuero_negro', peinado='texturizado', ancho=1.02, ceja=0.16, semilla=3),
]

TOP = 1.62  # altura de la coronilla en coordenadas de la cabeza

def mat_mechones(nombre, color):
    """Pelo esculpido: color base con vetas finas a lo largo de cada mechón, brillo suave y relieve."""
    if nombre in _mats:
        return _mats[nombre]
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    p = n['Principled BSDF']
    p.inputs['Roughness'].default_value = 0.32
    p.inputs['Sheen Weight'].default_value = 0.2
    p.inputs['Sheen Tint'].default_value = hex2rgb(color)
    p.inputs['Coat Weight'].default_value = 0.3
    p.inputs['Coat Roughness'].default_value = 0.25
    uv = n.new('ShaderNodeUVMap')
    ola = n.new('ShaderNodeTexWave'); ola.wave_type = 'BANDS'; ola.bands_direction = 'X'
    ola.inputs['Scale'].default_value = 7.0; ola.inputs['Distortion'].default_value = 4.0; ola.inputs['Detail'].default_value = 6.0
    ruido = n.new('ShaderNodeTexNoise'); ruido.inputs['Scale'].default_value = 25.0
    rampa = n.new('ShaderNodeValToRGB')
    rampa.color_ramp.elements[0].color = tuple(c * 0.6 for c in hex2rgb(color)[:3]) + (1,)
    rampa.color_ramp.elements[1].color = tuple(min(1.0, c * 1.6) for c in hex2rgb(color)[:3]) + (1,)
    mezcla = n.new('ShaderNodeMath'); mezcla.operation = 'MULTIPLY'
    l.new(uv.outputs['UV'], ola.inputs['Vector'])
    l.new(ola.outputs['Fac'], mezcla.inputs[0]); l.new(ruido.outputs['Fac'], mezcla.inputs[1])
    l.new(ola.outputs['Fac'], rampa.inputs['Fac'])
    l.new(rampa.outputs['Color'], p.inputs['Base Color'])
    relieve = n.new('ShaderNodeBump'); relieve.inputs['Strength'].default_value = 0.6; relieve.inputs['Distance'].default_value = 0.03
    l.new(mezcla.outputs['Value'], relieve.inputs['Height']); l.new(relieve.outputs['Normal'], p.inputs['Normal'])
    _mats[nombre] = m
    return m

def mechones(nombre, lista, material, padre):
    """Malla de mechones esculpidos: cada uno es un tubo aplanado, grueso en la raíz y en punta,
    que se curva a lo largo. lista: dicts con base, dir, normal, largo, radio, curva, giro, ancho."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV')
    ANILLOS, LADOS = 10, 12
    for m in lista:
        P = Vector(m['base']); T = Vector(m['dir']).normalized()
        Nn = Vector(m['normal']); Nn = (Nn - T * Nn.dot(T)).normalized()
        ds = m['largo'] / (ANILLOS - 1)
        anillos = []
        for i in range(ANILLOS):
            t = i / (ANILLOS - 1)
            r = m['radio'] * (1 - 0.82 * t ** 1.8) + 0.006
            B = T.cross(Nn)
            anillo = []
            for j in range(LADOS):
                a = 2 * math.pi * j / LADOS
                anillo.append(bm.verts.new(P + B * math.cos(a) * r * m.get('ancho', 1.35) + Nn * math.sin(a) * r * 0.72))
            anillos.append(anillo)
            # Avanza y curva: gira alrededor de B (se acuesta o se enrosca) y alrededor de T (torsión)
            rot = Matrix.Rotation(m['curva'] * ds, 3, B) @ Matrix.Rotation(m.get('giro', 0.0) * ds, 3, T)
            P = P + T * ds; T = (rot @ T).normalized(); Nn = (rot @ Nn).normalized()
        punta = bm.verts.new(P)
        for i in range(ANILLOS - 1):
            for j in range(LADOS):
                k = (j + 1) % LADOS
                f = bm.faces.new((anillos[i][j], anillos[i][k], anillos[i + 1][k], anillos[i + 1][j]))
                for lo, (u, v) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                    lo[uvl].uv = (u / LADOS, v / (ANILLOS - 1))
        for j in range(LADOS):
            k = (j + 1) % LADOS
            f = bm.faces.new((anillos[-1][j], anillos[-1][k], punta))
            for lo, (u, v) in zip(f.loops, ((j / LADOS, 1.0), ((j + 1) / LADOS, 1.0), ((j + 0.5) / LADOS, 1.0))):
                lo[uvl].uv = (u, v)
        bm.faces.new(list(reversed(anillos[0])))
    me = bpy.data.meshes.new(nombre); bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    ob = bpy.data.objects.new(nombre, me); scene.collection.objects.link(ob); ob.parent = padre
    ob.data.materials.append(material)
    s_ = ob.modifiers.new('suave', 'SUBSURF'); s_.levels = 1; s_.render_levels = 2
    return ob

def cintas(nombre, lista, material, padre):
    """Mechones largos y lisos que siguen una ruta (copete): sección aplanada orientada hacia afuera
    de la cabeza, un poco más delgada en la raíz, ancha en el centro y en punta al final."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV')
    LADOS = 14
    for m in lista:
        ruta = [Vector(p) for p in m['ruta']]; n = len(ruta)
        anillos = []
        for i, P in enumerate(ruta):
            t = i / (n - 1)
            T = (ruta[min(i + 1, n - 1)] - ruta[max(i - 1, 0)]).normalized()
            H = Vector(m.get('normal', (0, 0, 1)))
            if 'centro' in m:
                H = (P - Vector(m['centro'])).normalized()
            N = (H - T * H.dot(T)).normalized(); B = T.cross(N)
            r = m['radio'] * (0.8 + 0.2 * math.sin(min(t * 4, 1) * math.pi / 2)) * (1 - 0.85 * t ** 3) + 0.006
            anillos.append([bm.verts.new(P + B * math.cos(2 * math.pi * j / LADOS) * r * m.get('ancho', 1.7)
                                        + N * math.sin(2 * math.pi * j / LADOS) * r * m.get('grosor', 0.5)) for j in range(LADOS)])
        for i in range(n - 1):
            for j in range(LADOS):
                k = (j + 1) % LADOS
                f = bm.faces.new((anillos[i][j], anillos[i][k], anillos[i + 1][k], anillos[i + 1][j]))
                for lo, (u, v) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                    lo[uvl].uv = (u / LADOS, v / (n - 1))
        bm.faces.new(list(reversed(anillos[0]))); bm.faces.new(anillos[-1])
    me = bpy.data.meshes.new(nombre); bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    ob = bpy.data.objects.new(nombre, me); scene.collection.objects.link(ob); ob.parent = padre
    ob.data.materials.append(material)
    s_ = ob.modifiers.new('suave', 'SUBSURF'); s_.levels = 1; s_.render_levels = 2
    return ob

def _bez(p0, p1, p2, p3, n=10):
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3)))
    return out

class Cupula:
    """Elipsoide que envuelve la cabeza y define el volumen del pelo (cuánto sobresale arriba y a los lados)."""
    def __init__(self, alto, lado=1.0, fondo=0.95):
        self.c = Vector((0, 0.04, TOP - 0.55)); self.r = Vector((lado, fondo, 0.55 + alto))
    def punto(self, u, escala=1.0):
        return Vector((self.c.x + self.r.x * u.x * escala, self.c.y + self.r.y * u.y * escala, self.c.z + self.r.z * u.z * escala))
    def normal(self, u):
        return Vector((u.x / self.r.x, u.y / self.r.y, u.z / self.r.z)).normalized()

def _direcciones(n, rnd):
    """Puntos repartidos de forma pareja sobre una esfera (espiral de Fibonacci) con un poco de azar."""
    oro = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - z * z); th = oro * i + rnd.uniform(-0.15, 0.15)
        yield Vector((r * math.cos(th), r * math.sin(th), z))

def _cubre(u, cup, frente_min=TOP - 0.02):
    """Zona con pelo: arriba, lados por encima de las orejas y nuca; nunca sobre la cara."""
    p = cup.punto(u)
    if p.z < 1.0:
        return False
    if u.y < -0.45 and p.z < frente_min:
        return False
    if abs(p.x) > 0.6 and p.y < -0.4 and p.z < TOP - 0.1:
        return False
    return True

def _tangente(v, nrm):
    v = Vector(v); return (v - nrm * v.dot(nrm)).normalized()

def _masa(cup, PELO, cabeza, escala=0.9):
    """Masa interior que tapa los huecos entre mechones (casquete de la cúpula, un poco más pequeño)."""
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not _cubre(v.co.normalized(), cup)], context='VERTS')
    me = bpy.data.meshes.new('pelo_masa'); bm.to_mesh(me); bm.free()
    me.transform(Matrix.Translation(cup.c) @ Matrix.Diagonal((cup.r.x * escala, cup.r.y * escala, cup.r.z * escala, 1)))
    for f in me.polygons: f.use_smooth = True
    masa = bpy.data.objects.new('pelo_masa', me); scene.collection.objects.link(masa); masa.parent = cabeza
    masa.data.materials.append(PELO)

def pelo(s, cabeza, PELO, rnd):
    """Pelo esculpido con el volumen de la guía. La cabeza ocupa x ±0.88, y ±0.81 (frente en -y), z 0..1.62."""
    est = s['peinado']
    MECH = mat_mechones(f"mechones_{s['nombre']}", s['pelo'])
    J = lambda a: rnd.uniform(-a, a)
    caja('pelo_tapa', (1.76, 1.45, 0.1), (0, 0.12, TOP + 0.03), PELO, cabeza, bisel=0.04)
    caja('pelo_nuca', (1.82, 0.08, 0.95), (0, 0.83, 1.16), PELO, cabeza, bisel=0.03)
    for sx in (-1, 1):
        caja('pelo_lado', (0.08, 1.05, 0.6), (sx * 0.9, 0.2, 1.3), PELO, cabeza, bisel=0.03)

    if est == 'copete':
        # Copete: mechones gruesos y redondeados que suben desde la frente y se barren en diagonal
        # hacia atrás y a la derecha; las puntas caen por el lado derecho. Lados cortos.
        raya = -0.5; L = []
        for capa, (n_, pico, rad) in enumerate(((8, 0.82, 0.15), (7, 0.66, 0.14))):
            for i in range(n_):
                x0 = raya + 0.06 + (i + 0.5 * capa) * (1.3 / n_)
                h = pico - 0.2 * max(0.0, x0 - 0.0)
                xf = min(x0 + 0.78, 1.0)
                tramo1 = _bez((x0, -0.78 + 0.1 * capa, TOP - 0.06), (x0 + 0.04, -1.08 + 0.1 * capa, TOP + h * 0.85),
                              (x0 + 0.34, -0.42, TOP + h), (xf, 0.3, TOP + h * 0.5), 10)
                tramo2 = _bez((xf, 0.3, TOP + h * 0.5), (min(xf + 0.06, 1.0), 0.62, TOP + h * 0.3), (1.0, 0.85, TOP + 0.02),
                              (0.98, 0.9, TOP - 0.32), 6)
                L.append(dict(ruta=tramo1 + tramo2[1:], radio=rad * rnd.uniform(0.95, 1.08), ancho=1.25, grosor=0.85,
                              centro=(0, 0.1, TOP - 0.5)))
        for j in range(5):
            y = -0.7 + j * 0.32
            L.append(dict(ruta=_bez((raya + 0.02, y, TOP + 0.06), (raya - 0.22, y + 0.03, TOP + 0.4), (-0.88, y + 0.08, TOP + 0.24),
                                    (-0.98, y + 0.12, TOP - 0.25), 10), radio=0.13, ancho=1.3, grosor=0.8, centro=(0, 0.1, TOP - 0.5)))
        cintas('pelo', L, MECH, cabeza)
        return

    if est == 'rizado':
        # Masa redonda de rizos en bolitas (afro corto): esferas pequeñas y apretadas en dos capas
        cup = Cupula(0.82, lado=1.2, fondo=1.08); _masa(cup, PELO, cabeza, escala=0.9)
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV')
        for esc, n_ in ((1.0, 620), (0.94, 380)):
            for u in _direcciones(n_, rnd):
                if not _cubre(u, cup, TOP - 0.12):
                    continue
                nrm = cup.normal(u); c = cup.punto(u, esc) - nrm * 0.05
                r = rnd.uniform(0.1, 0.13)
                g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
                rot = Matrix.Rotation(rnd.uniform(0, 6.3), 3, Vector((J(1), J(1), J(1))).normalized() or Vector((0, 0, 1)))
                for v in g['verts']:
                    v.co = c + rot @ Vector((v.co.x * 1.1, v.co.y, v.co.z * 0.9))
                caras = {f for v in g['verts'] for f in v.link_faces}
                for f in caras:
                    for lo in f.loops:
                        d = (lo.vert.co - c).normalized()
                        lo[uvl].uv = (math.atan2(d.y, d.x) / 6.283 + 0.5, d.z * 0.5 + 0.5)
        me = bpy.data.meshes.new('rizos'); bm.to_mesh(me); bm.free()
        for f in me.polygons: f.use_smooth = True
        ob = bpy.data.objects.new('rizos', me); scene.collection.objects.link(ob); ob.parent = cabeza
        ob.data.materials.append(MECH)
        return

    # Texturizado: mechones gruesos en punta, hacia adelante y arriba, con flequillo que cubre la parte alta de la frente
    cup = Cupula(0.52, lado=1.1, fondo=1.0); _masa(cup, PELO, cabeza, escala=0.9)
    L = []
    for u in _direcciones(560, rnd):
        if not _cubre(u, cup, TOP - 0.1):
            continue
        nrm = cup.normal(u); base = cup.punto(u) - nrm * 0.09; x, y, z = base
        if z > TOP:
            d = _tangente((J(0.6), -1.0, 0.35), nrm) + nrm * rnd.uniform(0.5, 0.9); curva = -2.2 + J(0.9)
        else:
            d = _tangente((math.copysign(0.4, x), 0.1, -1.0), nrm) + nrm * 0.35; curva = -1.8
        largo = rnd.uniform(0.45, 0.58) if z > TOP else rnd.uniform(0.24, 0.3)
        L.append(dict(base=base, dir=d, normal=nrm, largo=largo, radio=rnd.uniform(0.12, 0.14),
                      curva=curva, giro=J(1.2), ancho=1.3))
    for k in range(12):
        x = -0.78 + k * 0.142
        L.append(dict(base=(x + J(0.03), -0.74, TOP + 0.14), dir=(J(0.5), -0.9, 0.1), normal=(0, -0.5, 1), largo=rnd.uniform(0.4, 0.48),
                      radio=0.12, curva=-3.6 + J(0.6), giro=J(0.8), ancho=1.3))
    mechones('pelo', L, MECH, cabeza)

def barba(cabeza, BARBA):
    """Barba de candado gruesa: bigote, perilla y línea por la quijada hasta las patillas."""
    caja('barba_menton', (1.4, 0.1, 0.16), (0, -0.8, 0.08), BARBA, cabeza, bisel=0.04)
    for sx in (-1, 1):
        caja('bigote', (0.27, 0.07, 0.09), (sx * 0.13, -0.835, 0.54), BARBA, cabeza, rot=(0, sx * 0.18, 0), bisel=0.03)
    for sx in (-1, 1):
        caja('candado', (0.09, 0.07, 0.42), (sx * 0.33, -0.825, 0.34), BARBA, cabeza, bisel=0.03)
        caja('quijada_frente', (0.1, 0.09, 0.42), (sx * 0.81, -0.8, 0.3), BARBA, cabeza, rot=(0, sx * -0.25, 0), bisel=0.03)
        caja('barba_lado', (0.08, 0.7, 0.75), (sx * 0.9, -0.38, 0.5), BARBA, cabeza, rot=(0.3, 0, 0), bisel=0.03)
        caja('patilla', (0.08, 0.26, 0.4), (sx * 0.9, -0.05, 0.98), BARBA, cabeza, bisel=0.02)
    caja('mosca', (0.14, 0.06, 0.12), (0, -0.82, 0.22), BARBA, cabeza, bisel=0.025)

def ropa(s, torso, w, mats):
    """Torso vestido según el atuendo; devuelve los materiales de manga y puño."""
    at = s['atuendo']
    if at == 'buso':
        TELA = mat(f"buso_{s['nombre']}", '#23262c', 0.85, sheen=0.5, ruido=0.12)
        TELA2 = mat(f"buso2_{s['nombre']}", '#23262c', 0.9, factor=0.75)
        caja('cuerpo', (1.64 * w, 0.9, 1.44), (0, 0, 0.7), TELA, torso, bisel=0.12)
        caja('ruedo', (1.66 * w, 0.92, 0.16), (0, 0, 0.06), TELA2, torso, bisel=0.05)
        # Capucha caída sobre la espalda y los hombros
        caja('capucha', (1.16, 0.46, 0.52), (0, 0.4, 1.42), TELA, torso, rot=(-0.35, 0, 0), bisel=0.16)
        for sx in (-1, 1):
            caja('capucha_borde', (0.24, 0.7, 0.3), (sx * 0.44, -0.04, 1.45), TELA, torso, rot=(0, 0, sx * 0.3), bisel=0.1)
            caja('cuello_v', (0.3, 0.14, 0.22), (sx * 0.18, -0.42, 1.38), TELA2, torso, rot=(0, 0, sx * 0.55), bisel=0.06)
            cilindro('cordon', 0.028, 0.32, (sx * 0.16, -0.47, 1.16), BLANCO, torso)
            cilindro('punta_cordon', 0.034, 0.08, (sx * 0.16, -0.47, 0.97), PLATA, torso)
        # Bolsillo canguro con costura
        caja('bolsillo', (1.0 * w, 0.05, 0.42), (0, -0.465, 0.32), TELA, torso, bisel=0.03)
        caja('bolsillo_borde', (1.0 * w, 0.06, 0.05), (0, -0.47, 0.53), TELA2, torso, bisel=0.015)
        for sx in (-1, 1):
            caja('bolsillo_lado', (0.05, 0.06, 0.4), (sx * 0.5 * w, -0.47, 0.32), TELA2, torso, rot=(0, sx * 0.35, 0), bisel=0.015)
        plano_imagen('logo_pecho', 0.48, 0.39, (0, -0.452, 0.74), LOGO, torso)
        return TELA, TELA2
    if at == 'camisa_vestir':
        TELA = mat(f"camisa_{s['nombre']}", '#f1f3f6', 0.65, sheen=0.3, ruido=0.06)
        TELA2 = mat(f"camisa2_{s['nombre']}", '#f1f3f6', 0.7, factor=0.86)
        BOTON = mat('boton_camisa', '#d5d9df', 0.3)
        caja('cuerpo', (1.62 * w, 0.88, 1.42), (0, 0, 0.7), TELA, torso, bisel=0.09)
        caja('cuello', (0.76, 0.66, 0.13), (0, 0, 1.4), TELA, torso, bisel=0.04)
        for sx in (-1, 1):
            caja('punta_cuello', (0.36, 0.07, 0.26), (sx * 0.2, -0.45, 1.33), TELA, torso, rot=(0.25, 0, sx * 0.6), bisel=0.03)
        caja('piel_v', (0.16, 0.03, 0.14), (0, -0.445, 1.3), mats['PIEL2'], torso, bisel=0.02)
        caja('tapeta', (0.14, 0.03, 1.2), (0, -0.452, 0.62), TELA2, torso, bisel=0.012)
        for i in range(5):
            caja('boton', (0.06, 0.03, 0.06), (0, -0.47, 1.12 - i * 0.24), BOTON, torso, bisel=0.012)
        # Bolsillo en el pecho (lado izquierdo del socio) con el símbolo AX y el lapicero dorado
        px = 0.44 * w
        caja('bolsillo', (0.38, 0.04, 0.4), (px, -0.455, 0.86), TELA, torso, bisel=0.02)
        caja('bolsillo_borde', (0.39, 0.05, 0.05), (px, -0.46, 1.05), TELA2, torso, bisel=0.012)
        plano_imagen('logo_bolsillo', 0.22, 0.18, (px + 0.04, -0.478, 0.82), LOGO, torso)
        cilindro('lapicero', 0.035, 0.42, (px - 0.1, -0.47, 1.06), mat('lapicero', '#1a1a1d', 0.25), torso)
        cilindro('lapicero_tapa', 0.038, 0.16, (px - 0.1, -0.47, 1.2), ORO, torso)
        cilindro('lapicero_punta', 0.02, 0.04, (px - 0.1, -0.47, 1.3), ORO, torso)
        caja('lapicero_gancho', (0.03, 0.02, 0.2), (px - 0.1, -0.505, 1.12), ORO, torso, bisel=0.008)
        return TELA, TELA2
    if at == 'blazer':
        saco_c, cam_c = s.get('saco', '#1d2c4f'), s.get('camisa', '#f1f3f6')
        SACO = mat(f"blazer_{s['nombre']}", saco_c, 0.88, ruido=0.08)
        SACO2 = mat(f"blazer2_{s['nombre']}", saco_c, 0.5, factor=0.72)
        CAM = mat(f"camisa_{s['nombre']}", cam_c, 0.6, ruido=0.05)
        CAM2 = mat(f"camisa2_{s['nombre']}", cam_c, 0.7, factor=0.85)
        caja('cuerpo', (1.64 * w, 0.9, 1.44), (0, 0, 0.7), SACO, torso, bisel=0.09)
        caja('cuello', (0.76, 0.66, 0.13), (0, 0, 1.4), CAM, torso, bisel=0.04)
        # Abertura del saco en V que deja ver la camisa abierta (sin corbata)
        for an, z in ((0.62, 1.2), (0.5, 1.0), (0.38, 0.8), (0.26, 0.62)):
            caja('camisa_v', (an, 0.03, 0.22), (0, -0.452, z), CAM, torso, bisel=0.01)
        for sx in (-1, 1):
            caja('punta_cuello', (0.3, 0.06, 0.22), (sx * 0.18, -0.47, 1.33), CAM, torso, rot=(0.25, 0, sx * 0.6), bisel=0.025)
            caja('solapa', (0.22, 0.06, 0.85), (sx * 0.29, -0.47, 0.95), SACO2, torso, rot=(0, sx * 0.38, 0), bisel=0.03)
        caja('piel_v', (0.18, 0.03, 0.16), (0, -0.46, 1.3), mats['PIEL2'], torso, bisel=0.02)
        caja('tapeta', (0.1, 0.03, 0.62), (0, -0.462, 0.9), CAM2, torso, bisel=0.01)
        for z in (1.08, 0.86, 0.64):
            caja('boton_camisa', (0.05, 0.03, 0.05), (0, -0.478, z), CAM2, torso, bisel=0.01)
        caja('boton_saco', (0.08, 0.04, 0.08), (0.05, -0.47, 0.4), SACO2, torso, bisel=0.02)
        caja('linea_saco', (0.03, 0.03, 0.5), (0.04, -0.455, 0.25), SACO2, torso, bisel=0.008)
        if s.get('panuelo', True):
            caja('panuelo', (0.2, 0.05, 0.08), (0.5 * w, -0.47, 1.0), BLANCO, torso, bisel=0.02)
        caja('bolsillo_saco', (0.32, 0.04, 0.04), (0.5 * w, -0.462, 0.95), SACO2, torso, bisel=0.01)
        plano_imagen('pin_ax', 0.17, 0.14, (0.42 * w, -0.5, 1.14), LOGO, torso)
        for sx in (-1, 1):
            caja('bolsillo_bajo', (0.42, 0.04, 0.05), (sx * 0.46 * w, -0.462, 0.3), SACO2, torso, bisel=0.012)
        return SACO, CAM2

def personaje(s, x, y, giro, pose):
    rnd = random.Random(s['semilla'])
    PIEL = mat(f"piel_{s['nombre']}", s['piel'], 0.5, sss=0.06)
    PIEL2 = mat(f"piel2_{s['nombre']}", s['piel'], 0.55, sss=0.1, factor=0.82)
    PELO = mat(f"pelo_{s['nombre']}", s['pelo'], 0.6, ruido=0.2)
    IRIS = mat('iris_negro', '#0d0b0a', 0.2)
    w = s['ancho']
    PANT, PANT2, COST = PANTALONES[s['pantalon']]
    ZAP, SUEL = ZAPATOS[s['zapato']]

    raiz = vacio(s['nombre'], (x, y, 0)); raiz.rotation_euler = (0, 0, giro)

    # Zapatos y piernas
    for sx in (-1, 1):
        if s['zapato'] == 'tenis':
            caja('zapato', (0.62, 0.92, 0.3), (sx * 0.4 * w, -0.1, 0.2), ZAP, raiz)
            caja('cordones', (0.36, 0.3, 0.04), (sx * 0.4 * w, -0.32, 0.36), SUEL, raiz, bisel=0.015)
            caja('puntera', (0.64, 0.3, 0.16), (sx * 0.4 * w, -0.44, 0.16), SUEL, raiz, bisel=0.05)
            caja('talon', (0.64, 0.26, 0.2), (sx * 0.4 * w, 0.26, 0.2), SUEL, raiz, bisel=0.05)
        else:
            caja('zapato', (0.6, 0.96, 0.24), (sx * 0.4 * w, -0.12, 0.17), ZAP, raiz, bisel=0.09)
            caja('empeine', (0.5, 0.36, 0.1), (sx * 0.4 * w, -0.05, 0.3), ZAP, raiz, bisel=0.04)
        caja('suela', (0.66, 0.98, 0.09), (sx * 0.4 * w, -0.12, 0.045), SUEL, raiz, bisel=0.03)
        caja('pierna', (0.6 * w, 0.62, 1.05), (sx * 0.36 * w, 0, 0.86), PANT, raiz)
        if COST:
            caja('costura', (0.03, 0.025, 0.95), (sx * (0.36 * w + 0.302 * w), 0, 0.9), COST, raiz, bisel=0.008)
        caja('ruedo', (0.62 * w, 0.64, 0.08), (sx * 0.36 * w, 0, 0.38), PANT2, raiz, bisel=0.02)
        if s.get('cargo'):
            caja('bolsillo_cargo', (0.06, 0.36, 0.34), (sx * (0.36 * w + 0.31 * w), 0.0, 0.92), PANT, raiz, bisel=0.02)
            caja('tapa_cargo', (0.07, 0.38, 0.08), (sx * (0.36 * w + 0.32 * w), 0.0, 1.1), PANT2, raiz, bisel=0.015)
    caja('cadera', (1.46 * w, 0.74, 0.42), (0, 0, 1.52), PANT, raiz)
    caja('cinturon', (1.5 * w, 0.78, 0.13), (0, 0, 1.68), CINTURON, raiz, bisel=0.03)
    caja('hebilla', (0.24, 0.06, 0.15), (0, -0.41, 1.68), HEBILLA, raiz, bisel=0.02)

    # Torso y ropa
    torso = vacio('torso', (0, 0, 1.72), raiz)
    caja('cuello_piel', (0.52, 0.46, 0.3), (0, 0, 1.48), PIEL2, torso)
    MANGA, PUNO = ropa(s, torso, w, {'PIEL2': PIEL2})
    if s.get('cadena'):
        metal = ORO if s['cadena'] == 'oro' else PLATA
        for i in range(15):
            a = -1.15 + i * (2.3 / 14)
            caja('eslabon', (0.07, 0.04, 0.05), (math.sin(a) * 0.34, -0.48, 1.32 - math.cos(a) * 0.3 + 0.1), metal, torso, rot=(0, -a, 0), bisel=0.012)
        if s.get('cruz'):
            caja('cruz_v', (0.055, 0.03, 0.2), (0, -0.5, 1.03), metal, torso, bisel=0.012)
            caja('cruz_h', (0.15, 0.03, 0.055), (0, -0.5, 1.07), metal, torso, bisel=0.012)

    # Brazos con pivotes en hombro, codo y muñeca (manga larga en los tres atuendos)
    brazos = {}
    for lado, sx in (('der', -1), ('izq', 1)):
        hombro = vacio(f'hombro_{lado}', (sx * (0.81 * w + 0.27), 0, 1.28), torso)
        caja('manga', (0.54, 0.58, 0.72), (0, 0, -0.3), MANGA, hombro, bisel=0.08)
        codo = vacio(f'codo_{lado}', (0, 0, -0.64), hombro)
        caja('antebrazo', (0.46, 0.5, 0.62), (0, 0, -0.3), MANGA, codo, bisel=0.07)
        caja('puno', (0.49, 0.53, 0.12), (0, 0, -0.6), PUNO, codo, bisel=0.03)
        mano = vacio(f'mano_{lado}', (0, 0, -0.66), codo)
        caja('palma', (0.46, 0.44, 0.4), (0, 0, -0.18), PIEL, mano, bisel=0.07)
        for k in range(3):
            caja('dedo_linea', (0.018, 0.02, 0.16), (-0.1 + k * 0.1, -0.222, -0.3), PIEL2, mano, bisel=0.006)
        pulgar = vacio('pulgar_piv', (-sx * 0.2, -0.16, -0.06), mano)
        caja('pulgar', (0.14, 0.16, 0.24), (0, 0, -0.1), PIEL, pulgar, bisel=0.05)
        brazos[lado] = dict(hombro=hombro, codo=codo, mano=mano, pulgar=pulgar)

    # Cabeza
    cabeza = vacio('cabeza', (0, 0, 1.6), torso)
    caja('cabeza', (1.76, 1.62, 1.62), (0, 0, 0.81), PIEL, cabeza, bisel=0.14)
    for sx in (-1, 1):
        caja('oreja', (0.14, 0.32, 0.42), (sx * 0.92, 0.05, 0.78), PIEL, cabeza, bisel=0.05)
        caja('oreja_int', (0.04, 0.16, 0.24), (sx * 0.99, 0.05, 0.78), PIEL2, cabeza, bisel=0.015)
    caja('nariz', (0.24, 0.22, 0.3), (0, -0.88, 0.7), PIEL2, cabeza, bisel=0.06)
    for sx in (-1, 1):
        caja('mejilla', (0.26, 0.02, 0.12), (sx * 0.56, -0.815, 0.5), mat('rubor', '#e07f78', 0.7), cabeza, bisel=0.01)

    # Ojos, guiño opcional y cejas
    for sx in (-1, 1):
        if pose.get('guino') == sx:
            caja('guino_a', (0.24, 0.05, 0.07), (sx * 0.4 - 0.09, -0.82, 0.99), PUPILA, cabeza, rot=(0, -0.55, 0), bisel=0.02)
            caja('guino_b', (0.24, 0.05, 0.07), (sx * 0.4 + 0.09, -0.82, 0.99), PUPILA, cabeza, rot=(0, 0.55, 0), bisel=0.02)
        else:
            caja('ojo', (0.44, 0.06, 0.42), (sx * 0.4, -0.8, 0.98), OJO_B, cabeza, bisel=0.035)
            caja('parpado', (0.46, 0.07, 0.05), (sx * 0.4, -0.815, 1.2), PIEL2, cabeza, bisel=0.02)
            caja('iris', (0.25, 0.05, 0.31), (sx * 0.37, -0.83, 0.95), IRIS, cabeza, bisel=0.025)
            caja('pupila', (0.12, 0.04, 0.14), (sx * 0.37, -0.85, 0.95), PUPILA, cabeza, bisel=0.01)
            caja('brillo', (0.08, 0.02, 0.08), (sx * 0.37 + 0.06, -0.865, 1.04), BRILLO, cabeza, bisel=0.01)
        sube = pose.get('ceja_sube', {}).get(sx, 0.0)
        caja('ceja', (0.52, 0.1, s['ceja']), (sx * 0.4, -0.82, 1.3 + pose['cejas'] + sube), mat('ceja', '#140d09', 0.5), cabeza,
             rot=(0, -(0.18 * sx if sube else 0), 0), bisel=0.03)

    # Boca sonriente
    caja('boca', (0.6, 0.05, 0.2), (0, -0.8, 0.36), BOCA, cabeza, bisel=0.03)
    for sx in (-1, 1):
        caja('comisura', (0.12, 0.05, 0.14), (sx * 0.33, -0.8, 0.45), BOCA, cabeza, bisel=0.03)
    caja('dientes', (0.46, 0.04, 0.07), (0, -0.825, 0.42), DIENTES, cabeza, bisel=0.015)
    caja('lengua', (0.3, 0.03, 0.07), (0, -0.82, 0.3), LENGUA, cabeza, bisel=0.015)

    pelo(s, cabeza, PELO, rnd)
    if s.get('barba'):
        barba(cabeza, mat('barba', '#0d0806', 0.5, ruido=0.15))
    if s.get('gafas'):
        for sx in (-1, 1):
            cx, cz = sx * 0.4, 0.98
            caja('gafa_sup', (0.58, 0.07, 0.07), (cx, -0.9, cz + 0.24), MONTURA, cabeza, bisel=0.02)
            caja('gafa_inf', (0.58, 0.07, 0.07), (cx, -0.9, cz - 0.24), MONTURA, cabeza, bisel=0.02)
            caja('gafa_ext', (0.07, 0.07, 0.55), (cx + sx * 0.29, -0.9, cz), MONTURA, cabeza, bisel=0.02)
            caja('gafa_int', (0.07, 0.07, 0.55), (cx - sx * 0.29, -0.9, cz), MONTURA, cabeza, bisel=0.02)
            caja('patita', (0.06, 0.95, 0.06), (sx * 0.9, -0.42, cz + 0.2), MONTURA, cabeza, bisel=0.02)
        caja('puente', (0.22, 0.06, 0.06), (0, -0.9, 1.1), MONTURA, cabeza, bisel=0.02)

    # Accesorio en la mano
    if pose.get('calculadora'):
        calc = vacio('calc', (0, -0.25, -0.35), brazos[pose['calculadora']]['mano'])
        calc.rotation_euler = (1.2, 0, 0)
        caja('calc_cuerpo', (0.62, 0.12, 0.85), (0, 0, 0), CALC, calc, bisel=0.04)
        caja('calc_pantalla', (0.5, 0.03, 0.2), (0, -0.065, 0.26), PANTALLA, calc, bisel=0.015)
        for i in range(3):
            for j in range(4):
                caja('tecla', (0.1, 0.03, 0.08), (-0.16 + j * 0.107, -0.065, 0.06 - i * 0.12), TEAL if j == 3 else BLANCO, calc, bisel=0.01)

    # Pose: hombro (x, y), codo (x, y, z)
    for lado in ('der', 'izq'):
        b = brazos[lado]; p = pose[lado]
        b['hombro'].rotation_euler = (p[0], p[1], 0)
        b['codo'].rotation_euler = (p[2], p[3] if len(p) > 3 else 0, p[4] if len(p) > 4 else 0)
    if pose.get('pulgar_arriba'):
        b = brazos[pose['pulgar_arriba']]
        b['pulgar'].location = (0, -0.24, 0.02); b['pulgar'].rotation_euler = (math.pi, 0, 0)
    cabeza.rotation_euler = pose.get('cabeza', (0, 0, 0))
    return raiz

POSES = [
    # Centro: puño al frente, el otro brazo relajado
    dict(der=(-0.7, 0.06, -0.95, 0, -0.15), izq=(0.0, -0.12, -0.1, 0), cabeza=(0.03, 0, -0.03), cejas=0.04),
    # Izquierda: puño en alto hacia el centro y la otra mano en el bolsillo
    dict(der=(0.0, 0.14, 0, -0.65), izq=(0.0, -0.45, 0, -2.55), cabeza=(0, 0, 0.06), cejas=0.06),
    # Derecha: puño en alto hacia afuera y la otra mano en el bolsillo
    dict(der=(0.0, 0.14, 0, -0.65), izq=(0.0, -0.45, 0, -2.55), cabeza=(0.02, 0, -0.04), cejas=0.06),
]
POSICIONES = [(0, -0.5, 0), (-2.6, 0.3, 0.22), (2.6, 0.3, -0.22)]

for s, (x, y, g), pose in zip(SOCIOS, POSICIONES, POSES):
    personaje(s, x, y, g, pose)

# ---------------------------------------------------------------- set y luces
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=5.6, depth=0.3, location=(0, 0, -0.15))
bpy.context.object.data.materials.append(mat('tarima', '#13304d', 0.3))
bpy.ops.mesh.primitive_torus_add(major_radius=5.6, minor_radius=0.05, major_segments=160, location=(0, 0, 0.0))
bpy.context.object.data.materials.append(mat('aro', '#7fe3f5', 0.3, emision=5.0))
bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, -0.3))
bpy.context.object.data.materials.append(mat('piso', '#050b14', 0.4))
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 13, 40), rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(mat('pared', '#0a3d6b', 0.85))

def luz(nombre, loc, apunta, potencia, color='#ffffff', tam=4.0):
    l = bpy.data.lights.new(nombre, 'AREA'); l.energy = potencia; l.color = hex2rgb(color)[:3]; l.shape = 'DISK'; l.size = tam
    o = bpy.data.objects.new(nombre, l); scene.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(apunta) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

luz('clave', (-6, -10, 9), (0, 0, 2.8), 4200, '#ffe8d2', 7)
luz('relleno', (8, -9, 4), (0, 0, 2.6), 1100, '#fff2e6', 9)
luz('borde_cian', (7, 5, 5), (0, 0, 3), 2400, '#56d6ff', 5)
luz('borde_rojo', (-8, 4, 3), (0, 0, 2.5), 2200, '#ff3d63', 5)
luz('piso_rojo', (-7, -4, 0.6), (-3, 0, 0), 900, '#ff3d63', 4)
luz('pared', (0, 4, 10), (0, 13, 7), 900, '#3f8fe0', 12)
luz('cenital', (0, -2, 12), (0, 0, 0), 500, '#ffffff', 10)

world = bpy.data.worlds.new('mundo'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = hex2rgb('#203a52')
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5

# ---------------------------------------------------------------- cámara y render
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
if RETRATO is not None:
    x, y, _ = POSICIONES[int(RETRATO)]
    cam_d.lens = 70
    cam.location = (x + 0.35, y - 12.0, 5.0)
    objetivo = Vector((x, y, 3.95))
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1080
else:
    cam_d.lens = 50
    cam.location = (0, -15.4, 4.7)
    objetivo = Vector((0, 0, 2.85))
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1350
cam.rotation_euler = (objetivo - cam.location).to_track_quat('-Z', 'Y').to_euler()

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = MUESTRAS
scene.cycles.use_adaptive_sampling = True
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles_curves.shape = 'THICK'
scene.cycles_curves.subdivisions = 2
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Punchy'
scene.render.filepath = SALIDA
scene.render.image_settings.file_format = 'PNG'

if BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(BLEND).resolve()))
bpy.ops.render.render(write_still=True)
print('listo:', SALIDA)
