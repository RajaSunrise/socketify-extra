import setuptools



with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="socketify-extra",
    version="0.1.0",
    platforms=["any"],
    author="RajaSunrise",
    author_email="indra020204@gmail.com",
    description="Framework paling cepat untuk python saat ini",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=["socketify-extra"],

    package_data={
        "": [
            "./*.so",
            "./*.dll",
            "./uWebSockets/*",
            "./uWebSockets/*/*",
            "./uWebSockets/*/*/*",
            "./native/*",
            "./native/*/*",
            "./native/*/*/*",
        ]
    },
    python_requires=">=3.10",
    install_requires=["cffi>=1.16.0", "setuptools>=58.1.0"],
    has_ext_modules=lambda: True,
    cmdclass={},
    include_package_data=True,
)
