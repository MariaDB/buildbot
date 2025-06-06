param (
    [string]$BuildDir = "."
)

# Look for the first MariaDB MSI file in the $BuildDir
$msiFile = Get-ChildItem -Path $BuildDir -Filter "mariadb-*.msi" | Select-Object -First 1

if (-not $msiFile) {
    Write-Error "ERROR: No MariaDB MSI file found for uninstall."
    exit 1
}

Write-Output "Found installer for uninstall: $($msiFile.Name)"

# Log file
$logFile = "msi_uninstall.txt"

# Build msiexec arguments for uninstall
$arguments = @(
    "/i `"$($msiFile.FullName)`"",  # Reinstall mode with REMOVE=ALL
    "REMOVE=ALL",
    "/qn",
    "/l*v `"$logFile`""
)

# Run msiexec and wait
Write-Output "Starting uninstallation..."
$process = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru

# Check if uninstall failed
if ($process.ExitCode -ne 0) {
    Write-Error "ERROR: Uninstallation failed with exit code $($process.ExitCode)"
    Get-Content $logFile
    exit 1
}

Write-Output "Uninstallation completed successfully."
