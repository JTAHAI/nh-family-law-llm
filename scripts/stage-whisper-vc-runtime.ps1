# Stage the Visual C++ dependencies of the upstream whisper.cpp x64 release
# beside whisper-cli.exe. Use the Visual Studio redistributable directories.
function Install-WhisperVisualCppRuntime([string]$Destination) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
        throw 'Visual Studio C++ Build Tools with the x64 redistributable files are required.'
    }
    $installations = @(& $vswhere -all -products '*' -property installationPath)
    if ($LASTEXITCODE -ne 0) { throw 'Visual Studio build tool discovery failed.' }
    $roots = foreach ($installation in $installations) {
        $redist = Join-Path $installation 'VC\Redist\MSVC'
        Get-ChildItem -LiteralPath $redist -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -as [version] }
    }
    $groups = @(
        @{ name='msvcp140.dll'; folder='CRT' }
        @{ name='vcruntime140.dll'; folder='CRT' }
        @{ name='vcruntime140_1.dll'; folder='CRT' }
        @{ name='vcomp140.dll'; folder='OpenMP' }
    )
    foreach ($root in ($roots | Sort-Object { [version]$_.Name } -Descending)) {
        $folders = Get-ChildItem -LiteralPath (Join-Path $root.FullName 'x64') -Directory -ErrorAction SilentlyContinue
        $sources = @{}
        foreach ($item in $groups) {
            $folder = @($folders | Where-Object Name -like ("Microsoft.VC*." + $item.folder))
            if ($folder.Count -ne 1) { break }
            $source = Join-Path $folder[0].FullName $item.name
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { break }
            $sources[$item.name] = $source
        }
        if ($sources.Count -ne $groups.Count) { continue }
        $receipt = [ordered]@{}
        foreach ($item in $groups) {
            $source = Get-Item -LiteralPath $sources[$item.name] -Force
            $signature = Get-AuthenticodeSignature -LiteralPath $source.FullName
            if (($source.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $signature.Status -ne 'Valid' -or
                $signature.SignerCertificate.Subject -notmatch '(?:^|, )O=Microsoft Corporation(?:,|$)') {
                throw "Untrusted Visual C++ redistributable: $($item.name)"
            }
            $stream = [IO.BinaryReader]::new([IO.File]::OpenRead($source.FullName))
            try {
                $stream.BaseStream.Position = 0x3c
                $stream.BaseStream.Position = $stream.ReadInt32()
                if ($stream.ReadUInt32() -ne 0x4550 -or $stream.ReadUInt16() -ne 0x8664) {
                    throw 'Expected an x64 Visual C++ redistributable binary.'
                }
            } finally { $stream.Dispose() }
            $version = [version]$source.VersionInfo.FileVersion
            if ($version -lt [version]'14.44.35211.0') { throw 'Visual C++ redistributable is too old.' }
            $digest = (Get-FileHash -LiteralPath $source.FullName).Hash.ToLowerInvariant()
            $target = Join-Path $Destination $item.name
            Copy-Item -LiteralPath $source.FullName -Destination $target
            if ((Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -cne $digest) {
                throw "Visual C++ payload copy differs from original: $($item.name)"
            }
            $receipt[$item.name] = @{version=$version.ToString(); sha256=$digest}
        }
        return $receipt
    }
    throw 'No complete x64 Visual C++ redistributable was found in the installed build tools.'
}
