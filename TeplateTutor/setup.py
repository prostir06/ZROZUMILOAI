from setuptools import find_packages, setup

setup(
    name='tutor-contrib-zrozumilo',
    version='0.1.0',
    description='Tutor plugin: ZrozumiloAI support widget settings for Open edX',
    packages=find_packages(),
    python_requires='>=3.9',
    entry_points={
        'tutor.plugin.v1': [
            'zrozumilo = tutorzrozumilo.plugin',
        ],
    },
)
