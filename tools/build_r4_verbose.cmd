@echo off
set NoDefaultCurrentDirectoryInExePath=
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d E:\github\OGSR-Engine || exit /b 1
msbuild ogsr_engine\Layers\xrRenderPC_R4\xrRender_R4.vcxproj -p:Configuration=Release -p:Platform=x64 -p:SolutionDir=E:\github\OGSR-Engine\ -m -nologo -v:normal -fl "-flp:logfile=E:\github\OGSR-Engine\build_r4.log;verbosity=normal"
exit /b %ERRORLEVEL%
