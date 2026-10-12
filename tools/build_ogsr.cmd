@echo off
rem Builds OGSR Engine (E:\github\OGSR-Engine) Release x64 inside the VS 2022 developer environment.
rem LuaJIT (msvcbuild.bat) and DirectXTex (CompileShaders.cmd -> fxc) need cl/fxc on PATH, which plain msbuild lacks.
rem   tools\build_ogsr.cmd [extra msbuild args]   -> E:\github\OGSR-Engine\bin_x64\xrEngine.exe, log in build_release.log
rem The agent's shell sets NoDefaultCurrentDirectoryInExePath=1; LuaJIT's "call msvcbuild.bat" and DirectXTex's
rem "CompileShaders" rely on finding scripts in the working directory, so clear it for this build process only.
set NoDefaultCurrentDirectoryInExePath=
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d E:\github\OGSR-Engine || exit /b 1
msbuild Engine.sln -p:Configuration=Release -p:Platform=x64 -m -nologo -v:minimal -fl "-flp:logfile=E:\github\OGSR-Engine\build_release.log;verbosity=minimal" %*
exit /b %ERRORLEVEL%
