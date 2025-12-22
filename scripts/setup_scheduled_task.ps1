#Requires -Version 5.1
<#
.SYNOPSIS
    Sets up Windows Task Scheduler for the Natura Parga Article Generator.

.DESCRIPTION
    This script creates a Windows Scheduled Task to run the article generator
    every 2 days automatically. It handles Python detection, logging setup,
    and task configuration.

.PARAMETER Action
    The action to perform: Install, Remove, or Status (default: Install)

.PARAMETER Hour
    The hour to run the task (0-23, default: 9 for 9 AM)

.PARAMETER Minute
    The minute to run the task (0-59, default: 0)

.PARAMETER Force
    Skip confirmation prompts

.EXAMPLE
    .\setup_scheduled_task.ps1
    Installs the scheduled task with default settings (9:00 AM every 2 days)

.EXAMPLE
    .\setup_scheduled_task.ps1 -Action Remove
    Removes the scheduled task

.EXAMPLE
    .\setup_scheduled_task.ps1 -Hour 10 -Minute 30
    Installs the scheduled task to run at 10:30 AM every 2 days

.NOTES
    Author: Natura Parga Article Generator
    Requires: Windows PowerShell 5.1 or later
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("Install", "Remove", "Status", "Help")]
    [string]$Action = "Install",
    
    [Parameter()]
    [ValidateRange(0, 23)]
    [int]$Hour = 9,
    
    [Parameter()]
    [ValidateRange(0, 59)]
    [int]$Minute = 0,
    
    [Parameter()]
    [switch]$Force
)

# ============================================================
# Configuration
# ============================================================

$TaskName = "NaturaPargaArticleGenerator"
$TaskDescription = "Automatically generates and publishes SEO articles for Natura Parga every 2 days"

# ============================================================
# Helper Functions
# ============================================================

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )
    
    switch ($Type) {
        "Success" { Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
        "Warning" { Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
        "Error"   { Write-Host "[ERROR] $Message" -ForegroundColor Red }
        default   { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
    }
}

function Get-ProjectDirectory {
    # Get the directory where this script is located
    $ScriptDir = Split-Path -Parent $MyInvocation.ScriptName
    
    # Project root is one directory up from scripts/
    $ProjectDir = Split-Path -Parent $ScriptDir
    
    # Verify run_article.py exists
    if (-not (Test-Path (Join-Path $ProjectDir "run_article.py"))) {
        Write-ColorOutput "Cannot find run_article.py in $ProjectDir" -Type Error
        Write-ColorOutput "Make sure this script is in the scripts\ directory of the project" -Type Error
        exit 1
    }
    
    return $ProjectDir
}

function Get-PythonPath {
    param([string]$ProjectDir)
    
    # Check for virtual environment in order of preference
    $VenvPaths = @(
        (Join-Path $ProjectDir "venv\Scripts\python.exe"),
        (Join-Path $ProjectDir ".venv\Scripts\python.exe")
    )
    
    foreach ($VenvPath in $VenvPaths) {
        if (Test-Path $VenvPath) {
            Write-ColorOutput "Found virtual environment: $VenvPath"
            return $VenvPath
        }
    }
    
    # Fall back to system Python
    $SystemPython = Get-Command python -ErrorAction SilentlyContinue
    if ($SystemPython) {
        Write-ColorOutput "Using system Python: $($SystemPython.Source)" -Type Warning
        Write-ColorOutput "Consider using a virtual environment for isolation" -Type Warning
        return $SystemPython.Source
    }
    
    $SystemPython3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($SystemPython3) {
        Write-ColorOutput "Using system Python3: $($SystemPython3.Source)" -Type Warning
        return $SystemPython3.Source
    }
    
    Write-ColorOutput "Could not find Python installation" -Type Error
    Write-ColorOutput "Please install Python 3.11+ or create a virtual environment" -Type Error
    exit 1
}

function Test-Administrator {
    $CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-TaskExists {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    return $null -ne $Task
}

# ============================================================
# Task Management
# ============================================================

function Install-ArticleGeneratorTask {
    $ProjectDir = Get-ProjectDirectory
    $PythonPath = Get-PythonPath -ProjectDir $ProjectDir
    
    Write-ColorOutput "Project directory: $ProjectDir"
    
    # Verify Python version
    $PythonVersion = & $PythonPath --version 2>&1
    Write-ColorOutput "Python version: $PythonVersion"
    
    # Create logs directory if it doesn't exist
    $LogsDir = Join-Path $ProjectDir "logs"
    if (-not (Test-Path $LogsDir)) {
        New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
        Write-ColorOutput "Created logs directory: $LogsDir"
    }
    
    $LogFile = Join-Path $LogsDir "scheduled_runs.log"
    
    # Check if task already exists
    if (Test-TaskExists) {
        Write-ColorOutput "Scheduled task '$TaskName' already exists!" -Type Warning
        
        if (-not $Force) {
            $Response = Read-Host "Do you want to replace it? (y/N)"
            if ($Response -notmatch "^[Yy]$") {
                Write-ColorOutput "Keeping existing task"
                return
            }
        }
        
        # Remove existing task
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-ColorOutput "Removed existing task"
    }
    
    # Create the batch wrapper script
    $WrapperScript = Join-Path $ProjectDir "scripts\run_article_wrapper.bat"
    $WrapperContent = @"
@echo off
REM Wrapper script for Windows Task Scheduler
REM Generated by setup_scheduled_task.ps1

echo ========================================
echo Natura Parga Article Generator
echo Started: %date% %time%
echo ========================================

cd /d "$ProjectDir"
"$PythonPath" run_article.py

echo ========================================
echo Finished: %date% %time%
echo Exit Code: %ERRORLEVEL%
echo ========================================
"@
    
    Set-Content -Path $WrapperScript -Value $WrapperContent -Encoding ASCII
    Write-ColorOutput "Created wrapper script: $WrapperScript"
    
    # Build the command with output redirection
    # Using cmd.exe to handle output redirection properly
    $Action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$WrapperScript`" >> `"$LogFile`" 2>&1" `
        -WorkingDirectory $ProjectDir
    
    # Trigger: Every 2 days at specified time
    $Trigger = New-ScheduledTaskTrigger `
        -Daily `
        -DaysInterval 2 `
        -At ("{0:D2}:{1:D2}" -f $Hour, $Minute)
    
    # Settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    
    # Principal (run as current user)
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited
    
    Write-Host ""
    Write-Host "Task Configuration:"
    Write-Host "  Name: $TaskName"
    Write-Host "  Schedule: Every 2 days at $($Hour):$($Minute.ToString('D2'))"
    Write-Host "  Working Directory: $ProjectDir"
    Write-Host "  Log File: $LogFile"
    Write-Host ""
    
    if (-not $Force) {
        $Response = Read-Host "Install this scheduled task? (y/N)"
        if ($Response -notmatch "^[Yy]$") {
            Write-ColorOutput "Installation cancelled"
            return
        }
    }
    
    # Register the task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Description $TaskDescription `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -Principal $Principal `
            -Force | Out-Null
        
        Write-ColorOutput "Scheduled task installed successfully!" -Type Success
        Write-Host ""
        Write-Host "To verify the installation:"
        Write-Host "  - Open Task Scheduler (taskschd.msc)"
        Write-Host "  - Look for '$TaskName' in the task list"
        Write-Host ""
        Write-Host "To test the task manually:"
        Write-Host "  cd $ProjectDir"
        Write-Host "  python run_article.py --dry-run"
        Write-Host ""
        Write-Host "To view logs:"
        Write-Host "  Get-Content $LogFile -Tail 50"
        Write-Host ""
        Write-Host "To run the task immediately (for testing):"
        Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
        
    } catch {
        Write-ColorOutput "Failed to create scheduled task: $_" -Type Error
        
        if (-not (Test-Administrator)) {
            Write-ColorOutput "Try running PowerShell as Administrator" -Type Warning
        }
        
        exit 1
    }
}

function Remove-ArticleGeneratorTask {
    if (-not (Test-TaskExists)) {
        Write-ColorOutput "No scheduled task '$TaskName' found"
        return
    }
    
    # Show current task
    $Task = Get-ScheduledTask -TaskName $TaskName
    Write-Host ""
    Write-Host "Task to remove:"
    Write-Host "  Name: $($Task.TaskName)"
    Write-Host "  State: $($Task.State)"
    Write-Host ""
    
    if (-not $Force) {
        $Response = Read-Host "Remove this scheduled task? (y/N)"
        if ($Response -notmatch "^[Yy]$") {
            Write-ColorOutput "Removal cancelled"
            return
        }
    }
    
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-ColorOutput "Scheduled task removed successfully!" -Type Success
        
        # Also remove wrapper script if it exists
        $ProjectDir = Get-ProjectDirectory
        $WrapperScript = Join-Path $ProjectDir "scripts\run_article_wrapper.bat"
        if (Test-Path $WrapperScript) {
            Remove-Item $WrapperScript -Force
            Write-ColorOutput "Removed wrapper script"
        }
        
    } catch {
        Write-ColorOutput "Failed to remove scheduled task: $_" -Type Error
        exit 1
    }
}

function Show-TaskStatus {
    Write-Host ""
    Write-Host "Natura Parga Article Generator - Scheduled Task Status"
    Write-Host "======================================================="
    Write-Host ""
    
    if (Test-TaskExists) {
        $Task = Get-ScheduledTask -TaskName $TaskName
        $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        
        Write-ColorOutput "Scheduled task is INSTALLED" -Type Success
        Write-Host ""
        Write-Host "Task Details:"
        Write-Host "  Name: $($Task.TaskName)"
        Write-Host "  State: $($Task.State)"
        Write-Host "  Description: $($Task.Description)"
        Write-Host ""
        
        if ($TaskInfo.LastRunTime -and $TaskInfo.LastRunTime -ne [DateTime]::MinValue) {
            Write-Host "  Last Run: $($TaskInfo.LastRunTime)"
            Write-Host "  Last Result: $($TaskInfo.LastTaskResult)"
        } else {
            Write-Host "  Last Run: (not yet run)"
        }
        
        if ($TaskInfo.NextRunTime -and $TaskInfo.NextRunTime -ne [DateTime]::MinValue) {
            Write-Host "  Next Run: $($TaskInfo.NextRunTime)"
        }
        
        Write-Host ""
        
        # Check log file
        $ProjectDir = Get-ProjectDirectory
        $LogFile = Join-Path $ProjectDir "logs\scheduled_runs.log"
        
        if (Test-Path $LogFile) {
            $LogInfo = Get-Item $LogFile
            Write-Host "Log File: $LogFile"
            Write-Host "  Size: $([math]::Round($LogInfo.Length / 1KB, 2)) KB"
            Write-Host "  Last Modified: $($LogInfo.LastWriteTime)"
            Write-Host ""
            Write-Host "Last 5 lines of log:"
            Write-Host "---"
            Get-Content $LogFile -Tail 5 | ForEach-Object { Write-Host $_ }
            Write-Host "---"
        } else {
            Write-Host "Log File: $LogFile (not yet created - will be created on first run)"
        }
        
    } else {
        Write-ColorOutput "Scheduled task is NOT installed" -Type Warning
        Write-Host ""
        Write-Host "To install, run:"
        Write-Host "  .\scripts\setup_scheduled_task.ps1"
    }
    
    Write-Host ""
}

function Show-Help {
    Write-Host @"
Natura Parga Article Generator - Windows Task Scheduler Setup

Usage: .\setup_scheduled_task.ps1 [-Action <Action>] [-Hour <0-23>] [-Minute <0-59>] [-Force]

Actions:
  Install   Install the scheduled task (default)
  Remove    Remove the scheduled task
  Status    Check if the task is installed and show details
  Help      Show this help message

Parameters:
  -Hour     Hour to run (0-23, default: 9)
  -Minute   Minute to run (0-59, default: 0)
  -Force    Skip confirmation prompts

Examples:
  # Install with default schedule (9:00 AM every 2 days)
  .\setup_scheduled_task.ps1

  # Install with custom time (10:30 AM every 2 days)
  .\setup_scheduled_task.ps1 -Hour 10 -Minute 30

  # Remove the scheduled task
  .\setup_scheduled_task.ps1 -Action Remove

  # Check status
  .\setup_scheduled_task.ps1 -Action Status

  # Install without prompts
  .\setup_scheduled_task.ps1 -Force

Notes:
  - The task runs every 2 days at the specified time
  - Output is logged to logs\scheduled_runs.log
  - The task runs under your user account
  - No administrator privileges required for basic installation
"@
}

# ============================================================
# Main
# ============================================================

switch ($Action) {
    "Install" { Install-ArticleGeneratorTask }
    "Remove"  { Remove-ArticleGeneratorTask }
    "Status"  { Show-TaskStatus }
    "Help"    { Show-Help }
}
