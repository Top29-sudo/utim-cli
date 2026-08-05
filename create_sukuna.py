import bpy
import math
import os
from mathutils import Vector, Euler

def create_25d_sukuna():
    # -------------------------------------------------------------------------
    # 1. CLEAN SCENE
    # -------------------------------------------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for collection in bpy.data.collections:
        if collection != bpy.context.scene.collection:
            bpy.data.collections.remove(collection)

    # -------------------------------------------------------------------------
    # 2. RENDER SETTINGS & ENVIRONMENT
    # -------------------------------------------------------------------------
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = False

    # Dark background
    scene.world = bpy.data.worlds.new("SukunaWorld")
    scene.world.use_nodes = True
    bg_node = scene.world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (0.015, 0.015, 0.02, 1.0)

    # -------------------------------------------------------------------------
    # 3. CAMERA SETUP (CRITICAL FOR PROJECTION)
    # -------------------------------------------------------------------------
    # Place camera directly in front of the head
    bpy.ops.object.camera_add(location=(0, -3.2, 0.2), rotation=(math.radians(90), 0, 0))
    cam_obj = bpy.context.active_object
    cam_obj.name = "Sukuna_Camera"
    scene.camera = cam_obj

    # -------------------------------------------------------------------------
    # 4. CREATE MATERIALS
    # -------------------------------------------------------------------------
    # Skin Material (base skin tone + texture projection)
    skin_mat = bpy.data.materials.new(name="M_Skin_Projected")
    skin_mat.use_nodes = True
    skin_nodes = skin_mat.node_tree.nodes
    skin_links = skin_mat.node_tree.links
    skin_nodes.clear()
    
    skin_output = skin_nodes.new('ShaderNodeOutputMaterial')
    skin_principled = skin_nodes.new('ShaderNodeBsdfPrincipled')
    skin_principled.inputs['Roughness'].default_value = 0.5
    skin_links.new(skin_principled.outputs['BSDF'], skin_output.inputs['Surface'])

    # Project user's reference image onto head mesh
    img_path = r"C:\Users\user\Pictures\MV5BMmIxOTE0ZjMtMDliMy00OTNjLWI5YmMtOTRjN2ZiMzJjOTU4XkEyXkFqcGc@._V1_.jpg"
    if os.path.isfile(img_path):
        try:
            proj_img = bpy.data.images.load(img_path)
            
            coord_node = skin_nodes.new('ShaderNodeTexCoord')
            tex_node = skin_nodes.new('ShaderNodeTexImage')
            tex_node.image = proj_img
            tex_node.projection = 'FLAT'  # flat projection for camera map
            tex_node.extension = 'CLIP'
            
            # Map camera vector to UV mapping node
            mapping_node = skin_nodes.new('ShaderNodeMapping')
            # Scale and translate camera projection coordinates to align perfectly
            mapping_node.inputs['Scale'].default_value = (1.8, 1.8, 1.0)
            mapping_node.inputs['Location'].default_value = (0.5, 0.55, 0.0)
            
            skin_links.new(coord_node.outputs['Camera'], mapping_node.inputs['Vector'])
            skin_links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])
            
            # Blend node to fallback to base skin tone outside the image
            mix_node = skin_nodes.new('ShaderNodeMix')
            mix_node.data_type = 'RGBA'
            mix_node.blend_type = 'MIX'
            mix_node.inputs['Factor'].default_value = 1.0
            
            # Fallback color (soft background match or skin tone)
            mix_node.inputs[6].default_value = (0.1, 0.1, 0.1, 1.0)  # Dark matching the border
            
            skin_links.new(tex_node.outputs['Color'], mix_node.inputs[7])
            skin_links.new(mix_node.outputs[2], skin_principled.inputs['Base Color'])
            
            # Map alpha to mix factor to blend transparent edges
            skin_links.new(tex_node.outputs['Alpha'], mix_node.inputs['Factor'])
        except Exception as e:
            print(f"Error setting up texture projection: {e}")
    else:
        # Fallback skin tone
        skin_principled.inputs['Base Color'].default_value = (0.95, 0.80, 0.70, 1.0)

    # Hair Material (Sukuna Pink-Peach)
    hair_mat = bpy.data.materials.new(name="M_Hair")
    hair_mat.use_nodes = True
    hair_nodes = hair_mat.node_tree.nodes
    hair_nodes.clear()
    hair_output = hair_nodes.new('ShaderNodeOutputMaterial')
    hair_principled = hair_nodes.new('ShaderNodeBsdfPrincipled')
    hair_principled.inputs['Base Color'].default_value = (0.91, 0.53, 0.56, 1.0)  # Pink peach
    hair_principled.inputs['Roughness'].default_value = 0.8
    hair_mat.node_tree.links.new(hair_principled.outputs['BSDF'], hair_output.inputs['Surface'])

    # Kimono Scarf Material
    scarf_mat = bpy.data.materials.new(name="M_Scarf")
    scarf_mat.use_nodes = True
    scarf_nodes = scarf_mat.node_tree.nodes
    scarf_nodes.clear()
    scarf_output = scarf_nodes.new('ShaderNodeOutputMaterial')
    scarf_principled = scarf_nodes.new('ShaderNodeBsdfPrincipled')
    scarf_principled.inputs['Base Color'].default_value = (0.90, 0.88, 0.82, 1.0)
    scarf_principled.inputs['Roughness'].default_value = 0.9
    scarf_mat.node_tree.links.new(scarf_principled.outputs['BSDF'], scarf_output.inputs['Surface'])

    # -------------------------------------------------------------------------
    # 5. GEOMETRY
    # -------------------------------------------------------------------------
    # Head sphere (clean and smooth for clean projection mapping)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=(0, 0, 0.2))
    head_obj = bpy.context.active_object
    head_obj.name = "Sukuna_Head"
    head_obj.scale = (0.84, 0.82, 1.1)  # Smooth oval face
    head_obj.data.materials.append(skin_mat)
    
    # Add subdivision and shade smooth
    subsurf = head_obj.modifiers.new("Subsurf", "SUBSURF")
    subsurf.levels = 2
    bpy.ops.object.shade_smooth()

    # Neck
    bpy.ops.mesh.primitive_cylinder_add(radius=0.30, depth=0.8, location=(0, 0.1, -0.6))
    neck_obj = bpy.context.active_object
    neck_obj.name = "Sukuna_Neck"
    neck_obj.data.materials.append(skin_mat)
    bpy.ops.object.shade_smooth()
    
    # Shoulders
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.1, -1.2))
    shoulders_obj = bpy.context.active_object
    shoulders_obj.name = "Sukuna_Shoulders"
    shoulders_obj.scale = (1.6, 0.6, 0.4)
    shoulders_obj.data.materials.append(skin_mat)

    # -------------------------------------------------------------------------
    # 6. DENSE ANIME SPIKY HAIR
    # -------------------------------------------------------------------------
    # Layered pink hair spikes surrounding the projected head
    hair_roots = [
        # Sideburns & sides
        ((-0.78, -0.2, 0.4), (-0.7, -0.1, -0.25), 0.75),
        ((0.78, -0.2, 0.4), (0.7, -0.1, -0.25), 0.75),
        ((-0.78, 0.1, 0.5), (-0.8, 0.1, -0.1), 0.8),
        ((0.78, 0.1, 0.5), (0.8, 0.1, -0.1), 0.8),
        # Crown and top spikes
        ((0.0, -0.2, 1.25), (0.0, -0.1, 1.05), 0.85),
        ((-0.3, -0.1, 1.2), (-0.4, -0.1, 0.95), 0.8),
        ((0.3, -0.1, 1.2), (0.4, -0.1, 0.95), 0.8),
        ((-0.55, 0.05, 1.05), (-0.65, 0.05, 0.85), 0.75),
        ((0.55, 0.05, 1.05), (0.65, 0.05, 0.85), 0.75),
        # Back flares
        ((-0.6, 0.5, 0.75), (-0.75, 0.55, 0.35), 0.85),
        ((0.6, 0.5, 0.75), (0.75, 0.55, 0.35), 0.85),
        ((0.0, 0.65, 0.95), (0.0, 0.8, 0.55), 0.85),
        ((-0.3, 0.55, 1.15), (-0.35, 0.7, 0.8), 0.9),
        ((0.3, 0.55, 1.15), (0.35, 0.7, 0.8), 0.9),
    ]

    for i, (root, direction, length) in enumerate(hair_roots):
        curve_data = bpy.data.curves.new(name=f"HairSpike_Data_{i}", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.fill_mode = 'FULL'
        curve_data.bevel_depth = 0.12  # Solid anime locks
        curve_data.bevel_resolution = 4
        
        spline = curve_data.splines.new(type='BEZIER')
        spline.bezier_points.add(2)
        
        p0 = spline.bezier_points[0]
        p0.co = root
        p0.handle_left = Vector(root) - Vector(direction) * 0.12
        p0.handle_right = Vector(root) + Vector(direction) * 0.12
        
        mid = Vector(root) + Vector(direction) * (length * 0.5)
        p1 = spline.bezier_points[1]
        p1.co = mid
        p1.handle_left = mid - Vector((0, 0, 0.12))
        p1.handle_right = mid + Vector((0, 0, 0.12))
        
        tip = Vector(root) + Vector(direction) * length
        p2 = spline.bezier_points[2]
        p2.co = tip
        p2.handle_left = tip - Vector(direction) * 0.12
        p2.handle_right = tip + Vector(direction) * 0.12
        
        p0.radius = 1.0
        p1.radius = 0.5
        p2.radius = 0.01  # Sharp tips
        
        spike_obj = bpy.data.objects.new(f"HairSpike_{i}", curve_data)
        scene.collection.objects.link(spike_obj)
        spike_obj.data.materials.append(hair_mat)

    # -------------------------------------------------------------------------
    # 7. KIMONO COLLAR
    # -------------------------------------------------------------------------
    bpy.ops.mesh.primitive_torus_add(align='WORLD', location=(0, -0.05, -0.65), 
                                     major_radius=0.55, minor_radius=0.18,
                                     abso_major_rad=1.35, abso_minor_rad=0.85)
    collar = bpy.context.active_object
    collar.name = "Kimono_Collar"
    collar.scale = (1.15, 1.0, 0.6)
    collar.rotation_euler = (math.radians(12), 0, 0)
    collar.data.materials.append(scarf_mat)

    # -------------------------------------------------------------------------
    # 8. LIGHTING SETUP
    # -------------------------------------------------------------------------
    # Key Light (Front Right)
    bpy.ops.object.light_add(type='SPOT', radius=1.0, location=(2.0, -3.5, 1.5))
    key_light = bpy.context.active_object
    key_light.name = "L_Key"
    key_light.data.energy = 600
    key_light.data.color = (1.0, 1.0, 1.0)
    key_light.rotation_euler = (math.radians(60), 0, math.radians(30))
    
    # Fill Light (Front Left)
    bpy.ops.object.light_add(type='AREA', radius=2.5, location=(-2.0, -2.5, 0.5))
    fill_light = bpy.context.active_object
    fill_light.name = "L_Fill"
    fill_light.data.energy = 200
    fill_light.data.color = (0.8, 0.85, 1.0)
    fill_light.rotation_euler = (math.radians(45), 0, math.radians(-45))

    # Rim Light (Back Center)
    bpy.ops.object.light_add(type='SPOT', radius=1.0, location=(0.0, 3.0, 2.0))
    rim_light = bpy.context.active_object
    rim_light.name = "L_Rim"
    rim_light.data.energy = 900
    rim_light.data.color = (1.0, 0.9, 1.0)
    rim_light.rotation_euler = (math.radians(130), 0, 0)

    # -------------------------------------------------------------------------
    # 9. SAVE & RENDER
    # -------------------------------------------------------------------------
    export_path = r"C:/Users/user/Desktop/New folder/New folder/sukuna_3d.blend"
    bpy.ops.wm.save_as_mainfile(filepath=export_path)
    print(f"Model saved successfully to: {export_path}")
    
    render_path = r"C:/Users/user/Desktop/New folder/New folder/sukuna_render.png"
    scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"Render saved successfully to: {render_path}")

if __name__ == "__main__":
    create_25d_sukuna()
