param(
  [Parameter(Mandatory=$true)]
  [string]$InputPath,
  [Parameter(Mandatory=$true)]
  [string]$OutputDir,
  [string]$RenderSlides = "true"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$shouldRenderSlides = @("1", "true", "yes", "y") -contains $RenderSlides.ToLowerInvariant()

function Safe-Name([string]$Name) {
  $stem = [System.IO.Path]::GetFileNameWithoutExtension($Name)
  $safe = $stem -replace '[\\/:*?"<>|]+', '_'
  if ([string]::IsNullOrWhiteSpace($safe)) { return "office_file" }
  return $safe
}

$inputItem = Get-Item -Path $InputPath
$ext = $inputItem.Extension.ToLowerInvariant()
$safeStem = Safe-Name $inputItem.Name
$textDir = Join-Path $OutputDir "texts"
$renderDir = Join-Path $OutputDir "rendered"
New-Item -ItemType Directory -Force -Path $textDir | Out-Null
New-Item -ItemType Directory -Force -Path $renderDir | Out-Null

$record = [ordered]@{
  source_path = $inputItem.FullName
  source_name = $inputItem.Name
  extension = $ext
  status = "started"
  text_path = $null
  rendered_dir = $null
  tables_dir = $null
  slides = $null
  chars = 0
  warnings = @()
}

function Csv-Escape([object]$Value) {
  if ($null -eq $Value) { return "" }
  $text = [string]$Value
  if ($text.Contains('"') -or $text.Contains(',') -or $text.Contains("`n") -or $text.Contains("`r")) {
    return '"' + ($text -replace '"', '""') + '"'
  }
  return $text
}

if ($ext -eq ".ppt" -or $ext -eq ".pptx") {
  $app = New-Object -ComObject PowerPoint.Application
  try {
    $presentation = $app.Presentations.Open($inputItem.FullName, $true, $true, $false)
    try {
      $lines = New-Object System.Collections.Generic.List[string]
      $lines.Add("# " + $inputItem.Name)
      $lines.Add("")
      $lines.Add("- Source: " + $inputItem.FullName)
      $lines.Add("- Slides: " + $presentation.Slides.Count)
      $lines.Add("")

      $deckRenderDir = Join-Path $renderDir $safeStem
      if ($shouldRenderSlides) {
        New-Item -ItemType Directory -Force -Path $deckRenderDir | Out-Null
      }

      for ($i = 1; $i -le $presentation.Slides.Count; $i++) {
        $slide = $presentation.Slides.Item($i)
        $lines.Add("## Slide " + $i)
        $lines.Add("")
        foreach ($shape in $slide.Shapes) {
          try {
            if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
              $text = $shape.TextFrame.TextRange.Text
              if (-not [string]::IsNullOrWhiteSpace($text)) {
                $text = ($text -replace "`r", "`n").Trim()
                $lines.Add($text)
                $lines.Add("")
              }
            }
          } catch {
            $record.warnings += "Skipped a non-text or legacy shape on slide $i."
          }
        }
        if ($shouldRenderSlides) {
          $png = Join-Path $deckRenderDir ("slide_{0:D2}.png" -f $i)
          $slide.Export($png, "PNG", 1440, 1080)
        }
      }

      $textPath = Join-Path $textDir ($safeStem + ".md")
      [System.IO.File]::WriteAllLines($textPath, $lines, [System.Text.UTF8Encoding]::new($false))
      $record.status = "ok"
      $record.text_path = $textPath
      if ($shouldRenderSlides) { $record.rendered_dir = $deckRenderDir }
      $record.slides = $presentation.Slides.Count
      $record.chars = (Get-Content -Path $textPath -Raw -Encoding UTF8).Length
    } finally {
      $presentation.Close()
    }
  } finally {
    $app.Quit()
  }
} elseif ($ext -eq ".doc" -or $ext -eq ".docx") {
  $app = New-Object -ComObject Word.Application
  $app.Visible = $false
  try {
    $document = $app.Documents.Open($inputItem.FullName, $false, $true)
    try {
      $text = $document.Content.Text
      $lines = @("# " + $inputItem.Name, "", "- Source: " + $inputItem.FullName, "", $text)
      $textPath = Join-Path $textDir ($safeStem + ".txt")
      [System.IO.File]::WriteAllLines($textPath, $lines, [System.Text.UTF8Encoding]::new($false))
      $record.status = "ok"
      $record.text_path = $textPath
      $record.chars = $text.Length
    } finally {
      $document.Close($false)
    }
  } finally {
    $app.Quit()
  }
} elseif ($ext -eq ".xls" -or $ext -eq ".xlsx") {
  $tablesDir = Join-Path $OutputDir "tables"
  $bookTablesDir = Join-Path $tablesDir $safeStem
  New-Item -ItemType Directory -Force -Path $bookTablesDir | Out-Null

  $app = New-Object -ComObject Excel.Application
  $app.Visible = $false
  $app.DisplayAlerts = $false
  try {
    $workbook = $app.Workbooks.Open($inputItem.FullName, 0, $true)
    try {
      $lines = New-Object System.Collections.Generic.List[string]
      $lines.Add("# " + $inputItem.Name)
      $lines.Add("")
      $lines.Add("- Source: " + $inputItem.FullName)
      $lines.Add("- Sheets: " + $workbook.Worksheets.Count)
      $lines.Add("")
      $lines.Add("## Sheets")
      $lines.Add("")

      foreach ($sheet in $workbook.Worksheets) {
        $used = $sheet.UsedRange
        $rows = $used.Rows.Count
        $cols = $used.Columns.Count
        $sheetSafe = ([string]$sheet.Name) -replace '[\\/:*?"<>|]+', '_'
        $csvPath = Join-Path $bookTablesDir ($sheetSafe + ".csv")
        $writer = New-Object System.IO.StreamWriter($csvPath, $false, [System.Text.UTF8Encoding]::new($true))
        try {
          for ($r = 1; $r -le $rows; $r++) {
            $cells = New-Object System.Collections.Generic.List[string]
            for ($c = 1; $c -le $cols; $c++) {
              $cells.Add((Csv-Escape $used.Cells.Item($r, $c).Text))
            }
            $writer.WriteLine(($cells -join ","))
          }
        } finally {
          $writer.Close()
        }
        $lines.Add("- " + $sheet.Name + ": " + $rows + " rows, " + $cols + " columns -> " + ([System.IO.Path]::GetFileName($csvPath)))
      }

      $textPath = Join-Path $textDir ($safeStem + ".md")
      [System.IO.File]::WriteAllLines($textPath, $lines, [System.Text.UTF8Encoding]::new($false))
      $record.status = "ok"
      $record.text_path = $textPath
      $record.tables_dir = $bookTablesDir
      $record.chars = (Get-Content -Path $textPath -Raw -Encoding UTF8).Length
    } finally {
      $workbook.Close($false)
    }
  } finally {
    $app.Quit()
  }
} else {
  throw "Unsupported Office extension: $ext"
}

$manifestPath = Join-Path $OutputDir ("office_extract_" + $safeStem + ".json")
$record | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Output ("MANIFEST`t" + $manifestPath)
