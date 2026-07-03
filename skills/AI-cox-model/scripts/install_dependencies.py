#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install required dependencies for Cox survival analysis skill."""

import subprocess
import sys


def check_and_install_packages():
    """Check and install all required packages."""
    required_packages = {
        "pandas": "pandas",
        "numpy": "numpy",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "lifelines": "lifelines",
        "scikit-learn": "scikit-learn",
        "pyyaml": "PyYAML",
        "reportlab": "reportlab",
    }

    print("Checking required dependencies for Cox Survival Analysis...")
    print("=" * 60)

    missing_packages = []

    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name} is installed")
        except ImportError:
            print(f"✗ {package_name} is NOT installed")
            missing_packages.append(package_name)

    if not missing_packages:
        print("=" * 60)
        print("All dependencies are already installed! ✓")
        return True

    print("=" * 60)
    print(f"\nInstalling {len(missing_packages)} missing package(s)...")
    print("-" * 60)

    for package in missing_packages:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])
            print(f"  ✓ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to install {package}: {e}")
            return False

    print("-" * 60)
    print("All dependencies installed successfully! ✓")
    return True


if __name__ == "__main__":
    success = check_and_install_packages()
    sys.exit(0 if success else 1)
