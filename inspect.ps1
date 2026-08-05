Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('C:\Users\user\Desktop\New folder\New folder\error.jpeg')
Write-Host "Size: $($img.Size)"
Write-Host "PixelFormat: $($img.PixelFormat)"
$img.Dispose()
