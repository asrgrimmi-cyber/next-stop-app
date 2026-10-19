' Starts Next Stop hidden at login. Copy to shell:startup and set the folder below.
Set sh = CreateObject("WScript.Shell")
dir = "C:\path\to\next-stop-app"
sh.CurrentDirectory = dir
sh.Run "cmd /c """ & dir & "\scripts\run-next-stop.cmd""", 0, False
