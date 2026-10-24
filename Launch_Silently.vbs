' DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS
' Silent Windows Launcher (Zero Console Window)
' Double-clicking this script launches the application and opens the browser silently.

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

' Run app_launcher.py in hidden window mode (0 = hide window, False = don't wait)
WshShell.Run "python """ & scriptDir & "\app_launcher.py""", 0, False
