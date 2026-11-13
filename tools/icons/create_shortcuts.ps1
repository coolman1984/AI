# Creates the NERP icons on the Windows desktop (and in the Start menu).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$shell = New-Object -ComObject WScript.Shell
$targets = @(
  @{ Name = "NERP Dashboard"; Bat = "NERP Dashboard.bat"; Icon = "mm_dashboard.ico"; Text = "ERP dashboard (live KPIs)" },
  @{ Name = "NERP";           Bat = "Start NERP.bat";     Icon = "mm_core.ico";      Text = "NERP (browser)" },
  @{ Name = "NERP Logon";     Bat = "NERP Logon.bat";     Icon = "mm_logon.ico";     Text = "NERP Logon / Easy Access" },
  @{ Name = "NERP Mobile";    Bat = "NERP Mobile.bat";    Icon = "mm_dashboard.ico"; Text = "Dashboard on the phone (QR code, live)" }
)
$folders = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("Programs")) "NERP"))
foreach ($f in $folders) { if (-not (Test-Path $f)) { New-Item -ItemType Directory -Path $f | Out-Null } }
# the program was renamed from "MM Core" to "NERP": remove the old shortcuts
foreach ($f in @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("Programs")) "MM Core"))) {
  if (Test-Path $f) { Get-ChildItem -Path $f -Filter "MM Core*.lnk" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue }
}
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
Write-Host "The icons are on the desktop and in the Start menu (folder NERP)."
