import os
import sys
sys.path.insert(0, 'utim_cli')
if "pytest" in sys.modules:
    import pytest
    pytest.skip("Skipping standalone script during pytest discovery", allow_module_level=True)
os.environ['UTIM_BLENDER_PATH'] = 'E:/Blender/blender.exe'

from blender_agent import blender_agent_create_from_image

if __name__ == "__main__":
    print("Running full Blender agent pipeline on suku.jpg...")
    result = blender_agent_create_from_image('E:/Blender/suku.jpg', 'suku_character', output_format='blend')
    print(result)