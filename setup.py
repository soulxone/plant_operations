from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="plant_operations",
    version="0.1.0",
    description="Corrugated plant receiving, shipping, GPS tracking, and load tag system tied into ERPNext",
    author="Welchwyse",
    author_email="admin@welchwyse.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
