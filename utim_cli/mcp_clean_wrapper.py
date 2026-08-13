import sys
import subprocess
import threading

def forward_stream(source, dest, filter_json=False):
    try:
        for line in source:
            if filter_json:
                # Check if the line starts with '{' (ignoring leading whitespace)
                stripped = line.strip()
                if stripped.startswith(b'{'):
                    dest.write(line)
                    dest.flush()
                else:
                    # Redirect plain text logging to stderr
                    sys.stderr.buffer.write(b"[stdout-log] " + line)
                    sys.stderr.buffer.flush()
            else:
                dest.write(line)
                dest.flush()
    except Exception:
        pass

def main():
    import os
    import shutil

    if len(sys.argv) < 2:
        sys.exit(1)
        
    cmd = sys.argv[1:]
    
    # Shebang resolution for Termux/Unix script compatibility
    if os.name != 'nt' and cmd:
        executable = cmd[0]
        if os.path.exists(executable) and os.path.isfile(executable):
            try:
                with open(executable, 'rb') as f:
                    first_line = f.readline()
                if first_line.startswith(b'#!'):
                    shebang = first_line[2:].decode('utf-8', errors='ignore').strip()
                    parts = shebang.split()
                    if parts:
                        interpreter = parts[0]
                        interpreter_args = parts[1:]
                        interpreter_name = os.path.basename(interpreter)
                        
                        if interpreter_name == 'env' and len(parts) > 1:
                            real_interpreter = parts[1]
                            resolved_interpreter = shutil.which(real_interpreter) or real_interpreter
                            cmd = [resolved_interpreter] + parts[2:] + cmd
                        else:
                            resolved_interpreter = shutil.which(interpreter_name) or interpreter
                            cmd = [resolved_interpreter] + interpreter_args + cmd
            except Exception:
                pass

    # On Windows, using shell=False is safer when commands are resolved to absolute paths,
    # as it prevents argument double-quoting bugs with cmd.exe command line construction.
    use_shell = False
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        shell=use_shell
    )
    
    t_in = threading.Thread(target=forward_stream, args=(sys.stdin.buffer, proc.stdin), daemon=True)
    t_out = threading.Thread(target=forward_stream, args=(proc.stdout, sys.stdout.buffer, True), daemon=True)
    t_err = threading.Thread(target=forward_stream, args=(proc.stderr, sys.stderr.buffer), daemon=True)
    
    t_in.start()
    t_out.start()
    t_err.start()
    
    proc.wait()
    sys.exit(proc.returncode)

if __name__ == '__main__':
    main()
