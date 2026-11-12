# Creates the MM Core icons on the Windows desktop (and in the Start menu).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$shell = New-Object -ComObject WScript.Shell
$targets = @(
  @{ Name = "MM Core Dashboard"; Bat = "MM Core Dashboard.bat"; Icon = "mm_dashboard.ico"; Text = "ERP dashboard (live KPIs)" },
  @{ Name = "MM Core";           Bat = "Start MM Core.bat";     Icon = "mm_core.ico";      Text = "MM Core (browser)" },
  @{ Name = "MM Core Logon";     Bat = "MM Core Logon.bat";     Icon = "mm_logon.ico";     Text = "MM Core Logon / Easy Access" },
  @{ Name = "MM Core Mobile";    Bat = "MM Core Mobile.bat";    Icon = "mm_dashboard.ico"; Text = "Dashboard on the phone (QR code, live)" }
)
$folders = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("Programs")) "MM Core"))
foreach ($f in $folders) { if (-not (Test-Path $f)) { New-Item -ItemType Directory -Path $f | Out-Null } }
foreach ($t in $targets) {
  foreach ($f in $folders) {
    $lnk = $shell.CreateShortcut((Join-Path $f ($t.Name + ".lnk")))
    $lnk.TargetPath = Join-Path $root $t.Bat
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = (Join-Path $root ("icons\" + $t.Icon)) + ",0"
    $lnk.WindowStyle = 7
    $lnk.Description = $t.Text
    $lnk.Save()
  }
  Write-Host ("  created: " + $t.Name)
}
Write-Host ""
Write-Host "The icons are on the desktop and in the Start menu (folder MM Core)."
