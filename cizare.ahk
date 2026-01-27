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
            SetTimer(LockMouseInGame, 10)
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
        SetTimer(LockMouseInGame, 0)
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
    SafeControlSend "{Alt up}"
    
    ; --- PATTERN START ---
    
    if (!SleepCheck(1234)) 
        return

    ; Move Right (D)
    SafeControlSend "{d down}"
    Sleep 235
    
    ; Start Mining (J)
    SafeControlSend "{j down}"
    
    ; Long Mining/Walking duration
    if (!SleepCheck(82156)) 
        return

    ; Stop moving Right
    SafeControlSend "{d up}"
    Sleep 109
    
    ; Stop Mining
    SafeControlSend "{j up}"
    Sleep 328

    ; Move Back (S) - CIZARE INPUT
    SafeControlSend "{s down}"
    if (!SleepCheck(1079)) 
        return
    SafeControlSend "{s up}"
    Sleep 359

    ; Move Left (A)
    SafeControlSend "{a down}"
    Sleep 203
    
    ; Start Mining (J)
    SafeControlSend "{j down}"
    
    ; Long Mining/Walking duration
    if (!SleepCheck(78047)) 
        return

    ; Stop Mining
    SafeControlSend "{j up}"
    Sleep 156
    
    ; Stop moving Left
    SafeControlSend "{a up}"
    
    ; Pause before return trip
    if (!SleepCheck(6719)) 
        return

    ; Move Back (S) - CIZARE INPUT
    SafeControlSend "{s down}"
    if (!SleepCheck(1500)) 
        return
    SafeControlSend "{s up}"

    ; --- PATTERN END ---

    if (toggle)
        SetTimer(FarmLoop, 10)
}

LockMouseInGame()
{
    global mcWin
    if WinActive(mcWin)
    {
        try {
            WinGetPos &X, &Y, &W, &H, mcWin
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
        if (A_TickCount - lastReinforce > 2000) {
            SafeControlSend "{j down}"
            lastReinforce := A_TickCount
        }
        Sleep 100
    }
    return true
}

ReleaseAll()
{
    SafeControlSend "{d up}{w up}{a up}{s up}{j up}{Alt up}"
}

; --- SAFE SEND FUNCTION (Fixes Crash) ---
SafeControlSend(keys)
{
    global mcWin
    Loop 2 ; Retry logic
    {
        try 
        {
            ControlSend keys,, mcWin
            return ; Success
        }
        catch 
        {
            Sleep 20 ; Wait 20ms and try again
        }
    }
    ; If it fails twice, it skips the input without crashing
}