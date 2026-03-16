import os
import sys
import traceback
import rasterio
import numpy as np
from scipy import ndimage
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

# 白名单式内置函数，限制危险操作
SAFE_BUILTINS = {
    'print': print,
    'len': len,
    'range': range,
    'enumerate': enumerate,
    'zip': zip,
    'map': map,
    'filter': filter,
    'sorted': sorted,
    'reversed': reversed,
    'list': list,
    'dict': dict,
    'tuple': tuple,
    'set': set,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'bytes': bytes,
    'min': min,
    'max': max,
    'sum': sum,
    'abs': abs,
    'round': round,
    'pow': pow,
    'divmod': divmod,
    'isinstance': isinstance,
    'issubclass': issubclass,
    'type': type,
    'hasattr': hasattr,
    'getattr': getattr,
    'setattr': setattr,
    'callable': callable,
    'iter': iter,
    'next': next,
    'any': any,
    'all': all,
    'repr': repr,
    'format': format,
    'vars': vars,
    'dir': dir,
    'id': id,
    'hash': hash,
    # 异常类
    'Exception': Exception,
    'ValueError': ValueError,
    'TypeError': TypeError,
    'RuntimeError': RuntimeError,
    'KeyError': KeyError,
    'IndexError': IndexError,
    'AttributeError': AttributeError,
    'ImportError': ImportError,
    'OSError': OSError,
    'IOError': IOError,
    'StopIteration': StopIteration,
    'NotImplementedError': NotImplementedError,
    'ArithmeticError': ArithmeticError,
    'ZeroDivisionError': ZeroDivisionError,
    'OverflowError': OverflowError,
    'MemoryError': MemoryError,
    'Warning': Warning,
    'UserWarning': UserWarning,
    # 其他常用
    'True': True,
    'False': False,
    'None': None,
    'object': object,
    'property': property,
    'staticmethod': staticmethod,
    'classmethod': classmethod,
}


def save_raster_helper(data, path, profile):
    """辅助函数：保存栅格数据，支持 2D 和 3D 数组"""
    with rasterio.open(path, 'w', **profile) as dst:
        if len(data.shape) == 2:
            dst.write(data, 1)
        else:
            for i in range(data.shape[0]):
                dst.write(data[i], i + 1)


def main():
    # 1. 设置路径
    input_dir = "/data/inputs"
    output_dir = "/data/outputs"
    script_path = "/data/scripts/user_code.py"

    # 获取输出文件名
    output_filename = os.environ.get("OUTPUT_FILENAME", "result.tif")

    # 2. 自动检索输入文件
    try:
        input_files = []
        if os.path.exists(input_dir):
            for f in sorted(os.listdir(input_dir)):
                if f.lower().endswith(('.tif', '.tiff', '.img', '.hdf')):
                    input_files.append(os.path.join(input_dir, f))

        print(f"找到 {len(input_files)} 个输入文件")
        for f in input_files:
            print(f"  - {os.path.basename(f)}")

    except Exception as e:
        print(f"ERROR: 无法读取输入目录: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # 3. 读取用户脚本
    if not os.path.exists(script_path):
        print(f"ERROR: 找不到用户脚本 {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        user_code = f.read()

    # 4. 构建输入文件路径映射
    #    支持三种访问方式：
    #      inputs["filename.tif"]  —— 按文件名
    #      inputs["input0"]        —— 按 input+序号 字符串
    #      inputs[0]               —— 按整数序号
    input_mapping = {}
    for idx, filepath in enumerate(input_files):
        basename = os.path.basename(filepath)
        input_mapping[basename] = filepath
        input_mapping[f"input{idx}"] = filepath
        input_mapping[idx] = filepath

    # 5. 构建执行上下文
    exec_globals = {
        "__builtins__": SAFE_BUILTINS,

        # 科学计算库
        "np": np,
        "numpy": np,
        "rasterio": rasterio,
        "ndimage": ndimage,

        # 路径常量
        "INPUT_DIR": input_dir,
        "OUTPUT_DIR": output_dir,
        "INPUT_FILES": input_files,
        "OUTPUT_FILE": os.path.join(output_dir, output_filename),

        # 便捷访问
        "inputs": input_mapping,

        # 标准库（仅暴露必要模块）
        "os": os,
        "sys": sys,
        "math": __import__("math"),
        "warnings": warnings,

        # 辅助函数
        "print": print,
        "read_raster": rasterio.open,
        "save_raster": save_raster_helper,
    }

    # 6. 展开快捷变量：input_0, input_1, ...
    #    用户脚本中可直接使用 input_0 访问第一个文件路径
    for idx, filepath in enumerate(input_files):
        exec_globals[f"input_{idx}"] = filepath

    # 如果只有一个输入文件，额外提供 input_file 快捷方式
    if len(input_files) == 1:
        exec_globals["input_file"] = input_files[0]

    # 7. 执行用户代码
    print("=" * 50)
    print("开始执行用户脚本...")
    print("=" * 50)

    try:
        exec(user_code, exec_globals)
        print("=" * 50)
        print("SUCCESS: 脚本执行完成")

        # 检查预期输出文件是否生成
        expected_output = os.path.join(output_dir, output_filename)
        if os.path.exists(expected_output):
            print(f"输出文件已生成: {output_filename}")
        else:
            # 兜底：扫描输出目录中所有 tif 文件
            generated_files = [
                f for f in os.listdir(output_dir)
                if f.lower().endswith('.tif')
            ]
            if generated_files:
                print(f"生成的文件: {', '.join(generated_files)}")
            else:
                print("WARNING: 未检测到输出文件，请确认脚本已将结果写入 OUTPUT_DIR")

    except Exception as e:
        exc_info = traceback.format_exc()
        print("=" * 50)
        print("ERROR: 脚本执行失败", file=sys.stderr)
        print(exc_info, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
