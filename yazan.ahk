#Requires AutoHotkey v2.0
#SingleInstance Force

SetKeyDelay 50, 50

toggle := false
mcWin := "ahk_exe javaw.exe"

F3::
{
    global toggle
    toggle := !toggle

    if (toggle)
    {
        if WinExist(mcWin)
        {
            try ControlFocus "ahk_exe javaw.exe"
            ToolTip("Farming: ON (Mouse Locked in Game)")
            SetTimer(FarmLoop, 100)
            SetTimer(LockMouseInGame, 10) ; Runs every 10ms to freeze mouse
            SetTimer(() => ToolTip(), -2000)
        }
        else
        {
            MsgBox("Minecraft window not found!")
            toggle := false
        }
    }
    else
    {
        ToolTip("Farming: OFF")
        SetTimer(FarmLoop, 0)
        SetTimer(LockMouseInGame, 0) ; Turn off mouse lock
        ReleaseAll()
        SetTimer(() => ToolTip(), -2000)
    }
}

FarmLoop()
{
    global mcWin, toggle
    SetTimer(FarmLoop, 0) 

    if (!toggle)
        return

    ; Auto-Correct Alt Key
    ControlSend "{Alt up}",, mcWin
    
    ; --- PATTERN START ---
    if (!SleepCheck(1406)) 
        return

    ControlSend "{d down}",, mcWin
    Sleep 31
    ControlSend "{j down}",, mcWin 
    
    if (!SleepCheck(82156)) 
        return

    ControlSend "{d up}",, mcWin
    Sleep 328

    ControlSend "{w down}",, mcWin
    if (!SleepCheck(1390)) 
        return

    ControlSend "{w up}",, mcWin
    Sleep 750

    ControlSend "{a down}",, mcWin
    ControlSend "{j down}",, mcWin ; Re-assert mining
    
    if (!SleepCheck(78485)) 
        return

    ControlSend "{a up}",, mcWin
    Sleep 625

    ControlSend "{w down}",, mcWin
    if (!SleepCheck(1547)) 
        return

    ControlSend "{w up}",, mcWin
    
    if (toggle)
        SetTimer(FarmLoop, 10)
}

; --- NEW: MOUSE LOCK FUNCTION ---
LockMouseInGame()
{
    global mcWin
    ; Only lock the mouse if Minecraft is the ACTIVE window
    if WinActive(mcWin)
    {
        WinGetPos &X, &Y, &W, &H, mcWin
        ; Force cursor to the exact center of the Minecraft window
        DllCall("SetCursorPos", "int", X + (W // 2), "int", Y + (H // 2))
    }
}

SleepCheck(duration)
{
    global toggle, mcWin
    endTime := A_TickCount + duration
    lastReinforce := A_TickCount

    while (A_TickCount < endTime)
    {
        if (!toggle) {
            ReleaseAll()
            return false
        }
        if (A_TickCount - lastReinforce > 2000) {
            ControlSend "{j down}",, mcWin
            lastReinforce := A_TickCount
        }
        Sleep 100
    }
    return true
}

ReleaseAll()
{
    global mcWin
    ControlSend "{d up}{w up}{a up}{j up}{Alt up}",, mcWin
}