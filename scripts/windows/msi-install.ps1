param (
    [int]$Port = 3306,
    [string]$InstallDir = "C:\Program Files\MariaDB",
    [string]$ServiceName = "MariaDB",
    [string]$BuildDir = "."
)

# Clean up leftovers of a previous test run that did not complete its
# uninstall (e.g. was killed, or the uninstall failed to remove files).
# A leftover data directory makes the MSI installation fail with
# "data directory exists and is not empty", permanently, until the
# worker is cleaned.
$svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    Write-Output "Removing leftover service $ServiceName"
    if ($svc.Status -ne 'Stopped') {
        Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
        try { $svc.WaitForStatus('Stopped', '00:01:00') } catch {}
    }
    sc.exe delete $ServiceName | Out-Null
}
if (Test-Path $InstallDir) {
    Write-Output "Removing leftover installation directory $InstallDir"
    Remove-Item -Recurse -Force $InstallDir
}

# Look for the first MariaDB MSI file in the $BuildDir
$msiFile = Get-ChildItem -Path $BuildDir -Filter "mariadb-*.msi" | Select-Object -First 1

if (-not $msiFile) {
    Write-Error "ERROR: No MariaDB MSI file found."
    exit 1
}

Write-Output "Found installer: $($msiFile.Name)"

# Log file
$logFile = "msi_install.txt"

# Arguments for msiexec
$arguments = @(
    "/i `"$($msiFile.FullName)`"",
    "PORT=$Port",
    "INSTALLDIR=`"$InstallDir`"",
    "SERVICENAME=$ServiceName",
    "/qn",
    "/l*v `"$logFile`""
)

Write-Output "Starting installation..."
$process = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru

if ($process.ExitCode -ne 0) {
    Write-Error "ERROR: Installation failed with exit code $($process.ExitCode)"
    Get-Content $logFile
    exit 1
}

Write-Output "Installation completed successfully."
