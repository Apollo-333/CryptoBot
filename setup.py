from setuptools import setup, find_packages

setup(
    name="crypto-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "ccxt==4.2.77",
        "pandas==1.5.3", 
        "python-telegram-bot==20.7",
        "python-dotenv==1.0.0",
        "numpy==1.24.3",
        "ta==0.10.2",
        "flask==2.3.3",
        "gunicorn==21.2.0",
        "requests==2.31.0"
    ],
)
