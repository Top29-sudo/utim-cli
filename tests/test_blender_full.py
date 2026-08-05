import os
import sys
if "pytest" in sys.modules:
    import pytest
    pytest.skip("Skipping standalone script during pytest discovery", allow_module_level=True)
os.environ['UTIM_BLENDER_PATH'] = r'E:\Blender\blender.exe'

from utim_cli.blender_agent import blender_agent_create_from_image

if __name__ == "__main__":
    print('Testing enhanced Blender agent...')
    result = blender_agent_create_from_image(
        image_path=r'E:/Blender/suku.jpg',
        name='suku_enhanced',
        output_format='glb'
    )
    print(result)