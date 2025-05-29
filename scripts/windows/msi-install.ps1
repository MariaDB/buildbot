param (
    [int]$Port = 3306,
    [string]$InstallDir = "C:\Program Files\MariaDB",
    [string]$ServiceName = "MariaDB",
    [string]$BuildDir = "."
)

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
