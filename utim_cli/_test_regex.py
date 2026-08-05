import re

# Test the full noise string
text = "System.Management.Automation.PSCustomObjectSystem.Object1Preparing modules for first use.0-1-1Completed-1"

# Broader pattern: match the whole PowerShell startup noise line
_PS_NOISE_RE = re.compile(
    r'System\.Management\.Automation\..*?(?:Completed-\d+|$)|'
    r'Preparing modules for first use\..*?(?:Completed-\d+|$)|'
    r'out-file\s*:\s*FileStream was asked to open a device.*?(?:$|\n)|'
    r'For support for devices like.*?(?:$|\n)|'
    r'call CreateFile, then use the FileStream.*?(?:$|\n)|'
    r'CategoryInfo\s*:\s*OpenError.*?(?:$|\n)|'
    r'FullyQualifiedErrorId\s*:\s*FileOpenFailure.*?(?:$|\n)|'
    r'At line:\d+ char:\d+.*?(?:$|\n)',
    re.IGNORECASE | re.DOTALL
)

result = _PS_NOISE_RE.sub("", text).strip()
print(f"Input:  {repr(text)}")
print(f"Output: {repr(result)}")
print(f"Empty:  {result == ''}")