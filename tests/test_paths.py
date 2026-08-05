import os, re

def _find_image_paths(line):
    results = []
    
    # 1. Find quoted paths
    quoted_pattern = r'("[^"]+"|\'[^\']+\')'
    for m in re.finditer(quoted_pattern, line):
        path = m.group(1)[1:-1]
        print(f"Quoted regex matched path: {path}")
        if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
            if os.path.isfile(path):
                results.append((m.start(), m.end(), path, True))
            else:
                print(f"Not a file (quoted): {path}")
                
    # 2. Find unquoted paths by looking backwards from extensions
    ext_pattern = r'(?i)(\.(?:png|jpg|jpeg|gif|webp|bmp))(?!\w)'
    for m in re.finditer(ext_pattern, line):
        end_idx = m.end()
        if any(start <= end_idx <= end for start, end, _, _ in results):
            continue
            
        prefix_text = line[:end_idx]
        parts = prefix_text.split(' ')
        
        valid_path = None
        valid_start = -1
        current_path_parts = []
        
        for i in range(len(parts)-1, -1, -1):
            current_path_parts.insert(0, parts[i])
            test_path = ' '.join(current_path_parts)
            if os.path.isfile(test_path):
                valid_path = test_path
                valid_start = end_idx - len(test_path)
                break
            if test_path.startswith('@') and os.path.isfile(test_path[1:]):
                valid_path = test_path[1:]
                valid_start = end_idx - len(test_path) + 1
                break
                
        if valid_path:
            results.append((valid_start, end_idx, valid_path, False))
        else:
            print(f"No file found (unquoted) ending at {end_idx}")
            
    results.sort(key=lambda x: x[0])
    return results

if __name__ == "__main__":
    print("Testing unquoted...")
    print(_find_image_paths('even after compression the ai is still sending huge amounts of tokens "⊘ Token limit nearing capacity (>75k): compressing intermediate tool logs..." "C:\\Users\\user\\Pictures\\Screenshots\\Screenshot 2026-05-18 150204.png"'))

    print("\nTesting without quotes around path...")
    print(_find_image_paths('even after compression the ai is still sending huge amounts of tokens C:\\Users\\user\\Pictures\\Screenshots\\Screenshot 2026-05-18 150204.png'))

