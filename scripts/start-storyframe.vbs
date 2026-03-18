Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = fso.GetParentFolderName(currentDir)
shell.Run "cmd /c """ & currentDir & "\start-storyframe.cmd""", 0, False
