$paths = @(
  "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin",
  "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\libnvvp",
  # ... include all your paths here as in previous script
  "C:\Users\amaan\OneDrive\Documents\coding\openai-gptoss-hackathon"
)

$joinedPaths = [string]::Join(";", $paths)

$regPath = "HKCU:\Environment"
Set-ItemProperty -Path $regPath -Name "Path" -Value $joinedPaths

# Notify the system about the environment variable change (so apps refresh)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class NativeMethods {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern IntPtr SendMessageTimeout(
    IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
    uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
}
"@

[void][NativeMethods]::SendMessageTimeout([IntPtr]::Zero, 0x1A, [UIntPtr]::Zero, "Environment", 0x0002, 1000, [ref]0)

Write-Output "User PATH updated in registry. Restart terminal/apps to apply."
