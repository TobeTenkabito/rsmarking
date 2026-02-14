from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy
import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(BASE_DIR, "engine")


def get_extensions():
    try:
        ext = [
            Extension(
                "engine.translator",
                [os.path.join(ENGINE_PATH, "translator.pyx")],
                include_dirs=[numpy.get_include()],
                extra_compile_args=["-O3"] if sys.platform != "win32" else ["/O2"],
            ),
            Extension(
                "engine.rendering",
                [os.path.join(ENGINE_PATH, "rendering.pyx")],
                include_dirs=[numpy.get_include()],
                extra_compile_args=["-O3"] if sys.platform != "win32" else ["/O2"],
            )
        ]
        return ext
    except Exception as e:
        print(f"### [BUILD_ERROR] Failed to construct extension module: {e} ###")
        return []


setup(
    name="TileServiceEngine",
    version="1.0.0",
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'initializedcheck': False
        },
        annotate=True
    ),
    zip_safe=False,
)
