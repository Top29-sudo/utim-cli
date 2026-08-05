f = open('orchestrator.py', encoding='utf-8').read()

# Find the single tool append (second occurrence of _cap_tool_result)
idx1 = f.find('result = _cap_tool_result(func_name, result)')
idx2 = f.find('result = _cap_tool_result(func_name, result)', idx1 + 50)

# The single append starts at idx2 and ends at the "# --- Repeated Tool" line
end_marker = '\n            # --- Repeated Tool '
end_idx = f.find(end_marker, idx2)

old_block = f[idx2:end_idx]
print("=== OLD BLOCK ===")
print(repr(old_block))
print()

# Build new block
new_block = '''result = _cap_tool_result(func_name, result)

                    # If result is an [Image: path] marker and model is vision-capable,
                    # inject the actual image as multimodal content
                    _img_match = __import__("re").match(r"^\\[Image:\\s+(.+)\\]$", result.strip())
                    if _img_match and func_name in ("read_file",):
                        try:
                            from utim_cli.tools import is_model_vision_capable
                            if is_model_vision_capable():
                                _img_path = _img_match.group(1)
                                _multimodal = _tool_result_to_multimodal(result, _img_path)
                                self.messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "name": func_name,
                                        "content": _multimodal,
                                    }
                                )
                            else:
                                self.messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "name": func_name,
                                        "content": result,
                                    }
                                )
                        except Exception:
                            self.messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": func_name,
                                    "content": result,
                                }
                            )
                    else:
                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": func_name,
                                "content": result,
                            }
                        )'''

f = f.replace(old_block, new_block)

# Now do the parallel one (first occurrence)
idx1_end = f.find(end_marker, f.find('result = _cap_tool_result(func_name, result)'))
# Actually the parallel one ends differently - find its actual end
# It's followed by "            else:" not "# --- Repeated Tool"
old_para_end_marker = '\n            else:\n                # Single tool'
old_para_start = f.find('result = _cap_tool_result(func_name, result)')
old_para_end = f.find(old_para_end_marker, old_para_start)
old_para_block = f[old_para_start:old_para_end]

new_para_block = '''result = _cap_tool_result(func_name, result)

                    # If result is an [Image: path] marker and model is vision-capable,
                    # inject the actual image as multimodal content
                    _img_match = __import__("re").match(r"^\\[Image:\\s+(.+)\\]$", result.strip())
                    if _img_match and func_name in ("read_file",):
                        try:
                            from utim_cli.tools import is_model_vision_capable
                            if is_model_vision_capable():
                                _img_path = _img_match.group(1)
                                _multimodal = _tool_result_to_multimodal(result, _img_path)
                                self.messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "name": func_name,
                                        "content": _multimodal,
                                    }
                                )
                            else:
                                self.messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "name": func_name,
                                        "content": result,
                                    }
                                )
                        except Exception:
                            self.messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": func_name,
                                    "content": result,
                                }
                            )
                    else:
                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": func_name,
                                "content": result,
                            }
                        )'''

f = f.replace(old_para_block, new_para_block)

open('orchestrator.py', 'w', encoding='utf-8').write(f)
print("OK: both tool append blocks replaced")