function Escape-PdfText {
    param([string]$Text)
    return $Text.Replace('\', '\\').Replace('(', '\(').Replace(')', '\)')
}

function New-SimplePdf {
    param(
        [string]$Path,
        [string[]]$Lines
    )

    $contentLines = @('BT', '/F1 12 Tf', '50 760 Td', '16 TL')
    foreach ($line in $Lines) {
        $contentLines += '(' + (Escape-PdfText $line) + ') Tj'
        $contentLines += 'T*'
    }
    $contentLines += 'ET'

    $stream = ($contentLines -join "`n") + "`n"
    $streamBytes = [System.Text.Encoding]::ASCII.GetByteCount($stream)

    $objects = @(
        "1 0 obj`n<< /Type /Catalog /Pages 2 0 R >>`nendobj`n",
        "2 0 obj`n<< /Type /Pages /Count 1 /Kids [3 0 R] >>`nendobj`n",
        "3 0 obj`n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>`nendobj`n",
        "4 0 obj`n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>`nendobj`n",
        "5 0 obj`n<< /Length $streamBytes >>`nstream`n$stream" + "endstream`nendobj`n"
    )

    $header = "%PDF-1.4`n"
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append($header)

    $offsets = @(0)
    foreach ($object in $objects) {
        $offsets += [System.Text.Encoding]::ASCII.GetByteCount($builder.ToString())
        [void]$builder.Append($object)
    }

    $xrefOffset = [System.Text.Encoding]::ASCII.GetByteCount($builder.ToString())
    [void]$builder.Append("xref`n0 6`n")
    [void]$builder.Append("0000000000 65535 f `n")
    for ($i = 1; $i -le 5; $i++) {
        [void]$builder.Append(($offsets[$i].ToString('0000000000')) + " 00000 n `n")
    }
    [void]$builder.Append("trailer`n<< /Size 6 /Root 1 0 R >>`nstartxref`n$xrefOffset`n%%EOF`n")

    [System.IO.File]::WriteAllText($Path, $builder.ToString(), [System.Text.Encoding]::ASCII)
}

function New-SimpleDocx {
    param(
        [string]$Path,
        [string[]]$Paragraphs
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $tempRoot = Join-Path $env:TEMP ([guid]::NewGuid().ToString())
    $relsDir = Join-Path $tempRoot '_rels'
    $wordDir = Join-Path $tempRoot 'word'
    New-Item -ItemType Directory -Force -Path $relsDir, $wordDir | Out-Null

    $contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'@
    [System.IO.File]::WriteAllText((Join-Path $tempRoot '[Content_Types].xml'), $contentTypes.Trim(), [System.Text.Encoding]::UTF8)

    $rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'@
    [System.IO.File]::WriteAllText((Join-Path $relsDir '.rels'), $rootRels.Trim(), [System.Text.Encoding]::UTF8)

    $paragraphXml = foreach ($paragraph in $Paragraphs) {
        $escaped = [System.Security.SecurityElement]::Escape($paragraph)
        '<w:p><w:r><w:t xml:space="preserve">' + $escaped + '</w:t></w:r></w:p>'
    }
    $documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    $($paragraphXml -join "`n    ")
    <w:sectPr/>
  </w:body>
</w:document>
"@
    [System.IO.File]::WriteAllText((Join-Path $wordDir 'document.xml'), $documentXml.Trim(), [System.Text.Encoding]::UTF8)

    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($tempRoot, $Path)
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sampleDir = Join-Path (Split-Path -Parent $scriptRoot) 'sample_documents'
New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null

New-SimplePdf -Path (Join-Path $sampleDir 'recruiting_playbook.pdf') -Lines @(
    'Recruiting Playbook',
    'Candidates should receive interview feedback within 24 hours of each panel.',
    'Recruiters own scheduling and candidate communication, while hiring managers own final debriefs.',
    'Every onsite interview loop must include at least one bar raiser from another team.',
    'A candidate can move to offer stage only after the debrief is complete and all scorecards are submitted.'
)

New-SimplePdf -Path (Join-Path $sampleDir 'offer_approval_policy.pdf') -Lines @(
    'Offer Approval Policy',
    'Offers up to the midpoint of the salary band require approval from the hiring manager and finance partner.',
    'Offers above the midpoint also require the VP of Talent approval before they are sent to the candidate.',
    'Equity refresh grants are not part of the standard offer package for new hires.',
    'All approved offers should be sent within two business days after the final interview decision.'
)

New-SimpleDocx -Path (Join-Path $sampleDir 'interview_scorecard_guidelines.docx') -Paragraphs @(
    'Interview Scorecard Guidelines',
    'Interviewers must submit scorecards before the debrief meeting begins.',
    'Strong hire or strong no hire recommendations require at least two concrete examples from the interview.',
    'Follow-up interviews are used only when the team lacks signal in one competency area, not to relitigate an already clear decision.',
    'Written feedback should describe evidence, risk, and the recommended next step in plain language.'
)
