param([Parameter(Mandatory=$true)][string]$RunDirectory)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $RunDirectory
$request = Get-Content -LiteralPath (Join-Path $RunDirectory 'launch.json') -Raw | ConvertFrom-Json
$env:APPDATA = Join-Path $RunDirectory 'appdata'
$env:LOCALAPPDATA = Join-Path $RunDirectory 'localappdata'
$env:TEMP = Join-Path $RunDirectory 'temp'
$env:TMP = $env:TEMP
$p = Start-Process -FilePath $request.java -ArgumentList $request.arguments -WorkingDirectory $RunDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $RunDirectory 'stdout.tmp') -RedirectStandardError (Join-Path $RunDirectory 'stderr.tmp')
$retainedProcessHandle = $p.Handle
[ordered]@{pid=$p.Id;started_at=$p.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'running.json') -Encoding UTF8
foreach ($key in @('PG_USERNAME','PG_PASSWORD')) { [Environment]::SetEnvironmentVariable($key,$null,'Process') }
$p.WaitForExit()
$p.Refresh()
[ordered]@{pid=$p.Id;exit_code=$p.ExitCode;stopped_at=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'exit.json') -Encoding UTF8
foreach ($name in @('stdout.tmp','stderr.tmp')) { Remove-Item -LiteralPath (Join-Path $RunDirectory $name) -ErrorAction SilentlyContinue }
