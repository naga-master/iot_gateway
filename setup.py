# Package installation script

from setuptools import setup, find_packages

setup(
    name="iot_gateway",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "iot_gateway=iot_gateway.__main__:main",
        ],
    },
    # Add your dependencies here
    install_requires=[
        "fastapi",
        "hypercorn",
        "pyyaml",
        "aiomqtt",
        "smbus2",
        "aiosqlite",
        "pydantic",
        # "Rpi.GPIO"
    ],
)