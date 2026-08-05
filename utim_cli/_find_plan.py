f = open('tools.py', encoding='utf-8').read()
idx = f.find('def plan_project')
# Find the next def or the end of the function
rest = f[idx:]
# Find the save-to-file part
save_idx = rest.find('.utim_tmp/plans/')
print(f"plan_project starts at: {idx}")
print(f"save file reference at: {idx + save_idx}")
print()
# Show the save block
block = rest[save_idx-100:save_idx+500]
print(block)