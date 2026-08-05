Get-ChildItem -Path 'C:\Users\user\.utim' -Recurse -Filter '*.py' -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) } |
  Select-Object -First 30 FullName, LastWriteTime
