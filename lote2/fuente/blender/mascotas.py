"""Mascotas de Axios en Blender: tres personajes en bloques detallados, uno por socio.

Uso (sin interfaz):
  blender -b -P mascotas.py -- --salida equipo.png [--retrato 0|1|2] [--muestras 96] [--blend mascotas.blend]

Estilo: bloques con bordes biselados, materiales físicos (piel con translucidez, tela,
jean, metal) e iluminación de estudio con Cycles. Los rasgos de cada socio se toman de
fotos de referencia que no se guardan en el repositorio.
"""
import math
import random
import sys
from pathlib import Path

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

# ---------------------------------------------------------------- escena limpia
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def hex2rgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1,)

_mats = {}
def mat(nombre, color, rough=0.6, sss=0.0, sheen=0.0, metal=0.0, emision=0.0, ruido=0.0):
    if nombre in _mats:
        return _mats[nombre]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    p = n['Principled BSDF']
    p.inputs['Base Color'].default_value = hex2rgb(color)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
        p.inputs['Subsurface Scale'].default_value = 0.08
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen
    if emision:
        p.inputs['Emission Color'].default_value = hex2rgb(color)
        p.inputs['Emission Strength'].default_value = emision
    if ruido:
        # Variación sutil de tono (tela, jean) para que no se vea plástico
        tex = n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 40; tex.inputs['Detail'].default_value = 8
        rmp = n.new('ShaderNodeMix'); rmp.data_type = 'RGBA'; rmp.blend_type = 'MULTIPLY'
        rmp.inputs['Factor'].default_value = ruido
        rmp.inputs['A'].default_value = hex2rgb(color)
        l.new(tex.outputs['Color'], rmp.inputs['B'])
        l.new(rmp.outputs['Result'], p.inputs['Base Color'])
        bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08
        l.new(tex.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs['Normal'], p.inputs['Normal'])
    _mats[nombre] = m
    return m

def vacio(nombre, loc=(0, 0, 0), padre=None):
    e = bpy.data.objects.new(nombre, None)
    scene.collection.objects.link(e)
    e.parent = padre; e.location = loc
    return e

def caja(nombre, tam, loc, material, padre=None, rot=(0, 0, 0), bisel=None):
    """Caja con medidas reales (escala aplicada) y bisel proporcional."""
    me = bpy.data.meshes.new(nombre)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    me.transform(Matrix.Diagonal((tam[0], tam[1], tam[2], 1)))
    ob = bpy.data.objects.new(nombre, me)
    scene.collection.objects.link(ob)
    ob.parent = padre; ob.location = loc; ob.rotation_euler = rot
    ob.data.materials.append(material)
    b = ob.modifiers.new('bisel', 'BEVEL')
    b.width = bisel if bisel is not None else min(0.06, min(tam) * 0.18)
    b.segments = 3; b.limit_method = 'NONE'
    for f in me.polygons: f.use_smooth = True
    return ob

def texto(nombre, cuerpo, tam, loc, material, padre=None, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(nombre, 'FONT')
    cu.body = cuerpo; cu.size = tam; cu.extrude = 0.012; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    fuente = AQUI / 'Poppins-Bold.ttf'
    if fuente.exists():
        cu.font = bpy.data.fonts.load(str(fuente), check_existing=True)
    ob = bpy.data.objects.new(nombre, cu)
    scene.collection.objects.link(ob)
    ob.parent = padre; ob.location = loc; ob.rotation_euler = rot
    ob.data.materials.append(material)
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
ORO = mat('oro', '#e2b44f', 0.22, metal=1.0)
PLATA = mat('plata', '#d6dbe2', 0.2, metal=1.0)
MONTURA = mat('montura', '#0d1117', 0.2)
CINTURON = mat('cinturon', '#3a2618', 0.45)
HEBILLA = mat('hebilla', '#c9ced6', 0.25, metal=1.0)
JEAN = mat('jean', '#3f6596', 0.85, ruido=0.25)
ROJO = mat('rojo_axios', '#c8102e', 0.4)
TEAL = mat('teal_axios', '#13808a', 0.45)
TEAL_BRILLO = mat('teal_brillo', '#4fc3cf', 0.3, emision=4.0)
CALC = mat('calculadora', '#1f2733', 0.4)
COSTURA = mat('costura', '#c9a25a', 0.6)
JEAN_OSC = mat('jean_osc', '#2f4f7a', 0.85, ruido=0.2)
PANTALLA = mat('pantalla', '#9fe3e9', 0.2, emision=1.2)

# ---------------------------------------------------------------- personajes
SOCIOS = [
    dict(nombre='socio1', piel='#d39a6e', pelo='#2a1a11', ojos='#4a2c18', camisa='#1e2127', manga='larga',
         peinado='ondulado', cadena='oro', pin=True, ancho=1.08, ceja=0.17, semilla=11),
    dict(nombre='socio2', piel='#a8704a', pelo='#16100c', ojos='#3a2414', camisa='#1b1d22', manga='corta',
         peinado='rizado', gafas=True, cadena='plata', cruz=True, ancho=0.94, ceja=0.12, semilla=5),
    dict(nombre='socio3', piel='#c18a5e', pelo='#1b130e', ojos='#3d2616', camisa='#1b1d22', manga='corta',
         peinado='gorra', gorra='#6f4b31', texto='AXIOS', manilla=True, ancho=1.04, ceja=0.13, semilla=3),
]

def personaje(s, x, y, giro, pose):
    rnd = random.Random(s['semilla'])
    PIEL = mat(f"piel_{s['nombre']}", s['piel'], 0.5, sss=0.15)
    PIEL2 = mat(f"piel2_{s['nombre']}", s['piel'], 0.55, sss=0.1)
    PIEL2.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = tuple(c * 0.82 for c in hex2rgb(s['piel'])[:3]) + (1,)
    PELO = mat(f"pelo_{s['nombre']}", s['pelo'], 0.42, sheen=0.4)
    CAMISA = mat(f"camisa_{s['nombre']}", s['camisa'], 0.8, sheen=0.5, ruido=0.12)
    DET = mat(f"detalle_{s['nombre']}", '#3a3f48', 0.6)
    IRIS = mat(f"iris_{s['nombre']}", s['ojos'], 0.2)
    w = s['ancho']

    raiz = vacio(s['nombre'], (x, y, 0)); raiz.rotation_euler = (0, 0, giro)

    # Zapatos y piernas
    for sx in (-1, 1):
        caja('zapato', (0.62, 0.92, 0.3), (sx * 0.4 * w, -0.1, 0.2), BLANCO, raiz)
        caja('suela', (0.66, 0.96, 0.1), (sx * 0.4 * w, -0.1, 0.05), SUELA, raiz, bisel=0.03)
        caja('cordones', (0.36, 0.3, 0.04), (sx * 0.4 * w, -0.32, 0.36), SUELA, raiz, bisel=0.015)
        caja('franja', (0.04, 0.5, 0.1), (sx * (0.4 * w + 0.315), -0.12, 0.22), TEAL, raiz, bisel=0.012)
        caja('pierna', (0.6 * w, 0.62, 1.05), (sx * 0.36 * w, 0, 0.86), JEAN, raiz)
        caja('costura', (0.03, 0.025, 0.95), (sx * (0.36 * w + 0.302 * w), 0, 0.9), COSTURA, raiz, bisel=0.008)
        caja('ruedo', (0.62 * w, 0.64, 0.08), (sx * 0.36 * w, 0, 0.38), JEAN_OSC, raiz, bisel=0.02)
    caja('cadera', (1.46 * w, 0.74, 0.42), (0, 0, 1.52), JEAN, raiz)
    caja('cinturon', (1.5 * w, 0.78, 0.13), (0, 0, 1.68), CINTURON, raiz, bisel=0.03)
    caja('hebilla', (0.24, 0.06, 0.15), (0, -0.41, 1.68), HEBILLA, raiz, bisel=0.02)

    # Torso
    torso = vacio('torso', (0, 0, 1.72), raiz)
    caja('camisa', (1.62 * w, 0.88, 1.42), (0, 0, 0.7), CAMISA, torso, bisel=0.09)
    caja('cuello_piel', (0.52, 0.46, 0.3), (0, 0, 1.48), PIEL2, torso)
    caja('cuello_tela', (0.74, 0.62, 0.1), (0, 0, 1.4), CAMISA, torso, bisel=0.04)
    if s['manga'] == 'larga':
        for sx in (-1, 1):
            caja('solapa', (0.34, 0.08, 0.3), (sx * 0.2, -0.45, 1.3), CAMISA, torso, rot=(0.3, 0, sx * 0.5), bisel=0.03)
        caja('tapeta', (0.1, 0.03, 1.15), (0, -0.452, 0.66), DET, torso, bisel=0.012)
        for i in range(4):
            caja('boton', (0.06, 0.03, 0.06), (0, -0.47, 1.08 - i * 0.28), DET, torso, bisel=0.012)
    if s.get('pin'):
        caja('pin', (0.12, 0.04, 0.12), (-0.45 * w, -0.46, 1.0), ROJO, torso, bisel=0.02)
    if s.get('texto'):
        texto('estampado', s['texto'], 0.32, (0, -0.452, 0.82), BLANCO, torso)
    if s.get('cadena'):
        metal = ORO if s['cadena'] == 'oro' else PLATA
        for i in range(15):
            a = -1.15 + i * (2.3 / 14)
            caja('eslabon', (0.06, 0.04, 0.045), (math.sin(a) * 0.34, -0.45, 1.3 - math.cos(a) * 0.28 + 0.12), metal, torso, rot=(0, -a, 0), bisel=0.012)
        if s.get('cruz'):
            caja('cruz_v', (0.05, 0.03, 0.2), (0, -0.465, 1.0), metal, torso, bisel=0.01)
            caja('cruz_h', (0.14, 0.03, 0.05), (0, -0.465, 1.04), metal, torso, bisel=0.01)

    # Brazos con pivotes en hombro, codo y muñeca
    brazos = {}
    for lado, sx in (('der', -1), ('izq', 1)):
        hombro = vacio(f'hombro_{lado}', (sx * (0.81 * w + 0.27), 0, 1.28), torso)
        caja('manga', (0.54, 0.58, 0.72), (0, 0, -0.3), CAMISA, hombro, bisel=0.07)
        if s['manga'] == 'corta':
            caja('ruedo_manga', (0.56, 0.6, 0.07), (0, 0, -0.64), DET, hombro, bisel=0.02)
        codo = vacio(f'codo_{lado}', (0, 0, -0.64), hombro)
        larga = s['manga'] == 'larga'
        caja('antebrazo', (0.44, 0.48, 0.62), (0, 0, -0.3), CAMISA if larga else PIEL, codo)
        if larga:
            caja('puno', (0.48, 0.52, 0.1), (0, 0, -0.6), DET, codo, bisel=0.02)
        if s.get('manilla') and sx == 1:
            caja('manilla', (0.5, 0.54, 0.1), (0, 0, -0.5), TEAL, codo, bisel=0.03)
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

    # Ojos con brillo y cejas
    for sx in (-1, 1):
        guino = pose.get('guino') == sx
        if guino:
            # Ojo cerrado en forma de ^ (guiño)
            caja('guino_a', (0.24, 0.05, 0.07), (sx * 0.4 - 0.09, -0.82, 0.99), PUPILA, cabeza, rot=(0, -0.55, 0), bisel=0.02)
            caja('guino_b', (0.24, 0.05, 0.07), (sx * 0.4 + 0.09, -0.82, 0.99), PUPILA, cabeza, rot=(0, 0.55, 0), bisel=0.02)
        else:
            caja('ojo', (0.38, 0.06, 0.36), (sx * 0.4, -0.8, 0.98), OJO_B, cabeza, bisel=0.03)
            caja('parpado', (0.4, 0.07, 0.06), (sx * 0.4, -0.815, 1.17), PIEL2, cabeza, bisel=0.02)
            caja('iris', (0.22, 0.05, 0.26), (sx * 0.37, -0.83, 0.96), IRIS, cabeza, bisel=0.02)
            caja('pupila', (0.12, 0.04, 0.14), (sx * 0.37, -0.85, 0.95), PUPILA, cabeza, bisel=0.01)
            caja('brillo', (0.07, 0.02, 0.07), (sx * 0.37 + 0.06, -0.865, 1.03), BRILLO, cabeza, bisel=0.01)
        sube = pose.get('ceja_sube', {}).get(sx, 0.0)
        caja('ceja', (0.48, 0.1, s['ceja']), (sx * 0.4, -0.82, 1.3 + pose['cejas'] + sube), PELO, cabeza,
             rot=(0, sx * pose.get('ceja_giro', 0.0) - (0.18 * sx if sube else 0), 0), bisel=0.03)

    # Boca sonriente en bloques
    if pose.get('boca') == 'picara':
        # Media sonrisa: un lado sube más que el otro
        caja('boca', (0.5, 0.05, 0.12), (0.04, -0.8, 0.38), BOCA, cabeza, rot=(0, -0.12, 0), bisel=0.03)
        caja('comisura', (0.12, 0.05, 0.12), (0.31, -0.8, 0.48), BOCA, cabeza, bisel=0.03)
        caja('dientes', (0.36, 0.04, 0.05), (0.05, -0.825, 0.41), DIENTES, cabeza, rot=(0, -0.12, 0), bisel=0.012)
    else:
        caja('boca', (0.6, 0.05, 0.2), (0, -0.8, 0.36), BOCA, cabeza, bisel=0.03)
        for sx in (-1, 1):
            caja('comisura', (0.12, 0.05, 0.14), (sx * 0.33, -0.8, 0.45), BOCA, cabeza, bisel=0.03)
        caja('dientes', (0.46, 0.04, 0.07), (0, -0.825, 0.42), DIENTES, cabeza, bisel=0.015)
        caja('lengua', (0.3, 0.03, 0.07), (0, -0.82, 0.3), LENGUA, cabeza, bisel=0.015)

    # Pelo
    if s['peinado'] in ('ondulado', 'rizado'):
        caja('pelo_tapa', (1.86, 1.72, 0.32), (0, 0.02, 1.66), PELO, cabeza, bisel=0.1)
        caja('pelo_nuca', (1.86, 0.34, 1.05), (0, 0.72, 1.12), PELO, cabeza, bisel=0.08)
        for sx in (-1, 1):
            caja('patilla', (0.14, 0.9, 0.62), (sx * 0.9, 0.24, 1.22), PELO, cabeza, bisel=0.05)
        caja('frente', (1.8, 0.2, 0.24), (0, -0.78, 1.55), PELO, cabeza, bisel=0.07)
    if s['peinado'] == 'ondulado':
        # Copete ondulado hacia arriba y atrás, con mechones irregulares
        caja('copete_1', (1.5, 0.62, 0.34), (0, -0.55, 1.86), PELO, cabeza, rot=(-0.35, 0, 0), bisel=0.12)
        caja('copete_2', (1.2, 0.5, 0.3), (0.05, -0.48, 2.08), PELO, cabeza, rot=(-0.55, 0, 0.06), bisel=0.11)
        caja('copete_3', (0.7, 0.36, 0.22), (0.1, -0.62, 2.22), PELO, cabeza, rot=(-0.8, 0, 0.1), bisel=0.08)
        for _ in range(9):
            caja('mechon', (rnd.uniform(0.32, 0.55), rnd.uniform(0.32, 0.5), rnd.uniform(0.16, 0.28)),
                 (rnd.uniform(-0.75, 0.75), rnd.uniform(-0.3, 0.75), rnd.uniform(1.8, 2.0)), PELO, cabeza,
                 rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.25, 0.25), rnd.uniform(-0.4, 0.4)), bisel=0.07)
        # Onda grande del copete, peinada hacia arriba y un poco a un lado
        caja('onda_1', (1.35, 0.6, 0.3), (0.08, -0.5, 2.12), PELO, cabeza, rot=(-0.62, 0, -0.08), bisel=0.12)
        caja('onda_2', (1.05, 0.52, 0.28), (0.16, -0.42, 2.33), PELO, cabeza, rot=(-0.8, 0, -0.14), bisel=0.11)
        caja('onda_3', (0.62, 0.42, 0.22), (0.3, -0.52, 2.46), PELO, cabeza, rot=(-1.0, 0, -0.22), bisel=0.08)
    if s['peinado'] == 'rizado':
        # Rizos: muchos bloques pequeños con alturas y giros variados
        for ix in range(7):
            for iy in range(6):
                px = -0.81 + ix * 0.27; py = -0.62 + iy * 0.27
                for capa in range(2 if rnd.random() < 0.6 else 1):
                    t = rnd.uniform(0.24, 0.34)
                    caja('rizo', (t, t, t), (px + rnd.uniform(-0.05, 0.05), py + rnd.uniform(-0.05, 0.05), 1.86 + capa * 0.2 + rnd.uniform(0, 0.16)),
                         PELO, cabeza, rot=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.8, 0.8)), bisel=0.07)
        for sx in (-1, 1):
            for k in range(5):
                t = rnd.uniform(0.22, 0.3)
                caja('rizo_lado', (t, t, t), (sx * 0.95, -0.4 + k * 0.28, 1.5 + rnd.uniform(-0.05, 0.12)), PELO, cabeza,
                     rot=(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6)), bisel=0.06)
    if s['peinado'] == 'gorra':
        GORRA = mat(f"gorra_{s['nombre']}", s['gorra'], 0.75, sheen=0.3, ruido=0.15)
        GORRA2 = mat(f"gorra2_{s['nombre']}", s['gorra'], 0.7)
        GORRA2.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = tuple(c * 0.6 for c in hex2rgb(s['gorra'])[:3]) + (1,)
        caja('pelo_nuca', (1.84, 0.3, 0.7), (0, 0.72, 1.0), PELO, cabeza, bisel=0.06)
        for sx in (-1, 1):
            caja('patilla', (0.12, 0.7, 0.42), (sx * 0.9, 0.2, 1.18), PELO, cabeza, bisel=0.04)
        caja('gorra', (1.92, 1.82, 0.62), (0, 0.04, 1.72), GORRA, cabeza, bisel=0.2)
        caja('gorra_banda', (1.95, 1.85, 0.1), (0, 0.04, 1.43), GORRA2, cabeza, bisel=0.04)
        caja('visera', (1.56, 0.92, 0.09), (0, -1.22, 1.46), GORRA2, cabeza, rot=(0.12, 0, 0), bisel=0.04)
        caja('boton_gorra', (0.16, 0.16, 0.08), (0, 0.04, 2.05), GORRA2, cabeza, bisel=0.03)
        caja('parche', (0.5, 0.04, 0.36), (0, -0.93, 1.74), TEAL, cabeza, bisel=0.04)
        texto('parche_a', 'A', 0.28, (0, -0.955, 1.73), BLANCO, cabeza)
    if s.get('gafas'):
        for sx in (-1, 1):
            cx, cz = sx * 0.4, 0.98
            caja('gafa_sup', (0.58, 0.07, 0.07), (cx, -0.9, cz + 0.24), MONTURA, cabeza, bisel=0.02)
            caja('gafa_inf', (0.58, 0.07, 0.07), (cx, -0.9, cz - 0.24), MONTURA, cabeza, bisel=0.02)
            caja('gafa_ext', (0.07, 0.07, 0.55), (cx + sx * 0.29, -0.9, cz), MONTURA, cabeza, bisel=0.02)
            caja('gafa_int', (0.07, 0.07, 0.55), (cx - sx * 0.29, -0.9, cz), MONTURA, cabeza, bisel=0.02)
            caja('patita', (0.06, 0.95, 0.06), (sx * 0.9, -0.42, cz + 0.2), MONTURA, cabeza, bisel=0.02)
        caja('puente', (0.22, 0.06, 0.06), (0, -0.9, 1.1), MONTURA, cabeza, bisel=0.02)

    # Accesorio opcional en la mano
    if pose.get('calculadora'):
        calc = vacio('calc', (0, -0.25, -0.35), brazos[pose['calculadora']]['mano'])
        calc.rotation_euler = (1.2, 0, 0)
        caja('calc_cuerpo', (0.62, 0.12, 0.85), (0, 0, 0), CALC, calc, bisel=0.04)
        caja('calc_pantalla', (0.5, 0.03, 0.2), (0, -0.065, 0.26), PANTALLA, calc, bisel=0.015)
        for i in range(3):
            for j in range(4):
                caja('tecla', (0.1, 0.03, 0.08), (-0.16 + j * 0.107, -0.065, 0.06 - i * 0.12), TEAL if j == 3 else BLANCO, calc, bisel=0.01)

    # Pose
    for lado in ('der', 'izq'):
        b = brazos[lado]; p = pose[lado]
        b['hombro'].rotation_euler = (p[0], p[1], 0)
        b['codo'].rotation_euler = (p[2], p[3] if len(p) > 3 else 0, p[4] if len(p) > 4 else 0)
    if pose.get('pulgar_arriba'):
        lado = pose['pulgar_arriba']
        b = brazos[lado]
        b['pulgar'].location = (0, -0.24, 0.02); b['pulgar'].rotation_euler = (math.pi, 0, 0)
    cabeza.rotation_euler = pose.get('cabeza', (0, 0, 0))
    torso.rotation_euler = (0, 0, pose.get('torso_giro', 0))
    return raiz

# Poses: [hombro_x, hombro_y, codo_x, codo_y]; x negativo = adelante, y lateral (signo según el lado)
POSES = [
    # Socio 1 (centro): manos en la cintura, seguro de sí mismo
    dict(der=(-0.25, -0.05, -1.45, 0, 1.5), izq=(-0.3, 0.05, -1.65, 0, -1.5), cabeza=(0.03, 0, -0.06), cejas=0.04,
         boca='picara', ceja_sube={1: 0.08}),
    # Socio 2 (izquierda): saluda con la mano, sostiene la calculadora con la otra
    dict(der=(0.0, 0.45, 0, 2.55), izq=(-0.75, -0.15, -1.15, 0), cabeza=(0, 0, 0.07), cejas=0.08, calculadora='izq'),
    # Socio 3 (derecha): pulgar arriba
    dict(der=(0.0, 0.12, 0, 0), izq=(-1.25, 0.15, -1.35, 0), cabeza=(0.02, 0, 0.06), cejas=0.07, pulgar_arriba='izq', guino=-1),
]
POSICIONES = [(0, -0.5, 0), (-2.65, 0.3, 0.25), (2.65, 0.3, -0.25)]

for s, (x, y, g), pose in zip(SOCIOS, POSICIONES, POSES):
    personaje(s, x, y, g, pose)

# ---------------------------------------------------------------- set y luces
piso_mat = mat('piso', '#0f3550', 0.35)
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=5.6, depth=0.3, location=(0, 0, -0.15))
bpy.context.object.data.materials.append(piso_mat)
bpy.ops.mesh.primitive_torus_add(major_radius=5.6, minor_radius=0.04, major_segments=160, location=(0, 0, 0.0))
bpy.context.object.data.materials.append(TEAL_BRILLO)
import bmesh
perfil = [(y, -0.3) for y in (-30, 6)] + [(6 + 6 * math.sin(a), -0.3 + 6 - 6 * math.cos(a)) for a in [i * math.pi / 2 / 12 for i in range(1, 13)]] + [(12, 30)]
me = bpy.data.meshes.new('ciclorama'); bm = bmesh.new()
izq_v = [bm.verts.new((-40, y, z)) for y, z in perfil]; der_v = [bm.verts.new((40, y, z)) for y, z in perfil]
for i in range(len(perfil) - 1):
    bm.faces.new((izq_v[i], der_v[i], der_v[i + 1], izq_v[i + 1]))
bm.to_mesh(me); bm.free()
for f in me.polygons: f.use_smooth = True
cic = bpy.data.objects.new('ciclorama', me); scene.collection.objects.link(cic)
cic.data.materials.append(mat('suelo', '#0b2238', 0.55))
letrero = texto('fondo_axios', 'AXIOS', 3.4, (0, 11.6, 8.1), mat('letrero', '#13808a', 0.45, emision=0.2))

def luz(nombre, tipo, loc, apunta, potencia, color='#ffffff', tam=4.0):
    l = bpy.data.lights.new(nombre, tipo); l.energy = potencia; l.color = hex2rgb(color)[:3]
    if tipo == 'AREA':
        l.shape = 'DISK'; l.size = tam
    o = bpy.data.objects.new(nombre, l); scene.collection.objects.link(o); o.location = loc
    d = Vector(apunta) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o

luz('clave', 'AREA', (-7, -10, 10), (0, 0, 2.5), 3400, '#fff4ea', 7)
luz('relleno', 'AREA', (8, -9, 4), (0, 0, 2.5), 1300, '#e6f2ff', 9)
luz('borde_teal', 'AREA', (7, 7, 7), (0, 0, 3), 1800, '#4fc3cf', 5)
luz('borde_rojo', 'AREA', (-8, 6, 6), (0, 0, 3), 900, '#ff5c6c', 5)
luz('cenital', 'AREA', (0, -2, 12), (0, 0, 0), 600, '#ffffff', 10)

# Fondo: degradado azul de la marca visto por la cámara; luz ambiental tenue
world = bpy.data.worlds.new('mundo'); scene.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
bg = wn['Background']
coord = wn.new('ShaderNodeTexCoord'); sep = wn.new('ShaderNodeSeparateXYZ'); ramp = wn.new('ShaderNodeValToRGB')
wl.new(coord.outputs['Window'], sep.inputs['Vector']); wl.new(sep.outputs['Y'], ramp.inputs['Fac'])
ramp.color_ramp.elements[0].color = hex2rgb('#061423'); ramp.color_ramp.elements[1].color = hex2rgb('#1a5a80')
ramp.color_ramp.elements[1].position = 0.75
amb = wn.new('ShaderNodeBackground'); amb.inputs['Color'].default_value = hex2rgb('#203a52'); amb.inputs['Strength'].default_value = 0.6
cam_bg = wn.new('ShaderNodeBackground'); wl.new(ramp.outputs['Color'], cam_bg.inputs['Color'])
lp = wn.new('ShaderNodeLightPath'); mix = wn.new('ShaderNodeMixShader')
wl.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac']); wl.new(amb.outputs['Background'], mix.inputs[1]); wl.new(cam_bg.outputs['Background'], mix.inputs[2])
wl.new(mix.outputs['Shader'], wn['World Output'].inputs['Surface'])

# ---------------------------------------------------------------- cámara y render
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
if RETRATO is not None:
    i = int(RETRATO); x, y, _ = POSICIONES[i]
    cam_d.lens = 70
    cam.location = (x + 0.35, y - 12.0, 5.0)
    objetivo = Vector((x, y, 3.95))
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1080
else:
    cam_d.lens = 50
    cam.location = (0, -15.8, 4.6)
    objetivo = Vector((0, 0, 2.75))
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1350
cam.rotation_euler = (objetivo - cam.location).to_track_quat('-Z', 'Y').to_euler()

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = MUESTRAS
scene.cycles.use_adaptive_sampling = True
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.film_transparent = False
scene.render.filepath = SALIDA
scene.render.image_settings.file_format = 'PNG'

if BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(BLEND).resolve()))
bpy.ops.render.render(write_still=True)
print('listo:', SALIDA)
