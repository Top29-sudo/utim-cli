from PIL import Image
img = Image.open(r'C:\Users\user\Desktop\New folder\New folder\error.png')
# Resize to smaller for faster inspection
w, h = img.size
new_w = 800
new_h = int(h * new_w / w)
img2 = img.resize((new_w, new_h), Image.LANCZOS)
img2.save(r'C:\Users\user\Desktop\New folder\New folder\error_small.png')
print(f"Resized to {new_w}x{new_h}")
# Sample some pixel data to understand content
import numpy as np
arr = np.array(img)
print("Shape:", arr.shape)
print("Mean color:", arr.mean(axis=(0,1)))
print("Min:", arr.min(), "Max:", arr.max())
# Check if it's mostly one color (screenshot of error) or varied
unique_colors = len(np.unique(arr.reshape(-1, arr.shape[-1]), axis=0))
print(f"Unique colors: {unique_colors}")
