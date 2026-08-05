Add-Type -AssemblyName System.Drawing
$src = 'C:\Users\user\Desktop\New folder\New folder\error.jpeg'
$img = [System.Drawing.Image]::FromFile($src)
$bmp = New-Object System.Drawing.Bitmap $img
$bmp.Save('C:\Users\user\Desktop\New folder\New folder\error.png', [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
$bmp.Dispose()
Write-Host "Converted to PNG"
