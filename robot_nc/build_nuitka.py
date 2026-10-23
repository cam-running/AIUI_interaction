#!/usr/bin/env python3
import os
import subprocess
import sys
import multiprocessing


def main():
    main_file = "main_robot.py"
    output_name = "robot_ai"
    build_dir = "build"

    if not os.path.exists(main_file):
        print("错误: 找不到 main_robot.py")
        return False

    jobs = multiprocessing.cpu_count()

    # 使用参数列表以避免在 Windows PowerShell 下多行续行被误解析
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        f"--jobs={jobs}",
        f"--output-dir={build_dir}",
        f"--output-filename={output_name}",
        "--nofollow-import-to=pytest,unittest,setuptools",
        "--include-module=socket",
        "--include-module=ssl",
        "--include-data-dir=config=config",
        # 显式包含 AIUI 运行所需的本地库
        # Windows x64 AIUI 动态库
        "--include-data-files=config/aiui/x64/*.dll=config/aiui/x64/",
        # Linux aarch64 AIUI 动态库（生产环境）
        "--include-data-files=config/aiui/arm/*.so=config/aiui/arm/",
        main_file,
    ]

    print("执行:", " ".join(cmd))
    # 不使用 shell，避免转义与续行差异导致参数丢失
    return subprocess.run(cmd).returncode == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
