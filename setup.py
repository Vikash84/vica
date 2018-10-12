from setuptools import setup

setup(
    name='vica',
    version='0.1.6',
    packages=['vica'],
    license='License :: OSI Approved :: BSD License',
    description="find highly divergent DNA and RNA viruses in microbiomes",
    long_description=open('README.rst').read(),
    classifiers=['Topic :: Scientific/Engineering :: Bio-Informatics',
                 'Topic :: Scientific/Engineering :: Artificial Intelligence',
                 'Programming Language :: Python :: 3.6',
                 'Programming Language :: Python :: 3.5',
                 'Development Status :: 3 - Alpha'],
    keywords='virus classifier metagenome RNA DNA microbiome tensorflow',
    url='http://github.com/usda-ars-gbru/vica',
    test_suite ='nose.collector',
    #tests_require=['nose'],
    author='Adam R. Rivers, Qingpeng Zhang',
    author_email='adam.rivers@ars.usda.gov',
    install_requires=['tensorflow>=1.4', 'pandas>=0.20.3', 'numpy',
        'biopython>=1.70','scipy', 'khmer>=2.1.1','ete3',
        'pyfaidx>=0.5', 'pyyaml', 'scikit-learn>=0.19.0'],
    python_requires='>3.5',
    tests_require=['nose'],
    include_package_data=True,
    entry_points= {'console_scripts':['vica=vica.vica_cli:main']},
    zip_safe=False)
