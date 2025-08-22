"""Setup configuration for email-document-ingestion."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

with open("requirements-dev.txt", "r", encoding="utf-8") as fh:
    dev_requirements = [
        line.strip() for line in fh
        if line.strip() and not line.startswith("#") and not line.startswith("-r")
    ]

setup(
    name="email-document-ingestion",
    version="0.1.0",
    author="Development Team",
    author_email="dev@example.com",
    description="A comprehensive system for ingesting, processing, and extracting text from emails and their attachments using multiple OCR engines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/email-document-ingestion",
    packages=find_packages(include=["api*", "workers*", "models*", "services*", "utils*", "config*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "email-ingest-api=main:main",
            "email-ingest-worker=workers.celery_app:worker_main",
            "email-ingest-cli=cli:app",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
