@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ==========================================
echo         使用WinSCP自动上传文件到服务器
echo ==========================================
echo.

:: ========== 配置区域 ==========
:: 工具路径配置
set WINSCP_PATH="D:\Program Files (x86)\WinSCP\WinSCP.exe"
set PLINK_PATH="D:\Program Files\PuTTY\plink.exe"

:: 服务器连接配置
set SERVER_IP=192.168.0.10
set USERNAME=admin
set PASSWORD=12345678
set WINSCP_HOST_KEY=ssh-ed25519 255 jpSGJzJruc/a09yKIik/CNLRhLtKht8Oe0PjXhrLKNQ

:: 路径配置
set LOCAL_BASE_DIR=E:\home\ict\robot_ai\docker
set REMOTE_BASE_DIR=/home/ict/robot_ai/docker
set LOCAL_FILE=%LOCAL_BASE_DIR%\install.sh
set REMOTE_FILE=%REMOTE_BASE_DIR%/install.sh
set LOCAL_DOCKER_DIR=%LOCAL_BASE_DIR%\docker_file
set REMOTE_DOCKER_DIR=%REMOTE_BASE_DIR%/docker_file
:: ================================

:: 检查 WinSCP 是否存在
if not exist %WINSCP_PATH% (
    echo 错误: 未找到 WinSCP。请确认路径是否正确。
    echo 当前设置路径: %WINSCP_PATH%
    goto :END
)

:: 检查 Plink 是否存在
if not exist %PLINK_PATH% (
    echo 错误: 未找到 Plink。请确认路径是否正确。
    echo 当前设置路径: %PLINK_PATH%
    goto :END
)




:: 检查本地文件是否存在
if not exist "%LOCAL_FILE%" (
    echo 错误: 本地文件不存在!
    echo 请确认路径: %LOCAL_FILE%
    goto :END
)

:: 获取或读取主机密钥
call :GET_HOST_KEY

:: 1️⃣ 检查远程文件和目录是否已存在
echo.
echo [INFO] 检查服务器文件状态...

:: 检查install.sh文件
%PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "test -f %REMOTE_FILE%" >nul 2>&1
set NEED_UPLOAD_INSTALL=%ERRORLEVEL%

:: 检查docker_file目录
%PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "test -d %REMOTE_DOCKER_DIR%" >nul 2>&1
set NEED_UPLOAD_DOCKER=%ERRORLEVEL%

if %NEED_UPLOAD_INSTALL% equ 0 (
    echo [INFO] install.sh 已存在于服务器
) else (
    echo [INFO] install.sh 不存在，需要上传
)

if %NEED_UPLOAD_DOCKER% equ 0 (
    echo [INFO] docker_file 目录已存在于服务器
) else (
    echo [INFO] docker_file 目录不存在，需要上传
)
:: 2️⃣ 执行 WinSCP 上传
if %NEED_UPLOAD_INSTALL% neq 0 (
    if %NEED_UPLOAD_DOCKER% neq 0 (
        echo [INFO] 开始上传所有文件到服务器...
    ) else (
        echo [INFO] 开始上传 install.sh 到服务器...
    )
) else (
    if %NEED_UPLOAD_DOCKER% neq 0 (
        echo [INFO] 开始上传 docker_file 目录到服务器...
    ) else (
        echo [INFO] 所有文件已存在，跳过上传
        goto :EXECUTE_SCRIPT
    )
)

:: 创建远程目录结构
echo [INFO] 创建远程目录结构...
%PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "mkdir -p %REMOTE_BASE_DIR%"

:: 如果需要上传docker_file目录，先创建该目录
if %NEED_UPLOAD_DOCKER% neq 0 (
    echo [INFO] 创建远程docker_file目录...
    %PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "mkdir -p %REMOTE_DOCKER_DIR%"
)

echo [INFO] 远程目录创建完成

:: 创建WinSCP脚本文件
echo open sftp://%USERNAME%:%PASSWORD%@%SERVER_IP%/ -hostkey="%WINSCP_HOST_KEY%" > winscp_script.txt
echo cd %REMOTE_BASE_DIR% >> winscp_script.txt

:: 根据需要添加上传命令
if %NEED_UPLOAD_INSTALL% neq 0 (
    echo put "%LOCAL_FILE%" >> winscp_script.txt
)
if %NEED_UPLOAD_DOCKER% neq 0 (
    echo put "%LOCAL_DOCKER_DIR%\*" "%REMOTE_DOCKER_DIR%/" >> winscp_script.txt
)

:: 总是上传Dockerfile和docker-compose.yml，确保是最新版本
echo put "%LOCAL_BASE_DIR%\Dockerfile" >> winscp_script.txt
echo put "%LOCAL_BASE_DIR%\docker-compose.yml" >> winscp_script.txt

echo exit >> winscp_script.txt

:: 执行WinSCP命令
echo [INFO] 正在通过WinSCP上传文件到服务器...
%WINSCP_PATH% /script=winscp_script.txt /log=winscp_log.txt /ini=nul

:: 检查上传结果
if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] 文件上传成功!
) else (
    echo.
    echo [ERROR] 文件上传失败! 错误码: %ERRORLEVEL%
    echo [INFO] 请查看日志文件: winscp_log.txt
    goto :CLEANUP
)

:: 清理临时文件
if exist winscp_script.txt del winscp_script.txt

:EXECUTE_SCRIPT

:: 3️⃣ 远程执行 install.sh
echo.
echo [INFO] 开始远程执行 install.sh...

:: 检查安装模式

echo.
echo [INFO] 选择安装模式：

echo [INFO] 第2步：保留现有Docker安装
echo.

set /p INSTALL_MODE="请选择 (1/2): "
if "%INSTALL_MODE%"=="2" (
    echo [INFO] 使用保留现有Docker模式...
    %PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "chmod +x %REMOTE_FILE% && echo %PASSWORD% | sudo -S %REMOTE_FILE% --keep"
) else (
    echo [INFO] 使用强制重新安装模式...
    %PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% -batch "chmod +x %REMOTE_FILE% && echo %PASSWORD% | sudo -S %REMOTE_FILE%"
)

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] install.sh 执行成功!
) else (
    echo [ERROR] install.sh 执行失败! 错误码: %ERRORLEVEL%
)

goto :CLEANUP

:: 获取主机密钥的子程序
:GET_HOST_KEY
echo [INFO] 配置SSH连接...

:: 首先尝试建立连接，如果失败则接受主机密钥
echo y | %PLINK_PATH% -ssh %USERNAME%@%SERVER_IP% -pw %PASSWORD% "echo connected" >connection_test.log 2>&1

:: 检查连接测试结果
findstr /i "connected" connection_test.log >nul
if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] SSH连接已建立
) else (
    echo [ERROR] 连接建立失败
    type connection_test.log
)

if exist connection_test.log del connection_test.log


echo [INFO] 主机密钥配置完成

goto :EOF

:CLEANUP
:: 清理临时文件
if exist winscp_script.txt del winscp_script.txt
if exist ssh_key_output.txt del ssh_key_output.txt
if exist winscp_log.txt (
    echo.
    echo [INFO] 如需查看详细日志，请检查: winscp_log.txt
)

:END
echo.
echo [INFO] 操作完成。
pause
