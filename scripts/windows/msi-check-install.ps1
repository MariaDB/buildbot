param (
    [int]$Port = 3306,
    [string]$InstallDir = "C:\Program Files\MariaDB",
    [string]$BuildDir = "."
)

$mysqldInstalled = Join-Path $InstallDir "bin\mysqld.exe"
$mysqldBuilt = Join-Path $BuildDir "sql\RelWithDebInfo\mysqld.exe"

# 1a. Check if MariaDB is installed
if (-not (Test-Path $mysqldInstalled)) {
    Write-Error "MariaDB not found at $mysqldInstalled"
    exit 1
}
Write-Output "MariaDB installation found at: $InstallDir"

# 1b. Check if built mysqld.exe exists
if (-not (Test-Path $mysqldBuilt)) {
    Write-Error "MariaDB built binary not found at $mysqldBuilt"
    exit 1
}
Write-Output "MariaDB built binary found at: $mysqldBuilt"

# 2. Compare built vs installed mysqld.exe
Write-Output "Checking that built and installed mysqld.exe are identical..."
$hash1 = Get-FileHash $mysqldBuilt -Algorithm SHA256
$hash2 = Get-FileHash $mysqldInstalled -Algorithm SHA256

if ($hash1.Hash -ne $hash2.Hash) {
    Write-Warning "mysqld.exe files differ!"

    Write-Output "`nBuilt mysqld.exe:"
    Get-Item $mysqldBuilt | Format-List Name, Length, LastWriteTime
    & $mysqldBuilt --version

    Write-Output "`nInstalled mysqld.exe:"
    Get-Item $mysqldInstalled | Format-List Name, Length, LastWriteTime
    & $mysqldInstalled --version

    exit 1
}
Write-Output "mysqld.exe files are identical."

# 3. Check if MariaDB server is running and accessible on the given port
$mysqlClient = Join-Path $InstallDir "bin\mysql.exe"

if (-not (Test-Path $mysqlClient)) {
    Write-Error "mysql client not found at $mysqlClient"
    exit 1
}

Write-Output "Checking if the server is running on port $Port..."

try {
    # Run the client
    & $mysqlClient -uroot --port=$Port -e @"
SELECT @@version, @@version_comment;
SHOW STATUS LIKE 'Uptime';
SELECT 'Stat' AS t, variable_name AS name, variable_value AS val
FROM information_schema.global_status
WHERE variable_name LIKE '%have%'
UNION
SELECT 'Vars', variable_name, variable_value
FROM information_schema.global_variables
WHERE variable_name LIKE '%have%'
ORDER BY t, name;
"@
    # Check exit code explicitly
    if ($LASTEXITCODE -ne 0) {
        throw "mysql client exited with code $LASTEXITCODE"
    }
}
catch {
    Write-Error "Could not launch or connect using mysql client: $_"
    exit 1
}


Write-Output "MariaDB is running and responsive on port $Port."
