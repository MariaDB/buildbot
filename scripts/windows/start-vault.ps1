# Deploy in WIN_MSI_VAULT_ROOT
try {
    # Kill any existing Vault processes
    Get-Process vault -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force
        Write-Host "Killed Vault process $($_.Id)"
    }

    # Set environment variables for dev mode
    $env:VAULT_DEV_ROOT_TOKEN_ID = "MTR"
    $env:VAULT_ADDR = "http://127.0.0.1:8200"


    Start-Sleep -Seconds 1 # For old Vault process to exit

    # Start Vault in detached mode using Start-Process
    Start-Process -FilePath "C:\vault\vault.exe" `
                  -ArgumentList "server -dev" `
                  -WindowStyle Hidden `

    Write-Host "Vault started in dev mode. PID: $((Get-Process vault).Id)"
    exit 0
}
catch {
    Write-Host "Failed to start Vault: $_"
    exit 1
}