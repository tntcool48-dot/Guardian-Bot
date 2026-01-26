#Requires AutoHotkey v2.0
#SingleInstance Force

SetKeyDelay 50, 50

toggle := false
mcWin := "ahk_exe javaw.exe" ; Target standard Java Minecraft

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

    ; Auto-Correct Alt Key (prevents menu sticking)
    ControlSend "{Alt up}",, mcWin
    
    ; --- PATTERN START ---
    
    ; [cite_start]Initial Pause [cite: 1]
    if (!SleepCheck(1234)) 
        return

    ; [cite_start]Move Right (D) [cite: 1]
    ControlSend "{d down}",, mcWin
    Sleep 235
    
    ; [cite_start]Start Mining (J instead of Click) [cite: 2]
    ControlSend "{j down}",, mcWin
    
    ; [cite_start]Long Mining/Walking duration (82s) [cite: 2]
    if (!SleepCheck(82156)) 
        return

    ; [cite_start]Stop moving Right [cite: 2]
    ControlSend "{d up}",, mcWin
    Sleep 109
    
    ; [cite_start]Stop Mining [cite: 2]
    ControlSend "{j up}",, mcWin
    Sleep 328

    ; [cite_start]Move Back (S) [cite: 2]
    ControlSend "{s down}",, mcWin
    if (!SleepCheck(1079)) 
        return
    ControlSend "{s up}",, mcWin
    Sleep 359

    ; [cite_start]Move Left (A) [cite: 3]
    ControlSend "{a down}",, mcWin
    Sleep 203
    
    ; [cite_start]Start Mining (J instead of Click) [cite: 3]
    ControlSend "{j down}",, mcWin
    
    ; [cite_start]Long Mining/Walking duration (78s) [cite: 3]
    if (!SleepCheck(78047)) 
        return

    ; [cite_start]Stop Mining [cite: 3]
    ControlSend "{j up}",, mcWin
    Sleep 156
    
    ; [cite_start]Stop moving Left [cite: 4]
    ControlSend "{a up}",, mcWin
    
    ; [cite_start]Long pause before return trip [cite: 4]
    if (!SleepCheck(6719)) 
        return

    ; [cite_start]Move Back (S) [cite: 4]
    ControlSend "{s down}",, mcWin
    if (!SleepCheck(1500)) 
        return
    ControlSend "{s up}",, mcWin

    ; --- PATTERN END ---

    if (toggle)
        SetTimer(FarmLoop, 10)
}

; --- MOUSE LOCK FUNCTION ---
LockMouseInGame()
{
    global mcWin
    ; Only lock the mouse if Minecraft is the ACTIVE window
    if WinActive(mcWin)
    {
        try {
            WinGetPos &X, &Y, &W, &H, mcWin
            ; Force cursor to the exact center of the Minecraft window
            DllCall("SetCursorPos", "int", X + (W // 2), "int", Y + (H // 2))
        }
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
        ; Reinforce holding 'j' every 2 seconds (prevents glitches)
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
    ; Releases all keys used in your specific loop
    ControlSend "{d up}{w up}{a up}{s up}{j up}{Alt up}",, mcWin
}