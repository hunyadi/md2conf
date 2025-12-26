# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2025, Levente Hunyadi
# https://github.com/hunyadi/md2conf

# Sets environment variables defined in the file `.env` as KEY=VALUE pairs in the current environment context.
#
# Usage (a.k.a. dot-sourcing):
# ```
# . .\load.ps1
# ```

# path to the `.env` file
$envFile = ".env"

# check if the file exists
if (-Not (Test-Path $envFile)) {
    Write-Error ".env file not found."
    exit 1
}

# process file contents line by line
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()

    # skip empty lines and comments
    if (-not $line -or $line.StartsWith("#")) {
        return
    }

    # match lines in the format `KEY=VALUE`
    if ($line -match '^\s*([^=]+?)\s*=\s*(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()

        # set the environment variable in the current process
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}
