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
        l.new(tex.outputs['Color'], mx.inputs['B']); l.new(mx.outputs['Result'], p.inputs['Base Color'])
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
}
ZAPATOS = {
    'tenis': (BLANCO, SUELA),
    'cuero_cafe': (mat('cuero_cafe', '#5b3520', 0.35), mat('suela_cafe', '#2a1a10', 0.5)),
    'cuero_negro': (mat('cuero_negro', '#16181c', 0.3), mat('suela_negra', '#0c0d10', 0.5)),
}

# ---------------------------------------------------------------- personajes
SOCIOS = [
    # Usted: camisa de vestir blanca con símbolo AX y lapicero dorado; copete peinado de lado; barba de candado
    dict(nombre='socio1', piel='#d39a6e', pelo='#241712', ojos='#4a2c18', atuendo='camisa_vestir', pantalon='chino',
         zapato='cuero_cafe', peinado='copete', barba=True, ancho=1.1, ceja=0.18, semilla=11),
    # Socio de rizos y gafas: buso negro con capucha, cordones, bolsillo canguro y logo AX
    dict(nombre='socio2', piel='#a8704a', pelo='#18110c', ojos='#3a2414', atuendo='buso', pantalon='jean',
         zapato='tenis', peinado='rizado', gafas=True, ancho=0.96, ceja=0.12, semilla=5),
    # Socio de gorra, en versión profesional: blazer azul, camisa celeste, corbata verde azulado
    dict(nombre='socio3', piel='#c18a5e', pelo='#1b130e', ojos='#3d2616', atuendo='blazer', pantalon='gris',
         zapato='cuero_negro', peinado='corto', ancho=1.04, ceja=0.13, semilla=3),
]

def pelo(s, cabeza, PELO, rnd):
    """Pelo hecho de mechones. La cabeza ocupa x ±0.88, y ±0.81 (frente en -y), z 0..1.62."""
    est = s['peinado']
    # Base que evita huecos entre mechones
    caja('pelo_tapa', (1.82, 1.68, 0.16), (0, 0.03, 1.66), PELO, cabeza, bisel=0.07)
    caja('pelo_nuca', (1.82, 0.18, 0.95), (0, 0.8, 1.15), PELO, cabeza, bisel=0.06)
    for sx in (-1, 1):
        caja('pelo_lado', (0.08, 1.0, 0.55 if est != 'rizado' else 0.75), (sx * 0.9, 0.22, 1.32), PELO, cabeza, bisel=0.03)

    if est == 'copete':
        # Raya al lado (x = -0.42); el pelo sube en la frente y se peina hacia atrás y hacia la derecha
        raya = -0.42
        for ix in range(8):
            for iy in range(6):
                x = -0.78 + ix * 0.22 + rnd.uniform(-0.03, 0.03); y = -0.66 + iy * 0.26 + rnd.uniform(-0.03, 0.03)
                if abs(x - raya) < 0.06:
                    continue
                frente = max(0.0, (0.1 - y) / 0.8)
                if x > raya:
                    d = (0.32 + 0.25 * frente, 1.0, 0.45 * frente - 0.12)
                else:
                    d = (-0.55, 0.75, -0.25)
                mechon('mechon', rnd.uniform(0.5, 0.68), rnd.uniform(0.26, 0.32), rnd.uniform(0.12, 0.15),
                       (x, y, 1.72 + 0.16 * frente + rnd.uniform(0, 0.04)), d, (0, 0, 1), PELO, cabeza,
                       curva=-rnd.uniform(0.35, 0.6), giro=rnd.uniform(-0.15, 0.15))
        # Copete delantero: mechones grandes que suben desde la frente
        for k in range(6):
            x = raya + 0.14 + k * 0.2
            mechon('copete', rnd.uniform(0.62, 0.75), 0.3, 0.17, (x, -0.8, 1.66 + k * 0.012),
                   (0.28 + k * 0.03, 0.55, 0.85), (0, -0.4, 1), PELO, cabeza, curva=-0.75, giro=rnd.uniform(-0.1, 0.1))
        for k in range(2):
            mechon('copete_izq', 0.45, 0.26, 0.14, (raya - 0.12 - k * 0.2, -0.8, 1.64), (-0.45, 0.6, 0.55), (0, -0.4, 1),
                   PELO, cabeza, curva=-0.6)

    if est == 'rizado':
        # Rizos: mechones cortos muy curvados en capas
        for _ in range(110):
            x = rnd.uniform(-0.86, 0.86); y = rnd.uniform(-0.78, 0.8)
            z = 1.66 + rnd.uniform(0, 0.32) * (1 - abs(x) * 0.35)
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 0.8)))
            mechon('rizo', rnd.uniform(0.24, 0.34), rnd.uniform(0.18, 0.24), rnd.uniform(0.12, 0.15), (x, y, z), d,
                   (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 1), PELO, cabeza,
                   curva=rnd.choice((-1, 1)) * rnd.uniform(1.6, 2.6), giro=rnd.uniform(-0.6, 0.6))
        for sx in (-1, 1):
            for _ in range(14):
                y = rnd.uniform(-0.45, 0.8); z = rnd.uniform(1.15, 1.65)
                mechon('rizo_lado', rnd.uniform(0.22, 0.3), 0.2, 0.13, (sx * 0.93, y, z),
                       (sx * 0.4, rnd.uniform(-1, 1), rnd.uniform(-1, 0.5)), (sx, 0, 0.3), PELO, cabeza,
                       curva=rnd.choice((-1, 1)) * rnd.uniform(1.6, 2.4))
        for k in range(8):
            x = -0.72 + k * 0.2
            mechon('rizo_frente', 0.26, 0.2, 0.13, (x, -0.8, 1.62 + rnd.uniform(0, 0.08)),
                   (rnd.uniform(-0.5, 0.5), -0.3, 0.9), (0, -1, 0.4), PELO, cabeza, curva=rnd.uniform(1.8, 2.5))

    if est == 'corto':
        # Corte corto y ordenado: mechones cortos peinados hacia adelante y arriba
        for ix in range(8):
            for iy in range(6):
                x = -0.76 + ix * 0.217 + rnd.uniform(-0.02, 0.02); y = -0.62 + iy * 0.27
                mechon('corto', rnd.uniform(0.3, 0.38), 0.24, 0.1, (x, y, 1.7 + rnd.uniform(0, 0.03)),
                       (rnd.uniform(-0.1, 0.1), -1.0, 0.25), (0, 0, 1), PELO, cabeza, curva=rnd.uniform(0.2, 0.35))
        for k in range(7):
            mechon('corto_frente', 0.24, 0.24, 0.11, (-0.66 + k * 0.22, -0.74, 1.66), (0, -0.6, 0.8), (0, -0.5, 1),
                   PELO, cabeza, curva=0.3)

def barba(cabeza, PELO):
    """Barba de candado delgada: línea por la mandíbula, bigote fino y mosca bajo el labio."""
    caja('barba_menton', (1.3, 0.08, 0.11), (0, -0.8, 0.07), PELO, cabeza, bisel=0.03)
    for sx in (-1, 1):
        caja('barba_lado', (0.06, 0.5, 0.52), (sx * 0.895, -0.45, 0.38), PELO, cabeza, rot=(0.4, 0, 0), bisel=0.02)
        caja('barba_quijada', (0.3, 0.08, 0.1), (sx * 0.7, -0.8, 0.15), PELO, cabeza, rot=(0, sx * 0.5, 0), bisel=0.03)
        caja('bigote', (0.22, 0.04, 0.04), (sx * 0.13, -0.835, 0.54), PELO, cabeza, rot=(0, sx * 0.12, 0), bisel=0.015)
    caja('mosca', (0.1, 0.04, 0.08), (0, -0.82, 0.18), PELO, cabeza, bisel=0.02)

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
        plano_imagen('logo_pecho', 0.6, 0.49, (0, -0.452, 0.74), LOGO, torso)
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
        SACO = mat(f"blazer_{s['nombre']}", '#1d2c4a', 0.65, sheen=0.4, ruido=0.1)
        SACO2 = mat(f"blazer2_{s['nombre']}", '#1d2c4a', 0.55, factor=0.75)
        CAM = mat(f"camisa_celeste_{s['nombre']}", '#dbe8f5', 0.6, ruido=0.05)
        caja('cuerpo', (1.64 * w, 0.9, 1.44), (0, 0, 0.7), SACO, torso, bisel=0.09)
        caja('cuello', (0.76, 0.66, 0.13), (0, 0, 1.4), CAM, torso, bisel=0.04)
        # Abertura en V con la camisa y la corbata
        for i, (an, z) in enumerate(((0.56, 1.22), (0.42, 1.03), (0.28, 0.86))):
            caja('camisa_v', (an, 0.03, 0.2), (0, -0.452, z), CAM, torso, bisel=0.01)
        for sx in (-1, 1):
            caja('punta_cuello', (0.3, 0.06, 0.2), (sx * 0.17, -0.47, 1.33), CAM, torso, rot=(0.25, 0, sx * 0.6), bisel=0.025)
            caja('solapa', (0.2, 0.06, 0.72), (sx * 0.25, -0.47, 1.0), SACO2, torso, rot=(0, sx * 0.42, 0), bisel=0.025)
        caja('nudo', (0.17, 0.06, 0.14), (0, -0.48, 1.27), TEAL, torso, bisel=0.03)
        caja('corbata', (0.15, 0.05, 0.5), (0, -0.475, 0.98), TEAL, torso, bisel=0.03)
        for z in (0.58, 0.34):
            caja('boton_saco', (0.08, 0.04, 0.08), (0, -0.47, z), mat('boton_saco', '#0f1626', 0.3), torso, bisel=0.02)
        caja('linea_saco', (0.03, 0.03, 0.7), (0.04, -0.455, 0.42), SACO2, torso, bisel=0.008)
        caja('panuelo', (0.2, 0.05, 0.08), (0.48 * w, -0.47, 1.0), BLANCO, torso, bisel=0.02)
        caja('bolsillo_saco', (0.32, 0.04, 0.04), (0.48 * w, -0.462, 0.95), SACO2, torso, bisel=0.01)
        plano_imagen('pin_ax', 0.14, 0.114, (-0.42 * w, -0.5, 1.1), LOGO, torso)
        for sx in (-1, 1):
            caja('bolsillo_bajo', (0.42, 0.04, 0.05), (sx * 0.46 * w, -0.462, 0.3), SACO2, torso, bisel=0.012)
        return SACO, CAM

def personaje(s, x, y, giro, pose):
    rnd = random.Random(s['semilla'])
    PIEL = mat(f"piel_{s['nombre']}", s['piel'], 0.5, sss=0.15)
    PIEL2 = mat(f"piel2_{s['nombre']}", s['piel'], 0.55, sss=0.1, factor=0.82)
    PELO = mat(f"pelo_{s['nombre']}", s['pelo'], 0.38, sheen=0.5, ruido=0.2)
    IRIS = mat(f"iris_{s['nombre']}", s['ojos'], 0.2)
    w = s['ancho']
    PANT, PANT2, COST = PANTALONES[s['pantalon']]
    ZAP, SUEL = ZAPATOS[s['zapato']]

    raiz = vacio(s['nombre'], (x, y, 0)); raiz.rotation_euler = (0, 0, giro)

    # Zapatos y piernas
    for sx in (-1, 1):
        if s['zapato'] == 'tenis':
            caja('zapato', (0.62, 0.92, 0.3), (sx * 0.4 * w, -0.1, 0.2), ZAP, raiz)
            caja('cordones', (0.36, 0.3, 0.04), (sx * 0.4 * w, -0.32, 0.36), SUEL, raiz, bisel=0.015)
            caja('franja', (0.04, 0.5, 0.1), (sx * (0.4 * w + 0.315), -0.12, 0.22), TEAL, raiz, bisel=0.012)
        else:
            caja('zapato', (0.6, 0.96, 0.24), (sx * 0.4 * w, -0.12, 0.17), ZAP, raiz, bisel=0.09)
            caja('empeine', (0.5, 0.36, 0.1), (sx * 0.4 * w, -0.05, 0.3), ZAP, raiz, bisel=0.04)
        caja('suela', (0.66, 0.98, 0.09), (sx * 0.4 * w, -0.12, 0.045), SUEL, raiz, bisel=0.03)
        caja('pierna', (0.6 * w, 0.62, 1.05), (sx * 0.36 * w, 0, 0.86), PANT, raiz)
        if COST:
            caja('costura', (0.03, 0.025, 0.95), (sx * (0.36 * w + 0.302 * w), 0, 0.9), COST, raiz, bisel=0.008)
        caja('ruedo', (0.62 * w, 0.64, 0.08), (sx * 0.36 * w, 0, 0.38), PANT2, raiz, bisel=0.02)
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
            caja('eslabon', (0.06, 0.04, 0.045), (math.sin(a) * 0.34, -0.48, 1.3 - math.cos(a) * 0.28 + 0.12), metal, torso, rot=(0, -a, 0), bisel=0.012)
        if s.get('cruz'):
            caja('cruz_v', (0.05, 0.03, 0.2), (0, -0.5, 1.0), metal, torso, bisel=0.01)
            caja('cruz_h', (0.14, 0.03, 0.05), (0, -0.5, 1.04), metal, torso, bisel=0.01)

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
            caja('ojo', (0.38, 0.06, 0.36), (sx * 0.4, -0.8, 0.98), OJO_B, cabeza, bisel=0.03)
            caja('parpado', (0.4, 0.07, 0.06), (sx * 0.4, -0.815, 1.17), PIEL2, cabeza, bisel=0.02)
            caja('iris', (0.22, 0.05, 0.26), (sx * 0.37, -0.83, 0.96), IRIS, cabeza, bisel=0.02)
            caja('pupila', (0.12, 0.04, 0.14), (sx * 0.37, -0.85, 0.95), PUPILA, cabeza, bisel=0.01)
            caja('brillo', (0.07, 0.02, 0.07), (sx * 0.37 + 0.06, -0.865, 1.03), BRILLO, cabeza, bisel=0.01)
        sube = pose.get('ceja_sube', {}).get(sx, 0.0)
        caja('ceja', (0.5, 0.1, s['ceja']), (sx * 0.4, -0.82, 1.3 + pose['cejas'] + sube), PELO, cabeza,
             rot=(0, -(0.18 * sx if sube else 0), 0), bisel=0.03)

    # Boca sonriente
    caja('boca', (0.6, 0.05, 0.2), (0, -0.8, 0.36), BOCA, cabeza, bisel=0.03)
    for sx in (-1, 1):
        caja('comisura', (0.12, 0.05, 0.14), (sx * 0.33, -0.8, 0.45), BOCA, cabeza, bisel=0.03)
    caja('dientes', (0.46, 0.04, 0.07), (0, -0.825, 0.42), DIENTES, cabeza, bisel=0.015)
    caja('lengua', (0.3, 0.03, 0.07), (0, -0.82, 0.3), LENGUA, cabeza, bisel=0.015)

    pelo(s, cabeza, PELO, rnd)
    if s.get('barba'):
        barba(cabeza, PELO)
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
    # Usted (centro): explica con la palma abierta; el bolsillo con el lapicero queda a la vista
    dict(der=(-0.7, 0.06, -0.95, 0, -0.15), izq=(0.0, -0.12, -0.1, 0), cabeza=(0.03, 0, -0.04), cejas=0.05, ceja_sube={1: 0.06}),
    # Socio de rizos (izquierda): saluda y sostiene la calculadora
    dict(der=(0.0, 0.45, 0, 2.55), izq=(-0.75, -0.15, -1.15, 0), cabeza=(0, 0, 0.07), cejas=0.08, calculadora='izq'),
    # Socio de blazer (derecha): pulgar arriba y guiño
    dict(der=(0.0, 0.12, 0, 0), izq=(-1.25, 0.15, -1.35, 0), cabeza=(0.02, 0, 0.06), cejas=0.07, pulgar_arriba='izq', guino=-1),
]
POSICIONES = [(0, -0.5, 0), (-2.7, 0.3, 0.25), (2.7, 0.3, -0.25)]

for s, (x, y, g), pose in zip(SOCIOS, POSICIONES, POSES):
    personaje(s, x, y, g, pose)

# ---------------------------------------------------------------- set y luces
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=5.6, depth=0.3, location=(0, 0, -0.15))
bpy.context.object.data.materials.append(mat('piso', '#0f3550', 0.35))
bpy.ops.mesh.primitive_torus_add(major_radius=5.6, minor_radius=0.04, major_segments=160, location=(0, 0, 0.0))
bpy.context.object.data.materials.append(TEAL_BRILLO)

# Ciclorama curvo: piso y fondo sin horizonte
perfil = [(y, -0.3) for y in (-30, 6)] + [(6 + 6 * math.sin(a), -0.3 + 6 - 6 * math.cos(a)) for a in [i * math.pi / 24 for i in range(1, 13)]] + [(12, 30)]
me = bpy.data.meshes.new('ciclorama'); bm = bmesh.new()
izq_v = [bm.verts.new((-40, y, z)) for y, z in perfil]; der_v = [bm.verts.new((40, y, z)) for y, z in perfil]
for i in range(len(perfil) - 1):
    bm.faces.new((izq_v[i], der_v[i], der_v[i + 1], izq_v[i + 1]))
bm.to_mesh(me); bm.free()
for f in me.polygons: f.use_smooth = True
cic = bpy.data.objects.new('ciclorama', me); scene.collection.objects.link(cic)
cic.data.materials.append(mat('suelo', '#0b2238', 0.55))
cu = bpy.data.curves.new('fondo_axios', 'FONT'); cu.body = 'AXIOS'; cu.size = 3.4; cu.extrude = 0.012
cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.font = bpy.data.fonts.load(str(AQUI / 'Poppins-Bold.ttf'), check_existing=True)
letrero = bpy.data.objects.new('fondo_axios', cu); scene.collection.objects.link(letrero)
letrero.location = (0, 11.6, 8.1); letrero.rotation_euler = (math.pi / 2, 0, 0)
letrero.data.materials.append(mat('letrero', '#13808a', 0.45, emision=0.2))

def luz(nombre, loc, apunta, potencia, color='#ffffff', tam=4.0):
    l = bpy.data.lights.new(nombre, 'AREA'); l.energy = potencia; l.color = hex2rgb(color)[:3]; l.shape = 'DISK'; l.size = tam
    o = bpy.data.objects.new(nombre, l); scene.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(apunta) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

luz('clave', (-7, -10, 10), (0, 0, 2.5), 3400, '#fff4ea', 7)
luz('relleno', (8, -9, 4), (0, 0, 2.5), 1300, '#e6f2ff', 9)
luz('borde_teal', (7, 7, 7), (0, 0, 3), 1800, '#4fc3cf', 5)
luz('borde_rojo', (-8, 6, 6), (0, 0, 3), 900, '#ff5c6c', 5)
luz('cenital', (0, -2, 12), (0, 0, 0), 600, '#ffffff', 10)

world = bpy.data.worlds.new('mundo'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = hex2rgb('#203a52')
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6

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
scene.render.filepath = SALIDA
scene.render.image_settings.file_format = 'PNG'

if BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(BLEND).resolve()))
bpy.ops.render.render(write_still=True)
print('listo:', SALIDA)
