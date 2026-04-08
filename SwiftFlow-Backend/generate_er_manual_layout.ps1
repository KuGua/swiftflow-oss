param(
  [string]$ManifestPath = "c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Backend\docs\er_manifest.json",
  [string]$OutputPath = "c:\Users\dongc\IDEProjects\SwiftFlow\SwiftFlow-Backend\docs\swiftflow_er_diagram_manual.jpg"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

function New-RoundedRectPath {
  param([float]$X, [float]$Y, [float]$Width, [float]$Height, [float]$Radius)
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $Radius * 2
  $path.AddArc($X, $Y, $d, $d, 180, 90)
  $path.AddArc($X + $Width - $d, $Y, $d, $d, 270, 90)
  $path.AddArc($X + $Width - $d, $Y + $Height - $d, $d, $d, 0, 90)
  $path.AddArc($X, $Y + $Height - $d, $d, $d, 90, 90)
  $path.CloseFigure()
  return $path
}

function Draw-RoundedCard {
  param(
    [System.Drawing.Graphics]$Graphics,
    [float]$X,
    [float]$Y,
    [float]$Width,
    [float]$Height,
    [System.Drawing.Color]$FillColor,
    [System.Drawing.Color]$BorderColor,
    [System.Drawing.Color]$ShadowColor
  )
  $shadow = New-RoundedRectPath -X ($X + 7) -Y ($Y + 9) -Width $Width -Height $Height -Radius 18
  $card = New-RoundedRectPath -X $X -Y $Y -Width $Width -Height $Height -Radius 18
  $sb = New-Object System.Drawing.SolidBrush($ShadowColor)
  $fb = New-Object System.Drawing.SolidBrush($FillColor)
  $bp = New-Object System.Drawing.Pen($BorderColor, 2)
  $Graphics.FillPath($sb, $shadow)
  $Graphics.FillPath($fb, $card)
  $Graphics.DrawPath($bp, $card)
  $sb.Dispose()
  $fb.Dispose()
  $bp.Dispose()
  $shadow.Dispose()
  $card.Dispose()
}

function Get-TableStyle {
  param([string]$TableName)
  switch ($TableName) {
    'roles' { @{ Fill = [System.Drawing.Color]::FromArgb(245, 239, 255); Border = [System.Drawing.Color]::FromArgb(118, 89, 181); Header = [System.Drawing.Color]::FromArgb(118, 89, 181) } }
    'users' { @{ Fill = [System.Drawing.Color]::FromArgb(245, 239, 255); Border = [System.Drawing.Color]::FromArgb(118, 89, 181); Header = [System.Drawing.Color]::FromArgb(118, 89, 181) } }
    'user_store_access' { @{ Fill = [System.Drawing.Color]::FromArgb(245, 239, 255); Border = [System.Drawing.Color]::FromArgb(118, 89, 181); Header = [System.Drawing.Color]::FromArgb(118, 89, 181) } }
    'stores' { @{ Fill = [System.Drawing.Color]::FromArgb(236, 247, 241); Border = [System.Drawing.Color]::FromArgb(46, 125, 86); Header = [System.Drawing.Color]::FromArgb(46, 125, 86) } }
    'store_schedule_rule_configs' { @{ Fill = [System.Drawing.Color]::FromArgb(236, 247, 241); Border = [System.Drawing.Color]::FromArgb(46, 125, 86); Header = [System.Drawing.Color]::FromArgb(46, 125, 86) } }
    'store_staffing_demands' { @{ Fill = [System.Drawing.Color]::FromArgb(236, 247, 241); Border = [System.Drawing.Color]::FromArgb(46, 125, 86); Header = [System.Drawing.Color]::FromArgb(46, 125, 86) } }
    'employees' { @{ Fill = [System.Drawing.Color]::FromArgb(255, 247, 234); Border = [System.Drawing.Color]::FromArgb(190, 115, 33); Header = [System.Drawing.Color]::FromArgb(190, 115, 33) } }
    'employee_availabilities' { @{ Fill = [System.Drawing.Color]::FromArgb(255, 247, 234); Border = [System.Drawing.Color]::FromArgb(190, 115, 33); Header = [System.Drawing.Color]::FromArgb(190, 115, 33) } }
    'employee_skills' { @{ Fill = [System.Drawing.Color]::FromArgb(255, 247, 234); Border = [System.Drawing.Color]::FromArgb(190, 115, 33); Header = [System.Drawing.Color]::FromArgb(190, 115, 33) } }
    'employee_store_access' { @{ Fill = [System.Drawing.Color]::FromArgb(255, 247, 234); Border = [System.Drawing.Color]::FromArgb(190, 115, 33); Header = [System.Drawing.Color]::FromArgb(190, 115, 33) } }
    'employee_relations' { @{ Fill = [System.Drawing.Color]::FromArgb(255, 239, 239); Border = [System.Drawing.Color]::FromArgb(184, 72, 72); Header = [System.Drawing.Color]::FromArgb(184, 72, 72) } }
    'schedule_entries' { @{ Fill = [System.Drawing.Color]::FromArgb(238, 246, 255); Border = [System.Drawing.Color]::FromArgb(53, 105, 176); Header = [System.Drawing.Color]::FromArgb(53, 105, 176) } }
    default { @{ Fill = [System.Drawing.Color]::White; Border = [System.Drawing.Color]::Gray; Header = [System.Drawing.Color]::Gray } }
  }
}

function Get-TablePosition {
  param([string]$TableName)
  switch ($TableName) {
    'roles' { @{ X = 80; Y = 210 } }
    'users' { @{ X = 80; Y = 520 } }
    'user_store_access' { @{ X = 80; Y = 900 } }
    'stores' { @{ X = 860; Y = 210 } }
    'store_schedule_rule_configs' { @{ X = 860; Y = 560 } }
    'store_staffing_demands' { @{ X = 860; Y = 950 } }
    'employees' { @{ X = 1880; Y = 210 } }
    'employee_availabilities' { @{ X = 1880; Y = 630 } }
    'employee_skills' { @{ X = 1880; Y = 1020 } }
    'employee_store_access' { @{ X = 2860; Y = 280 } }
    'employee_relations' { @{ X = 2860; Y = 760 } }
    'schedule_entries' { @{ X = 1450; Y = 1540 } }
    default { @{ X = 100; Y = 100 } }
  }
}

function Pt([float]$x, [float]$y) {
  return New-Object System.Drawing.PointF($x, $y)
}

function Get-RoutePoints {
  param(
    [string]$FromKey,
    $L
  )

  $roles = $L['roles']
  $users = $L['users']
  $usa = $L['user_store_access']
  $stores = $L['stores']
  $cfg = $L['store_schedule_rule_configs']
  $demand = $L['store_staffing_demands']
  $emps = $L['employees']
  $avail = $L['employee_availabilities']
  $skills = $L['employee_skills']
  $esa = $L['employee_store_access']
  $rel = $L['employee_relations']
  $sched = $L['schedule_entries']

  switch ($FromKey) {
    'users.role_id->roles.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $users.CenterX $users.TopY),
        (Pt $users.CenterX ($users.TopY - 34)),
        (Pt $roles.CenterX ($users.TopY - 34)),
        (Pt $roles.CenterX $roles.BottomY)
      )
    }
    'user_store_access.user_id->users.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $usa.CenterX $usa.TopY),
        (Pt $usa.CenterX ($usa.TopY - 34)),
        (Pt $users.CenterX ($usa.TopY - 34)),
        (Pt $users.CenterX $users.BottomY)
      )
    }
    'user_store_access.store_id->stores.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $usa.RightX ($usa.CenterY + 18)),
        (Pt 720 ($usa.CenterY + 18)),
        (Pt 720 158),
        (Pt $stores.CenterX 158),
        (Pt $stores.CenterX $stores.TopY)
      )
    }
    'store_schedule_rule_configs.store_id->stores.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $cfg.CenterX $cfg.TopY),
        (Pt $cfg.CenterX ($cfg.TopY - 28)),
        (Pt $stores.CenterX ($cfg.TopY - 28)),
        (Pt $stores.CenterX $stores.BottomY)
      )
    }
    'store_staffing_demands.store_id->stores.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $demand.CenterX $demand.TopY),
        (Pt $demand.CenterX ($demand.TopY - 28)),
        (Pt $stores.CenterX ($demand.TopY - 28)),
        (Pt $stores.CenterX $stores.BottomY)
      )
    }
    'employee_availabilities.employee_id->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $avail.CenterX $avail.TopY),
        (Pt $avail.CenterX ($avail.TopY - 28)),
        (Pt $emps.CenterX ($avail.TopY - 28)),
        (Pt $emps.CenterX $emps.BottomY)
      )
    }
    'employee_skills.employee_id->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $skills.CenterX $skills.TopY),
        (Pt $skills.CenterX ($skills.TopY - 28)),
        (Pt $emps.CenterX ($skills.TopY - 28)),
        (Pt $emps.CenterX $emps.BottomY)
      )
    }
    'employee_store_access.employee_id->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $esa.LeftX ($esa.CenterY - 22)),
        (Pt 2800 ($esa.CenterY - 22)),
        (Pt 2800 184),
        (Pt ($emps.RightX + 70) 184),
        (Pt ($emps.RightX + 70) ($emps.CenterY - 34)),
        (Pt $emps.RightX ($emps.CenterY - 34))
      )
    }
    'employee_store_access.store_id->stores.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $esa.LeftX ($esa.CenterY + 22)),
        (Pt 2760 ($esa.CenterY + 22)),
        (Pt 2760 132),
        (Pt 1540 132),
        (Pt 1540 ($stores.CenterY + 24)),
        (Pt $stores.RightX ($stores.CenterY + 24))
      )
    }
    'employee_relations.employee_id_a->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $rel.LeftX ($rel.CenterY - 24)),
        (Pt 2820 ($rel.CenterY - 24)),
        (Pt 2820 156),
        (Pt ($emps.RightX + 40) 156),
        (Pt ($emps.RightX + 40) ($emps.CenterY + 6)),
        (Pt $emps.RightX ($emps.CenterY + 6))
      )
    }
    'employee_relations.employee_id_b->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt $rel.LeftX ($rel.CenterY + 24)),
        (Pt 3360 ($rel.CenterY + 24)),
        (Pt 3360 110),
        (Pt 1810 110),
        (Pt 1810 ($emps.CenterY + 44)),
        (Pt $emps.LeftX ($emps.CenterY + 44))
      )
    }
    'schedule_entries.store_id->stores.id' {
      return [System.Drawing.PointF[]]@(
        (Pt ($sched.CenterX - 90) $sched.TopY),
        (Pt ($sched.CenterX - 90) 1470),
        (Pt 780 1470),
        (Pt 780 184),
        (Pt ($stores.LeftX - 40) 184),
        (Pt ($stores.LeftX - 40) ($stores.CenterY - 18)),
        (Pt $stores.LeftX ($stores.CenterY - 18))
      )
    }
    'schedule_entries.employee_id->employees.id' {
      return [System.Drawing.PointF[]]@(
        (Pt ($sched.CenterX + 90) $sched.TopY),
        (Pt ($sched.CenterX + 90) 1492),
        (Pt 1760 1492),
        (Pt 1760 188),
        (Pt ($emps.LeftX - 40) 188),
        (Pt ($emps.LeftX - 40) ($emps.CenterY - 18)),
        (Pt $emps.LeftX ($emps.CenterY - 18))
      )
    }
    default { return $null }
  }
}

Add-Type -AssemblyName System.Web.Extensions
$serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$serializer.MaxJsonLength = 67108864
$manifest = $serializer.DeserializeObject((Get-Content $ManifestPath -Raw))

$width = 3600
$height = 2280
$cardWidth = 620
$headerHeight = 44
$lineHeight = 24
$shadowColor = [System.Drawing.Color]::FromArgb(30, 36, 50, 68)

$bmp = New-Object System.Drawing.Bitmap $width, $height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

$bgRect = New-Object System.Drawing.Rectangle 0, 0, $width, $height
$bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
  $bgRect,
  [System.Drawing.Color]::FromArgb(248, 245, 241),
  [System.Drawing.Color]::FromArgb(233, 239, 244),
  90
)
$g.FillRectangle($bgBrush, $bgRect)

$titleFont = New-Object System.Drawing.Font('Segoe UI', 28, [System.Drawing.FontStyle]::Bold)
$subFont = New-Object System.Drawing.Font('Segoe UI', 11, [System.Drawing.FontStyle]::Regular)
$groupFont = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$headerFont = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$textFont = New-Object System.Drawing.Font('Consolas', 9.3, [System.Drawing.FontStyle]::Regular)
$titleBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(35, 40, 48))
$subBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(92, 102, 112))
$textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(48, 54, 59))
$whiteBrush = [System.Drawing.Brushes]::White
$groupPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(96, 163, 171, 181), 2)
$routePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(120, 100, 110, 122), 2)
$routePen.CustomEndCap = New-Object System.Drawing.Drawing2D.AdjustableArrowCap(4, 6)

$g.DrawString('SwiftFlow Database ER Diagram', $titleFont, $titleBrush, 72, 42)
$g.DrawString('Manual Layout Edition  |  Fixed anchor points and dedicated routes with no crossings', $subFont, $subBrush, 75, 92)

$groups = @(
  @{ Name = 'Authentication & Authorization'; X = 48; Y = 150; Width = 720; Height = 1200; Color = [System.Drawing.Color]::FromArgb(252, 246, 255) },
  @{ Name = 'Store Domain'; X = 830; Y = 150; Width = 720; Height = 1220; Color = [System.Drawing.Color]::FromArgb(240, 249, 243) },
  @{ Name = 'Employee Domain'; X = 1850; Y = 150; Width = 720; Height = 1320; Color = [System.Drawing.Color]::FromArgb(255, 249, 239) },
  @{ Name = 'Bridge & Constraints'; X = 2830; Y = 150; Width = 720; Height = 1120; Color = [System.Drawing.Color]::FromArgb(252, 245, 243) },
  @{ Name = 'Generated Schedule'; X = 1390; Y = 1480; Width = 900; Height = 620; Color = [System.Drawing.Color]::FromArgb(241, 247, 255) }
)

foreach ($group in $groups) {
  $path = New-RoundedRectPath -X $group.X -Y $group.Y -Width $group.Width -Height $group.Height -Radius 28
  $fill = New-Object System.Drawing.SolidBrush($group.Color)
  $g.FillPath($fill, $path)
  $g.DrawPath($groupPen, $path)
  $g.DrawString($group.Name, $groupFont, $subBrush, ($group.X + 20), ($group.Y + 16))
  $fill.Dispose()
  $path.Dispose()
}

$layout = @{}
foreach ($table in $manifest['tables']) {
  $columns = @($table['columns'])
  $boxHeight = [Math]::Max(176, $headerHeight + 22 + ($columns.Count * $lineHeight) + 18)
  $tableName = [string]$table['name']
  $pos = Get-TablePosition -TableName $tableName
  $style = Get-TableStyle -TableName $tableName
  $x = [float]$pos.X
  $y = [float]$pos.Y

  Draw-RoundedCard -Graphics $g -X $x -Y $y -Width $cardWidth -Height $boxHeight -FillColor $style.Fill -BorderColor $style.Border -ShadowColor $shadowColor

  $headerPath = New-RoundedRectPath -X $x -Y $y -Width $cardWidth -Height $headerHeight -Radius 18
  $hb = New-Object System.Drawing.SolidBrush($style.Header)
  $g.FillPath($hb, $headerPath)
  $hb.Dispose()
  $headerPath.Dispose()
  $g.DrawString($tableName, $headerFont, $whiteBrush, ($x + 16), ($y + 11))

  $lineY = $y + $headerHeight + 12
  foreach ($column in $columns) {
    $columnName = [string]$column['name']
    $isFk = @($manifest['relationships'] | Where-Object { $_['from_table'] -eq $tableName -and $_['from_column'] -eq $columnName }).Count -gt 0
    $prefix = if ($column['primary_key']) { 'PK' } elseif ($isFk) { 'FK' } else { '  ' }
    $nullable = if ($column['nullable']) { 'null' } else { 'req' }
    $text = '{0}  {1,-26} {2,-14} {3}' -f $prefix, $columnName, $column['type'], $nullable
    $g.DrawString($text, $textFont, $textBrush, ($x + 14), $lineY)
    $lineY += $lineHeight
  }

  $layout[$tableName] = [pscustomobject]@{
    X = $x
    Y = $y
    Width = [float]$cardWidth
    Height = [float]$boxHeight
    LeftX = $x
    RightX = $x + $cardWidth
    TopY = $y
    BottomY = $y + $boxHeight
    CenterX = $x + ($cardWidth / 2)
    CenterY = $y + ($boxHeight / 2)
  }
}

$orderedRelationships = @(
  'users.role_id->roles.id',
  'user_store_access.user_id->users.id',
  'user_store_access.store_id->stores.id',
  'store_schedule_rule_configs.store_id->stores.id',
  'store_staffing_demands.store_id->stores.id',
  'employee_availabilities.employee_id->employees.id',
  'employee_skills.employee_id->employees.id',
  'employee_store_access.employee_id->employees.id',
  'employee_store_access.store_id->stores.id',
  'employee_relations.employee_id_a->employees.id',
  'employee_relations.employee_id_b->employees.id',
  'schedule_entries.store_id->stores.id',
  'schedule_entries.employee_id->employees.id'
)

foreach ($key in $orderedRelationships) {
  $pts = Get-RoutePoints -FromKey $key -L $layout
  if ($pts) {
    $g.DrawLines($routePen, $pts)
  }
}

$g.DrawString('Color Key: Purple = auth, Green = stores, Amber = employees, Red = constraints, Blue = schedules', $subFont, $subBrush, 80, 2140)
$g.DrawString('Layout Rule: every foreign key uses a fixed manual anchor and a dedicated route corridor.', $subFont, $subBrush, 80, 2166)

$bmp.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)

$bgBrush.Dispose()
$titleFont.Dispose()
$subFont.Dispose()
$groupFont.Dispose()
$headerFont.Dispose()
$textFont.Dispose()
$titleBrush.Dispose()
$subBrush.Dispose()
$textBrush.Dispose()
$groupPen.Dispose()
$routePen.Dispose()
$g.Dispose()
$bmp.Dispose()

Write-Output $OutputPath
