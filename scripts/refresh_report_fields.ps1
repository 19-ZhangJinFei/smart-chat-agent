param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$PdfOutput
)
$ErrorActionPreference = 'Stop'
if ([IO.Path]::GetFullPath($Source) -eq [IO.Path]::GetFullPath($Output)) {
    throw '必须在独立副本更新域，不能覆盖原模板稿'
}
Copy-Item -LiteralPath $Source -Destination $Output -Force
$taskWord = $null
$taskDocument = $null
$taskOwnsWord = $false
$taskExistingWordIds = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskNewWordIds = @(Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $taskExistingWordIds -notcontains $_.Id })
    if ($taskNewWordIds.Count -ne 1 -or $taskWord.Documents.Count -ne 0) {
        throw '没有取得独立空白Word进程，停止操作以保护正在编辑的文档'
    }
    $taskOwnsWord = $true
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskDocument = $taskWord.Documents.Open($Output, $false, $false, $false)
    $taskDocument.Fields.Update() | Out-Null
    foreach ($taskToc in $taskDocument.TablesOfContents) {
        $taskToc.Update()
        $taskToc.Range.Font.Size = 11
        $taskToc.Range.Font.Name = 'Times New Roman'
        $taskToc.Range.Font.NameFarEast = '宋体'
        $taskToc.Range.Font.Color = 0
        $taskToc.Range.ParagraphFormat.LineSpacingRule = 0
        $taskToc.Range.ParagraphFormat.SpaceBefore = 0
        $taskToc.Range.ParagraphFormat.SpaceAfter = 0
    }
    $taskDocument.Repaginate()
    foreach ($taskToc in $taskDocument.TablesOfContents) { $taskToc.UpdatePageNumbers() }
    $taskDocument.Save()
    if ($PdfOutput) { $taskDocument.ExportAsFixedFormat([IO.Path]::GetFullPath($PdfOutput), 17) }
    Write-Output ('Word域更新完成；页数=' + $taskDocument.ComputeStatistics(2))
} finally {
    if ($taskDocument) {
        $taskDocument.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($taskDocument)
    }
    if ($taskWord) {
        if ($taskOwnsWord) { $taskWord.Quit() }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($taskWord)
    }
}
