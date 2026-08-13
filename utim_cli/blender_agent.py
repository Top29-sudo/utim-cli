"""
UTIM Blender Agent — Advanced Image-to-3D Pipeline (v2)
========================================================

Architecture (4 Phases)
------------------------
Phase 0 – Deep Image Analysis
    OpenCV + Pillow analyse the image locally: dominant colours, contours,
    depth-map estimation, feature regions (face, body, hair, clothing).
    A rich "scene_brief" dict is assembled for Phase 1.

Phase 1 – Vision-LLM Scene Understanding
    The image AND scene_brief are sent to a vision-capable LLM with a
    comprehensive system prompt that asks for:
      • Structured part decomposition (head, body, hair, accessory…)
      • Per-part geometry strategy (primitive hint, mesh complexity)
      • Material and colour information per part
      • Tattoo / decal texture descriptions
      • Overall proportions, pose, and scene context

Phase 2 – Procedural Blender Script Generation
    A code-generation LLM receives the scene analysis and writes a
    complete, sophisticated bpy Python script that:
      1. Builds each body part using Blender primitives + modifiers
         (Subdivision Surface, Solidify, Skin, Curve-based hair, etc.)
      2. Applies per-part Principled BSDF materials with the analysed colours
      3. Projects the original image as a texture on the main surface using
         Smart UV Project + image texture nodes
      4. Optionally generates procedural tattoo decals via overlay material
      5. Sets up a 3-point studio light rig
      6. Exports to the requested format

Phase 3 – Execution, Validation & Retry
    The script is executed via Blender in headless mode. If it fails a
    parse-and-fix loop runs up to MAX_RETRIES times before raising.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import pathlib
import re
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from utim_cli.constants import DEFAULT_MODEL

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_VISION_MODELS: List[str] = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "openrouter/free"
]

_CODE_MODELS: List[str] = [
    DEFAULT_MODEL,
    "cohere/north-mini-code:free",
    "openrouter/free"
]



def _get_vision_models() -> List[str]:
    """Return vision model list, with user override prepended if configured."""
    try:
        from utim_cli.config import config
        override = config.get("subagent_model_blender_vision")
        if override and override not in ("__non_agent__", "__none__"):
            return [override] + [m for m in _VISION_MODELS if m != override]
    except Exception:
        pass
    return _VISION_MODELS


def _get_code_models() -> List[str]:
    """Return code model list, with user override prepended if configured."""
    try:
        from utim_cli.config import config
        override = config.get("subagent_model_blender_code")
        if override and override not in ("__non_agent__", "__none__"):
            return [override] + [m for m in _CODE_MODELS if m != override]
    except Exception:
        pass
    return _CODE_MODELS

MAX_RETRIES = 3  # Script fix-and-retry attempts

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_VISION_SYSTEM_PROMPT = """\
You are an expert Blender 3D artist and scene analyst. Examine the image and
produce a detailed JSON scene description that will be used to procedurally
rebuild this image as a 3D scene in Blender.

CRITICAL ANALYSIS GUIDELINES:
- DEPTH CUES: Analyze perspective, shading gradients, and contour lines to estimate depth/z-distance
- PROPORTIONS: Provide precise relative measurements (values 0.0-1.0 for size/position ratios)

MANDATORY - CHECK THESE BEFORE OUTPUT:
1. TATTOOS: If ANY symbols/markings on skin, set has_tattoos=true and list EACH in tattoos array with location and shape_description
2. EYE COLOR: Extract EXACT iris color - check carefully, may be red/yellow/etc
3. HAIR GRADIENTS: If hair has color transitions, extract dark_root_color, mid_color, tip_color
4. EXPRESSION: Describe accurately (smirk, neutral, angry, etc)

- EYES: Must detail exact eye construction (color, size, shape, pupil, cornea)
- Multi-object scenes: If multiple objects exist, provide "objects" array with each object's own structure

OUTPUT FORMAT — a single raw JSON object (no markdown, no explanation):

{
  "scene_type": "character",
  "description": "<one-paragraph description>",
  "subject_label": "<e.g. anime_character, human_face, vehicle, animal>",

  "parts": [
    {
      "id": "head",
      "label": "Head / Face",
      "geometry_hint": "uv_sphere_deformed",
      "dominant_colors": [[r,g,b]],
      "material": {
        "name": "Skin",
        "base_color": [r, g, b, 1.0],
        "roughness": 0.6,
        "metallic": 0.0,
        "subsurface": 0.0,
        "subsurface_color": [r, g, b],
        "emission": [0,0,0]
      },
      "relative_size": [w, h, d],
      "relative_position": [x, y, z],
      "depth_hint": "convex/front-facing",
      "notes": "describe shape details"
    }
  ],

  "hair": {
    "style": "spiky_anime",
    "color": [r, g, b],
    "secondary_color": [r, g, b],
    "dark_root_color": [r, g, b],
    "tip_color": [r, g, b],
    "length": "medium",
    "spike_count": 14,
    "spike_directions": [
      {"angle": 45, "direction": "forward_left", "width": 0.15},
      {"angle": 60, "direction": "up_right", "width": 0.12}
    ],
    "notes": "describe spike shapes and flow direction"
  },

  "face_details": {
    "has_tattoos": true,
    "tattoos": [
      {
        "location": "forehead_center",
        "relative_position": [0.0, 0.85, 0.02],
        "size": [0.35, 0.12],
        "color": [r, g, b],
        "shape_description": "double-trident with dot between (example: like Jujutsu Kaisen symbol)",
        "depth_hint": "flat_on_surface"
      }
    ],
    "eyebrows": true,
    "eyebrow_color": [r, g, b],
    "eye_color": [r, g, b],
    "eye_style": "anime_large",
    "eye_size_ratio": 0.25,
    "pupil_color": [r, g, b],
    "expression": "smirk",
    "eye_details": {
      "iris_size": 0.7,
      "shine_position": "upper_left",
      "cornea_ior": 1.4
    }
  },

  "clothing": [
    {
      "item": "scarf",
      "color": [r, g, b],
      "secondary_color": [r, g, b],
      "material_hint": "fabric_thick",
      "coverage": "neck_to_chin",
      "thickness": 0.02,
      "fold_directions": ["down_center", "out_sides"],
      "relative_position": [0.0, -0.1, 0.0]
    }
  ],

  "objects": [
    {
      "id": "background",
      "label": "Background Object",
      "geometry_hint": "plane",
      "dominant_colors": [[r,g,b]],
      "relative_size": [w, h, d],
      "relative_position": [x, y, z]
    }
  ],

  "lighting_suggestion": {
    "type": "three_point",
    "key_color": [r, g, b],
    "fill_color": [r, g, b],
    "rim_color": [r, g, b]
  },

  "overall_proportions": {
    "head_scale": 1.0,
    "body_visible": true,
    "visible_parts": ["head", "neck", "shoulders"],
    "head_to_body_ratio": 0.25
  },

  "depth_estimation": {
    "foreground": "head/neck",
    "background": "image_background",
    "depth_layers": 3
  },

  "image_texture_applicable": true,
  "background_color": [r, g, b]
}

Rules:
- All color values are 0.0-1.0 floats.
- For anime characters: subsurface=0.0, roughness=0.7, eye_style="anime_large".
- **TATTOOS/DECALS ARE MANDATORY**: If ANY markings, symbols, or special patterns are VISIBLE on skin, hair, or clothing, you MUST set has_tattoos=true and populate the tattoos array with precise positioning.
- **Eye details are mandatory**: ALWAYS populate eye_details with iris_size, shine_position, and cornea_ior.
- Hair spikes MUST have spike_count matching actual visible hair strands - count carefully and list ALL directions.
- Eye_size_ratio should be a decimal like 0.25 for 25% of head width.
- Tattoo relative_position uses 0-1 scale from head center (x,y,z) where z=0 is head center, z>0 is up.
- Output ONLY the raw JSON object — no backticks, no text before or after.
"""

_GEOMETRY_SYSTEM_PROMPT = """\
You are an expert 3D modeler and structural geometric analyst. Your task is to perform a detailed "inch-by-inch" (or unit-by-unit) spatial and geometric analysis of the subject in the provided image.

Analyze the image and produce a detailed structural decomposition. Detail the exact relative measurements, positions, curves, and spatial relations for EVERY key feature.

Your output must be a single JSON object with the following schema:
{
  "scene_type": "character",
  "subject_label": "<e.g. anime_character, human_face, vehicle, animal>",
  "description": "<one-paragraph description>",
  "visual_geometry": {
    "dimensions": {
      "head": {
        "width_in": 6.5,
        "height_in": 9.0,
        "depth_in": 7.0,
        "shape_description": "<e.g. oval, soft jawline, sharp chin, tapered skull>"
      },
      "neck": {
        "radius_in": 2.0,
        "height_in": 3.5,
        "tilt_degrees": 0.0
      },
      "shoulders": {
        "width_in": 16.0,
        "height_in": 4.0,
        "depth_in": 5.0
      }
    },
    "features": {
      "left_eye": {
        "center_relative": [-1.5, 0.5, 3.2],
        "width_in": 1.2,
        "height_in": 0.8,
        "socket_depth_in": 0.5,
        "iris_color_rgb": [0.0, 0.0, 0.0],
        "pupil_size_ratio": 0.3
      },
      "right_eye": {
        "center_relative": [1.5, 0.5, 3.2],
        "width_in": 1.2,
        "height_in": 0.8,
        "socket_depth_in": 0.5,
        "iris_color_rgb": [0.0, 0.0, 0.0],
        "pupil_size_ratio": 0.3
      },
      "nose": {
        "center_relative": [0.0, 0.0, 3.5],
        "bridge_length_in": 2.0,
        "bridge_width_in": 0.6,
        "tip_protrusion_in": 0.8
      },
      "mouth": {
        "center_relative": [0.0, -1.5, 3.3],
        "width_in": 2.2,
        "height_in": 0.5,
        "lip_thickness_in": 0.3,
        "expression_shape": "<e.g. smirk upturned on right side, wide grin with visible teeth>"
      }
    },
    "hair_geometry": {
      "style": "<e.g. spiky_anime, long_waves>",
      "hair_color_rgb": [0.0, 0.0, 0.0],
      "spikes": [
        {
          "index": 0,
          "base_relative": [-2.0, 3.0, 1.0],
          "tip_relative": [-3.5, 4.5, 1.5],
          "base_width_in": 0.8,
          "curve_direction": "up_and_left_outward"
        }
      ],
      "overall_volume_description": "describe hair mass shape and flow"
    },
    "surface_markings": {
      "has_tattoos": true,
      "tattoos": [
        {
          "id": "forehead_center",
          "relative_position": [0.0, 0.85, 0.02],
          "dimensions_in": [3.5, 1.2],
          "path_description": "two vertical-curved lines like a trident, with a dot in center",
          "color_rgb": [0.0, 0.0, 0.0]
        }
      ]
    }
  },
  "parts": [
    {
      "id": "head",
      "label": "Head / Face",
      "geometry_hint": "uv_sphere_deformed",
      "dominant_colors": [[0.8,0.6,0.5]],
      "material": {
        "name": "Skin",
        "base_color": [0.8, 0.6, 0.5, 1.0],
        "roughness": 0.6,
        "metallic": 0.0,
        "subsurface": 0.15,
        "subsurface_color": [0.8, 0.6, 0.5],
        "emission": [0,0,0]
      },
      "relative_size": [6.5, 9.0, 7.0],
      "relative_position": [0.0, 0.0, 0.0],
      "depth_hint": "convex",
      "notes": "describe shape details"
    }
  ],
  "hair": {
    "style": "spiky_anime",
    "color": [0.9, 0.5, 0.6],
    "secondary_color": [0.9, 0.5, 0.6],
    "dark_root_color": [0.2, 0.1, 0.1],
    "tip_color": [1.0, 0.6, 0.7],
    "length": "medium",
    "spike_count": 14,
    "notes": "spiky hair"
  },
  "face_details": {
    "has_tattoos": true,
    "tattoos": [
      {
        "location": "forehead_center",
        "relative_position": [0.0, 0.85, 0.02],
        "size": [0.35, 0.12],
        "color": [0.0, 0.0, 0.0],
        "shape_description": "trident shape forehead tattoo",
        "depth_hint": "flat_on_surface"
      }
    ],
    "eyebrows": true,
    "eyebrow_color": [0.1, 0.1, 0.1],
    "eye_color": [0.8, 0.1, 0.1],
    "eye_style": "anime_large",
    "eye_size_ratio": 0.25,
    "pupil_color": [0.2, 0.0, 0.0],
    "expression": "smirk",
    "eye_details": {
      "iris_size": 0.7,
      "shine_position": "upper_left",
      "cornea_ior": 1.4
    }
  },
  "clothing": [],
  "objects": [],
  "lighting_suggestion": {
    "type": "three_point",
    "key_color": [1.0, 1.0, 0.9],
    "fill_color": [0.8, 0.8, 1.0],
    "rim_color": [0.9, 0.9, 1.0]
  },
  "overall_proportions": {
    "head_scale": 1.0,
    "body_visible": true,
    "visible_parts": ["head", "neck", "shoulders"],
    "head_to_body_ratio": 0.25
  },
  "depth_estimation": {
    "foreground": "head/neck",
    "background": "image_background",
    "depth_layers": 3
  },
  "image_texture_applicable": true,
  "background_color": [0.1, 0.1, 0.1]
}

Rules:
- All color values are 0.0-1.0 float arrays.
- HAIR STRUCTURE ACCURACY IS CRITICAL: Analyze the exact start/root position on the scalp or hairline, the overall flow direction, the thickness profile, and the exact end/tip position in 3D space for EVERY major hair strand/spike. Map out at least 14+ distinct hair spikes/strands with detailed root-to-tip coordinates, growth angles, and taper instructions to capture the spiky anime hair flow accurately.
- MINUTE DETAILS: Examine eye contours, iris color transitions, facial markings (tattoos), and clothing creases, providing relative coordinates for all components.
- Output ONLY the raw JSON object, no explanation, no markdown.
"""

_ASSEMBLY_SYSTEM_PROMPT = """\
You are an expert 3D technical director. You take a detailed visual geometry analysis JSON of a character/object and write a precise step-by-step mathematical assembly plan to reconstruct this in Blender using Python (`bpy`).

Write a detailed, logical assembly document. Focus on how to represent the complex geometry procedurally:
1. **Base Mesh Generation**: How to create the head mesh (e.g. start with a sphere, deform vertices mathematically to create the chin/jaw, or combine a sphere and cylinder, then carve out eye sockets using boolean difference with cylinders/cubes).
2. **Feature Modeling**: How to build the nose, mouth, eyes (layered sclera, iris, cornea) and place them exactly at the relative coordinates.
3. **Hair Construction**: Detail the exact root coordinate on the scalp, growth vector, control point tangents, and tip coordinates for each hair strand/spike. Plan how to generate Curves (with custom bevel depth and resolution) or Cones to model each spiky strand, ensuring they taper naturally from root to tip.
4. **Tattoos / Markings**: How to project decals or create curves shrinkwrapped onto the head mesh to represent the tattoos/markings exactly.
5. **Shading & Texture Projection**: Detail how to set up camera texture projection mapping to connect the source image texture to the Principled BSDF shader, aligning the projection with the camera.

Output your plan as clear technical text with mathematical coordinates and procedural steps. Do not write python code yet, just the step-by-step technical modeling plan.
"""


_CODE_SYSTEM_PROMPT = """\
You are a world-class Blender Python scripting expert specializing in procedural 3D modeling and rendering. You will receive a Visual Geometry Analysis JSON, a 3D Assembly Plan, and target export details. You must write a complete, runnable `bpy` Python script that builds this 3D model in Blender.

BLENDER COORDINATE SYSTEM & DIRECTION (CRITICAL):
- In Blender's coordinate space:
  - X-axis: Left-to-Right (Negative X is Left, Positive X is Right).
  - Y-axis: Depth (Negative Y is Front, Positive Y is Back).
  - Z-axis: Height (Negative Z is Down, Positive Z is Up).
- Default Camera & View Direction:
  - The default camera is positioned at (0, -4, 0) looking along the POSITIVE Y-axis (facing (0, 0, 0)).
  - Therefore, the FRONT OF THE FACE/CHARACTER is at NEGATIVE Y (Y must be between -0.7 and -1.0).
  - Placements at POSITIVE Y (Y > 0) are on the back of the head or inside the skull and will be invisible to the camera!
  - You MUST place the eyes, nose, mouth, and facial decals/tattoos at NEGATIVE Y (e.g. Y = -0.9 to -1.0)!

VARIABLE SCOPE PROTECTION & MATERIAL NODE HYGIENE (CRITICAL):
- NEVER reuse variable names like `nodes`, `links`, or `principled` across different materials! If you reuse these names without re-assigning them, you will corrupt node setups on previous materials.
- Use UNIQUE variable names for EACH material, for example:
  - Skin Material: `skin_mat`, `skin_nodes`, `skin_links`, `skin_principled`
  - Sclera Material: `sclera_mat`, `sclera_nodes`, `sclera_links`, `sclera_principled`
  - Iris Material: `iris_mat`, `iris_nodes`, `iris_links`, `iris_principled`
  - Hair Material: `hair_mat`, `hair_nodes`, `hair_links`, `hair_principled`
- Always verify that texture projection nodes are linked to the Skin material's node tree, NOT overwritten by another material's node tree!

MANDATORY GEOMETRY CONSTRUCTION RULES:
1. **Head & Jaw (Tapered)**:
   - Create a tapered head shape. For example, combine a sphere for the skull with a cylinder/cone for the jaw/chin, join them (`bpy.ops.object.join()`), and add a Subdivision modifier for a smooth organic shape.
2. **Eye Sockets (Boolean subtraction)**:
   - To prevent eyes from clipping or bulging weirdly, carve out two eye sockets in the head mesh by subtracting two cylinder/sphere primitives using a Boolean Difference Modifier before inserting the eye spheres.
3. **Layered Eye Construction**:
   - Create white sclera spheres flattened on the X axis, iris planes with `iris_mat` placed on the FRONT of the sclera, and transparent cornea shells.
   - Symmetrically position them at negative Y (Y = -0.85) and negative/positive X (Left X = -0.35, Right X = 0.35).
4. **Anime Spiky Hair**:
   - For spiky anime hair, create CURVE objects with custom bevel depth. Position each spike's start point (root) on the scalp surface (various positions on the skull sphere where Z > 0) and extend the curve outward to the tip coordinates following the growth angles. Set Spline point handles to 'VECTOR' for sharp spikes.
5. **Tattoos / Face Markings**:
   - Create flat planes for decals. Position them at negative Y (Y = -0.92) to match the face surface, and apply a Shrinkwrap modifier targeting the head mesh. Apply a black/emission material.
6. **Camera Texture Projection**:
   - Set up the camera projection node on the Skin material's tree to project the source image onto the head mesh.
7. **3-Point Lighting Rig**:
   - Set up Key, Fill, and Rim lights with appropriate intensities.

CRITICAL COMPATIBILITY — Blender 5.x STRICT RULES:
1. Use `bpy.context.scene.collection.objects.link(obj)` — NEVER `bpy.context.collection.objects.link(obj)`
2. NEVER use `mesh.use_auto_smooth` — removed in Blender 5.x
3. NEVER use `mesh.normals_split_custom_set()` or `mesh.normals_split_custom_set_from_vertices()`
4. NEVER use `bmesh` for mesh creation — use `mesh.from_pydata(vertices, [], faces)` instead
5. `bpy.context.view_layer.objects.active` requires an object already linked to the scene
6. Use `obj.select_set(True)` to select objects
7. For Subdivision Surface: `mod = obj.modifiers.new("Subsurf", "SUBSURF"); mod.levels = 2`
8. NEVER set vertex normals directly — they are read-only in Blender 5.x
9. Change principled.inputs['Subsurface'] to principled.inputs['Subsurface Weight'] (Blender 5.x update)

SCRIPT STRUCTURE:
- Clear the scene using `bpy.ops.object.select_all` + `bpy.ops.object.delete`.
- Build HEAD first, then EYES, then HAIR, then CLOTHING, then TATTOOS.
- Set up 3-point lighting rig and camera.
- Apply materials and texture projection.
- Export to target path and print UTIM_BLENDER_SUCCESS.

EXPORT CODE (hardcode the exact values given in the user prompt, NOT placeholders):
```python
export_path = "<ACTUAL_PATH_STRING>"
export_format = "<ACTUAL_FORMAT_STRING>"
if export_format == 'blend':
    bpy.ops.wm.save_as_mainfile(filepath=export_path, copy=True)
elif export_format == 'obj':
    bpy.ops.wm.obj_export(filepath=export_path)
elif export_format == 'glb':
    bpy.ops.export_scene.gltf(filepath=export_path, export_format='GLB')
elif export_format == 'fbx':
    bpy.ops.export_scene.fbx(filepath=export_path)
print(f"UTIM_BLENDER_SUCCESS: {export_path}")
```

Output ONLY the Python script — no markdown, no explanation, no fences.
"""

_FIX_SYSTEM_PROMPT = """\
You are a Blender Python debugging expert. A bpy script failed with an error.
Fix the script so it runs correctly in Blender 5.x.

Rules:
- Output ONLY the corrected Python script, no explanation, no markdown fences.
- Keep all the original logic intact; only fix the errors.
- NEVER use bmesh, mesh.use_auto_smooth, normals_split_custom_set.
- ALWAYS use bpy.context.scene.collection.objects.link(obj).
- If a modifier or operator is unavailable, comment it out gracefully.
- Make sure export_path and export_format are hardcoded strings.
- BLNDER 5.x FIX: Change principled.inputs['Subsurface'] to principled.inputs['Subsurface Weight']
- End the script with: print(f"UTIM_BLENDER_SUCCESS: {export_path}")
"""

# ---------------------------------------------------------------------------
# Low-level LLM call
# ---------------------------------------------------------------------------

def _llm_call(
    system: str,
    user_text: str,
    models: List[str],
    image_b64: Optional[str] = None,
    image_mime: Optional[str] = None,
    max_tokens: int = 8192,
    timeout: int = 120,
) -> str:
    """Call OpenRouter with a system+user message, returning the assistant text.

    Tries each model in *models* until one succeeds.
    """
    from utim_cli.config import config
    api_key = os.getenv("OPENROUTER_API_KEY", "") or config.get("api_key")
    if not api_key:
        raise RuntimeError("Neither OPENROUTER_API_KEY nor UTIM API key is set.")

    if image_b64 and image_mime:
        user_content: Any = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
        ]
    else:
        user_content = user_text

    last_err: Exception = RuntimeError("No models tried.")
    for model in models:
        for attempt in range(3):
            try:
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(
                    json_data={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_content},
                        ],
                        "max_tokens": max_tokens,
                        "stream": False,
                    },
                    stream=False,
                    timeout=timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return text.strip()
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                code = getattr(getattr(exc, "response", None), "status_code", 0)
                if code == 429 and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                break  # try next model
    raise RuntimeError(f"All LLM models failed. Last error: {last_err}") from last_err


# ---------------------------------------------------------------------------
# Phase 0 — Local image pre-analysis (no LLM needed)
# ---------------------------------------------------------------------------

def _phase0_local_analysis(image_path: str) -> Dict[str, Any]:
    """Extract dominant colours, basic image stats, and depth hints using Pillow."""
    brief: Dict[str, Any] = {
        "width": 0,
        "height": 0,
        "dominant_colors": [],
        "aspect_ratio": 1.0,
        "has_transparency": False,
        "brightness": 0.5,
        "depth_hints": {},
        "face_landmarks": {},
    }

    try:
        from PIL import Image, ImageFilter, ImageDraw  # type: ignore
        import statistics
        
        img = Image.open(image_path).convert("RGBA")
        brief["width"] = img.width
        brief["height"] = img.height
        brief["aspect_ratio"] = round(img.width / max(img.height, 1), 3)
        brief["has_transparency"] = img.mode == "RGBA"

        # Quantise to 8 dominant colours
        small = img.convert("RGB").resize((150, 150), Image.LANCZOS)
        quantised = small.quantize(colors=8, method=Image.Quantize.FASTOCTREE)
        palette = quantised.getpalette()
        if palette:
            colors = []
            for i in range(0, min(24, len(palette)), 3):
                r, g, b = palette[i], palette[i + 1], palette[i + 2]
                colors.append([round(r / 255, 3), round(g / 255, 3), round(b / 255, 3)])
            brief["dominant_colors"] = colors

        # Average brightness
        grey = small.convert("L")
        pixels = list(grey.getdata())
        brief["brightness"] = round(statistics.mean(pixels) / 255, 3)

        # --- Depth Estimation: Enhanced edge and gradient analysis ---
        # Blur and find edges to approximate depth contours
        blurred = grey.filter(ImageFilter.GaussianBlur(radius=2))
        edges = blurred.filter(ImageFilter.FIND_EDGES)
        
        # Analyze edge density in different regions (vertical slices)
        edge_pixels = list(edges.getdata())
        width_small = 150
        height_small = 150
        total_pixels = width_small * height_small
        
        # Divide image into vertical strips and count edges (proxy for depth changes)
        strip_counts = []
        for x in range(0, width_small, 15):  # 10 vertical strips
            edge_count = 0
            total_in_strip = 0
            for y in range(height_small):
                for dx in range(15):
                    if x + dx < width_small:
                        idx = y * width_small + (x + dx)
                        if idx < len(edge_pixels):
                            total_in_strip += 1
                            if edge_pixels[idx] > 50:
                                edge_count += 1
            strip_counts.append(edge_count / max(total_in_strip, 1))
        
        # Horizontal strips for depth layers
        horizontal_edge_density = []
        for y in range(0, height_small, 15):
            strip_start = y * width_small
            strip_end = min(strip_start + 15 * width_small, len(edge_pixels))
            strip_edges = edge_pixels[strip_start:strip_end]
            edge_count = sum(1 for p in strip_edges if p > 50)
            horizontal_edge_density.append(edge_count / max(len(strip_edges), 1))
        
        # Depth hints from edge distribution
        center_strip = len(strip_counts) // 2 if strip_counts else 0
        brief["depth_hints"] = {
            "vertical_edge_density": strip_counts,
            "horizontal_edge_density": horizontal_edge_density,
            "center_focus": strip_counts[center_strip] if strip_counts else 0.5,
            "has_center_subject": bool(strip_counts[center_strip] > 0.1) if strip_counts else True,
            "estimated_layer_depth": len([c for c in horizontal_edge_density if c > 0.15]) if horizontal_edge_density else 1,
            "depth_variance": round(statistics.stdev(strip_counts) if len(strip_counts) > 1 else 0, 3),
        }

        # --- Simple face landmark estimation (center of mass for skin tones) ---
        # Look for face-like region using simple luminance analysis
        face_region_found = False
        for y in range(0, height_small, 15):
            row_lum = grey.crop((0, y, width_small, min(y + 15, height_small)))
            row_pixels = list(row_lum.getdata())
            avg_bright = statistics.mean(row_pixels)
            if 0.3 < avg_bright / 255 < 0.7:  # skin tone range
                face_region_found = True
                break
        
        brief["face_landmarks"] = {
            "estimated_face_present": face_region_found,
            "skin_tone_range": [min(pixels), max(pixels)] if pixels else [128, 128],
        }

        # --- Dark mark/tattoo detection hint ---
        # Look for dark marks on lighter skin regions (typical tattoo contrast)
        # This is a heuristic to hint that tattoos may be present
        forehead_dark_pixels = 0
        if height_small > 0:
            # Top 20% of image is forehead area
            forehead_strip = grey.crop((0, 0, width_small, max(20, height_small // 5)))
            forehead_pixels = list(forehead_strip.getdata())
            forehead_dark_pixels = sum(1 for p in forehead_pixels if p < 100)  # Dark pixels
        
        brief["potential_tattoos"] = {
            "dark_marks_on_forehead": forehead_dark_pixels > 50,
            "check_tattoos": forehead_dark_pixels > 50,
        }

    except ImportError:
        pass  # Pillow not available — skip local analysis
    except Exception:
        pass  # Silently ignore analysis errors

    return brief


# ---------------------------------------------------------------------------
# Phase 1 — Vision-LLM scene understanding
# ---------------------------------------------------------------------------

def _phase1_vision(image_path: str, scene_brief: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Send the image to a vision model, perform visual geometry analysis, and write an assembly plan."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext)
        if not mime_type:
            raise ValueError(f"Unsupported image format: {image_path}")

    with open(image_path, "rb") as fh:
        image_b64 = base64.b64encode(fh.read()).decode()

    brief_text = (
        f"Image pre-analysis (local):\n"
        f"  Resolution : {scene_brief.get('width')}x{scene_brief.get('height')} px\n"
        f"  Brightness : {scene_brief.get('brightness')}\n"
        f"  Dominant colours (0-1 RGB): {json.dumps(scene_brief.get('dominant_colors', []))}\n"
        f"  Depth hints: {json.dumps(scene_brief.get('depth_hints', {}))}\n"
        f"  Face landmarks: {json.dumps(scene_brief.get('face_landmarks', {}))}\n"
        f"  Potential tattoos: {json.dumps(scene_brief.get('potential_tattoos', {}))}\n\n"
        "MANDATORY: Perform a meticulous 'inch-by-inch' visual geometry analysis of the character facial shapes, jaw structure, spiky hair curves, and tattoos.\n"
        "Examine this image carefully and output the JSON scene description exactly as specified."
    )

    # Pass 1: Visual Geometry Analysis
    raw = _llm_call(
        system=_GEOMETRY_SYSTEM_PROMPT,
        user_text=brief_text,
        models=_get_vision_models(),
        image_b64=image_b64,
        image_mime=mime_type,
        max_tokens=8192,
    )

    # Strip possible markdown fences the model emits despite instructions
    clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    
    # Find the outermost JSON object using brace counting for robustness
    start = clean.find("{")
    if start < 0:
        raise ValueError(
            f"Vision model did not return a JSON object.\nRaw output:\n{raw}"
        )
    
    # Count braces to find matching end brace
    brace_count = 0
    end = start
    for i, char in enumerate(clean[start:], start):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    if end <= start:
        # Fallback to original method
        end = clean.rfind("}") + 1
    
    json_str = clean[start:end]
    
    try:
        scene_data: Dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to repair common JSON issues
        # Remove trailing commas before } or ]
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        # Remove comments (not standard JSON but models sometimes include them)
        json_str = re.sub(r"//.*$", "", json_str, flags=re.MULTILINE)
        try:
            scene_data = json.loads(json_str)
        except json.JSONDecodeError as e2:
            raise ValueError(
                f"Vision model returned malformed JSON at position {e2.pos}:\n"
                f"Error: {e2.msg}\n"
                f"JSON snippet: {json_str[max(0,e2.pos-50):e2.pos+50]}\n"
                f"Raw output:\n{raw[:2000]}"
            ) from e2

    # Ensure defaults
    scene_data.setdefault("parts", [])
    scene_data.setdefault("hair", {})
    scene_data.setdefault("face_details", {})
    scene_data.setdefault("clothing", [])
    scene_data.setdefault("objects", [])
    scene_data.setdefault("lighting_suggestion", {"type": "three_point"})
    scene_data.setdefault("depth_estimation", {"depth_layers": 1})
    scene_data.setdefault("image_texture_applicable", True)
    scene_data.setdefault("background_color", [0.95, 0.95, 0.95])
    scene_data.setdefault("overall_proportions", {"head_to_body_ratio": 0.25})
    
    # Ensure nested defaults
    scene_data["lighting_suggestion"].setdefault("rim_color", [0.8, 0.8, 1.0])
    scene_data["face_details"].setdefault("tattoos", [])
    scene_data["face_details"].setdefault("has_tattoos", bool(scene_data["face_details"].get("tattoos")))

    # Pass 2: 3D Assembly Plan
    plan_prompt = (
        f"Visual Geometry Analysis JSON:\n{json.dumps(scene_data, indent=2)}\n\n"
        "Formulate a detailed, math-oriented 3D modeling and camera texture projection assembly plan for Blender."
    )
    assembly_plan = _llm_call(
        system=_ASSEMBLY_SYSTEM_PROMPT,
        user_text=plan_prompt,
        models=_get_code_models(),
        max_tokens=8192,
    )

    return scene_data, assembly_plan


# ---------------------------------------------------------------------------
# Phase 2 — Blender script generation
# ---------------------------------------------------------------------------

def _phase2_generate_script(
    scene_data: Dict[str, Any],
    assembly_plan: str,
    image_path: str,
    name: str,
    export_path: str,
    export_format: str,
) -> str:
    """Ask a code model to write a complete bpy script for the scene."""

    # Forward-slash paths for Blender (works cross-platform)
    blender_image_path = image_path.replace("\\", "/")
    blender_export_path = export_path.replace("\\", "/")

    user_prompt = (
        f"Object name: {name}\n"
        f"Export path: {blender_export_path}\n"
        f"Export format: {export_format}\n"
        f"Source image path (for texture projection): {blender_image_path}\n\n"
        f"Visual Geometry Analysis JSON:\n{json.dumps(scene_data, indent=2)}\n\n"
        f"3D Assembly Plan:\n{assembly_plan}\n\n"
        "Generate the complete Blender Python script now.\n\n"
        "IMPORTANT INSTRUCTIONS FOR ENHANCED SCENE DATA:\n"
        "- Build every part listed in scene_data['parts'] as a separate named object\n"
        "- Use the EXACT export_path and export_format strings above — do NOT use placeholders\n"
        "- For head/jaw: construct complex organic geometry from vertex lists or join neck, jaw, and skull, adding subsurf modifier\n"
        "- For hair: buildCurve Hair with bevel depth, or place cones precisely tapering to tips according to the directions\n"
        "- For eye sockets: subtract sphere primitives using boolean difference modifier, placing sclera, iris, cornea inside\n"
        "- For tattoos: create curves shrinkwrapped onto target surface, colored black or emission\n"
        "- For camera texture projection: implement Camera projection UV mapping shader\n"
        "- Set up rim lighting using lighting_suggestion.rim_color\n"
    )

    raw_script = _llm_call(
        system=_CODE_SYSTEM_PROMPT,
        user_text=user_prompt,
        models=_get_code_models(),
        max_tokens=16384,
    )

    return _clean_and_patch_script(raw_script, blender_export_path, export_format, blender_image_path)


# ---------------------------------------------------------------------------
# Script cleaning & Blender 5.x compatibility patching
# ---------------------------------------------------------------------------

def _clean_and_patch_script(
    raw: str,
    export_path: str,
    export_format: str,
    image_path: str = "",
) -> str:
    """Strip markdown fences, replace placeholders, and fix Blender 5.x issues."""
    # Strip fences
    script = re.sub(r"```(?:python)?\s*|\s*```", "", raw).strip()

    # ── Placeholder replacement ──────────────────────────────────────────────
    esc_path = export_path.replace("\\", "/")
    esc_fmt = export_format

    placeholder_patterns = [
        (r'export_path\s*=\s*__EXPORT_PATH__', f'export_path = "{esc_path}"'),
        (r'export_format\s*=\s*__EXPORT_FORMAT__', f'export_format = "{esc_fmt}"'),
        (r'export_path\s*=\s*["\']__EXPORT_PATH__["\']', f'export_path = "{esc_path}"'),
        (r'export_format\s*=\s*["\']__EXPORT_FORMAT__["\']', f'export_format = "{esc_fmt}"'),
        (r'export_path\s*=\s*["\']<ACTUAL[^"\']*>["\']', f'export_path = "{esc_path}"'),
        (r'export_format\s*=\s*["\']<ACTUAL[^"\']*>["\']', f'export_format = "{esc_fmt}"'),
        (r'export_path\s*=\s*["\']<ACTUAL_EXPORT_PATH_STRING>["\']', f'export_path = "{esc_path}"'),
        (r'export_format\s*=\s*["\']<ACTUAL_EXPORT_FORMAT_STRING>["\']', f'export_format = "{esc_fmt}"'),
    ]
    for pattern, replacement in placeholder_patterns:
        script = re.sub(pattern, replacement, script)

    if image_path:
        esc_img = image_path.replace("\\", "/")
        script = re.sub(
            r'image_path\s*=\s*["\']<[^"\']*>["\']',
            f'image_path = "{esc_img}"',
            script,
        )

    # ── Blender 5.x compatibility fixes ─────────────────────────────────────
    script = script.replace(
        "bpy.context.collection.objects.link(obj)",
        "bpy.context.scene.collection.objects.link(obj)",
    )
    script = re.sub(
        r"mesh\.use_auto_smooth\s*=\s*(True|False)",
        "# mesh.use_auto_smooth removed in Blender 5.x",
        script,
    )
    script = re.sub(
        r"mesh\.normals_split_custom_set_from_vertices\([^)]*\)",
        "# normals_split_custom_set_from_vertices removed in Blender 5.x",
        script,
    )
    script = re.sub(
        r"mesh\.normals_split_custom_set\([^)]*\)",
        "# normals_split_custom_set removed in Blender 5.x",
        script,
    )
    script = re.sub(
        r"v\.normal\s*=\s*[^#\n]+",
        "# vertex.normal is read-only in Blender 5.x",
        script,
    )
    script = re.sub(
        r"mesh\.vertices\[[^\]]+\]\.normal\s*=\s*[^#\n]+",
        "# vertex.normal is read-only in Blender 5.x",
        script,
    )
    # Blender 5.x renamed 'Subsurface' to 'Subsurface Weight'
    script = re.sub(
        r"principled\.inputs\['Subsurface'\]\s*=\s*([^#\n]+)",
        r"principled.inputs['Subsurface Weight'].default_value = \1",
        script,
    )
    script = re.sub(
        r"principled\.inputs\['Subsurface'\]\.default_value\s*=\s*([^#\n]+)",
        r"principled.inputs['Subsurface Weight'].default_value = \1",
        script,
    )

    # Ensure the success marker is present
    if "UTIM_BLENDER_SUCCESS" not in script:
        script += f'\nprint(f"UTIM_BLENDER_SUCCESS: {esc_path}")\n'

    return script


# ---------------------------------------------------------------------------
# Phase 3 — Blender execution with retry
# ---------------------------------------------------------------------------

def _phase3_execute(
    script: str,
    scene_data: Dict[str, Any],
    image_path: str,
    name: str,
    export_path: str,
    export_format: str,
    tmp_dir: pathlib.Path,
) -> str:
    """Execute the Blender script, retrying with LLM-assisted fixes on failure."""
    from utim_cli.config import BLENDER_PATH  # noqa: PLC0415
    if not BLENDER_PATH:
        raise RuntimeError(
            "Blender executable not found. Set UTIM_BLENDER_PATH environment variable "
            "or install Blender on the system PATH."
        )

    current_script = script
    last_error = ""

    for attempt in range(MAX_RETRIES + 1):
        # Save script
        script_path = tmp_dir / f"gen_{name}_{uuid.uuid4().hex[:8]}.py"
        script_path.write_text(current_script, encoding="utf-8")

        # Build command
        if os.name == "nt":
            cmd = f'& "{BLENDER_PATH}" -b -noaudio -P "{script_path}"'
        else:
            cmd = f'"{BLENDER_PATH}" -b -noaudio -P "{script_path}"'

        # Auto-approve in sandbox mode
        try:
            from utim_cli.tools import _SANDBOX_MODE, is_command_approved, approve_command  # noqa: PLC0415
            if _SANDBOX_MODE and not is_command_approved(cmd):
                approve_command(cmd)
        except Exception:
            pass

        result = subprocess.run(
            cmd if os.name != "nt" else ["powershell", "-Command", cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

        combined_output = (result.stdout or "") + (result.stderr or "")

        if result.returncode == 0:
            # Verify export file exists
            if pathlib.Path(export_path).exists():
                return export_path
            match = re.search(r"UTIM_BLENDER_SUCCESS:\s*(.+)", combined_output)
            if match:
                found_path = match.group(1).strip()
                if pathlib.Path(found_path).exists():
                    return found_path
            last_error = (
                f"Blender exit 0 but export not found at: {export_path}\n"
                f"Output:\n{combined_output[-2000:]}"
            )
        else:
            last_error = (
                f"Blender exit code {result.returncode}\n"
                f"Output:\n{combined_output[-2000:]}"
            )

        if attempt < MAX_RETRIES:
            # Ask LLM to fix the script
            fix_prompt = (
                f"The following Blender Python script failed with this error:\n\n"
                f"--- ERROR ---\n{last_error}\n\n"
                f"--- SCRIPT ---\n{current_script}\n\n"
                f"Fix the script. "
                f"Export path must be: {export_path.replace(chr(92), '/')}\n"
                f"Export format must be: {export_format}"
            )
            try:
                raw_fixed = _llm_call(
                    system=_FIX_SYSTEM_PROMPT,
                    user_text=fix_prompt,
                    models=_get_code_models(),
                    max_tokens=16384,
                )
                current_script = _clean_and_patch_script(
                    raw_fixed,
                    export_path.replace("\\", "/"),
                    export_format,
                    image_path.replace("\\", "/"),
                )
            except Exception as fix_exc:
                raise RuntimeError(
                    f"Script execution failed and LLM fix also failed.\n"
                    f"Blender error:\n{last_error}\n"
                    f"Fix error: {fix_exc}"
                ) from fix_exc

    raise RuntimeError(
        f"Blender script failed after {MAX_RETRIES + 1} attempts.\n"
        f"Last error:\n{last_error}"
    )

def blender_agent_create_from_image(
    image_path: Optional[str] = None,
    prompt: Optional[str] = None,
    name: Optional[str] = None,
    output_path: Optional[str] = None,
    output_format: str = "glb",
) -> str:
    """Create a detailed 3-D model from an image or text prompt using the direct Tripo API.

    Saves the resulting model to the blender_assets/ folder inside .utim_tmp/ directory.
    """
    from utim_cli.tools import generate_3d_model
    import os
    import re
    import uuid

    if not image_path and not prompt:
        return "Error: Please provide either an image_path or a text prompt for 3D model generation."

    task_type = "image_to_model" if image_path else "text_to_model"
    safe_name = name or f"blender_{uuid.uuid4().hex[:8]}"
    
    # Map 'blend' or other formats to glb if needed
    tripo_format = output_format if output_format in ("glb", "obj") else "glb"
    res = generate_3d_model(
        type=task_type,
        prompt=prompt,
        image_path=image_path,
        name=safe_name,
        output_format=tripo_format
    )
    
    return f"[Blender Agent] Tripo direct API generation response:\n{res}"
