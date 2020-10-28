from setuptools import setup


with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='compile-commands',
    version='0.0.1',
    url="https://github.com/qdewaghe/compile-commands",
    author="Quentin Dewaghe",
    author_email="q.dewaghe@gmail.com",
    description='Compilation Database Manipulation Utility',
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Natural Language :: English"
    ],
    python_requires='>=3.4',
    packages=["src"],
    entry_points={
        "console_scripts": [
            "myscript = src.compile_commands.__main__:main",
        ],
    },
    extras_require={
        "dev": [
            "pytest>=3.7"
        ],
    }
)