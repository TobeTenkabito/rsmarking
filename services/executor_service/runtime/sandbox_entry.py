import os
import sys
import traceback
import rasterio
import numpy as np


def main():
    # 1. 挂载路径由 config.py 约定，容器内固定读取这些路径
    input_dir = "/data/inputs"
    output_dir = "/data/outputs"
    script_path = "/data/scripts/user_code.py"

    # 约定输出文件名由环境变量传入，或者采用默认值
    output_filename = os.environ.get("OUTPUT_FILENAME", "result.tif")
    output_filepath = os.path.join(output_dir, output_filename)

    # 2. 自动检索输入文件（按字典序排列）
    try:
        input_files = [
            os.path.join(input_dir, f) for f in sorted(os.listdir(input_dir))
            if f.endswith(('.tif', '.tiff'))
        ]
    except Exception as e:
        print(f"ERROR: 无法读取输入目录: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # 3. 读取用户脚本
    if not os.path.exists(script_path):
        print(f"ERROR: 找不到用户脚本 {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        user_code = f.read()

    # 4. 构建受限的安全执行上下文
    # 注入全局变量，让用户无需自己构建绝对路径
    exec_globals = {
        "__builtins__": __builtins__,
        "np": np,
        "rasterio": rasterio,
        "DATA_INPUTS": input_files,
        "OUTPUT_PATH": output_filepath,
        "math": __import__("math")
    }

    # 5. 执行用户代码
    try:
        # 使用 exec 执行代码块
        exec(user_code, exec_globals)
        print("SUCCESS: 脚本执行完成")
    except Exception as e:
        # 捕获并格式化异常，打印到 stderr 供外部宿主机捕获
        exc_info = traceback.format_exc()
        print(f"ERROR: 脚本执行失败:\n{exc_info}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()