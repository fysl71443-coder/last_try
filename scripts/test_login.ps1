param(
  [string]$Base = 'https://mt-m-lqry-lsyny.onrender.com',
  [string]$User = 'admin',
  [string]$Pass = 'admin123'
)

$ErrorActionPreference = 'Stop'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) GET /login
$r1 = Invoke-WebRequest -Uri ("$Base/login") -WebSession $session -MaximumRedirection 5
Write-Host ("GET /login: {0}" -f $r1.StatusCode)
$html = $r1.Content
$csrf = $null
$match = [Regex]::Match($html, 'name=["' + "'" + ']csrf_token["' + "'" + '][^>]*value=["' + "'" + ']([^"' + "'" + ']+)["' + "'" + ']', 'IgnoreCase')
if($match.Success){ $csrf = $match.Groups[1].Value }
Write-Host ("csrf_token found: {0}" -f ([bool]$csrf))

# 2) POST /login
$body = @{ username=$User; password=$Pass }
if($csrf){ $body['csrf_token'] = $csrf }
$r2 = Invoke-WebRequest -Uri ("$Base/login") -Method Post -Body $body -WebSession $session -MaximumRedirection 5 -AllowUnencryptedAuthentication
Write-Host ("POST /login: {0}" -f $r2.StatusCode)
$finalUrl = $r2.BaseResponse.ResponseUri.AbsoluteUri
Write-Host ("Final URL: $finalUrl")

$contentLow = ($r2.Content | Out-String).ToLowerInvariant()
$ok = ($contentLow -like '*logout*') -or ($contentLow -like '*china town*') -or ($contentLow -like '*dashboard*')
Write-Host ("Heuristic success: $ok")

# 3) GET /
$r3 = Invoke-WebRequest -Uri ("$Base/") -WebSession $session -MaximumRedirection 5
Write-Host ("GET /: {0}" -f $r3.StatusCode)
$homeLow = ($r3.Content | Out-String).ToLowerInvariant()
$hasLogout = ($homeLow -like '*logout*') -or ($homeLow -like '*تسجيل الخروج*')
Write-Host ("Home has logout?: $hasLogout")

