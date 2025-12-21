from setuptools import find_packages
from setuptools import setup


version = "2.0.1.dev0"

setup(
    name="plone.app.drafts",
    version=version,
    description="Low-level container for draft content",
    long_description=open("README.rst").read() + "\n" + open("CHANGES.rst").read(),
    # Get more strings from
    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: 5.2",
        "Framework :: Plone :: 6.0",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="plone draft content",
    author="Plone Foundation",
    author_email="plone-developers@lists.sourceforge.net",
    url="http://plone.org",
    license="GPL",
    packages=find_packages("src"),
    namespace_packages=["plone", "plone.app"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.9",
    install_requires=[
        "setuptools",
        "plone.app.uuid",
        "plone.autoform",
        "plone.behavior>=1.1",
        "plone.dexterity",
        "plone.protect",
        "plone.uuid",
        "Products.CMFCore",
        "Products.GenericSetup",
        "z3c.form",
        "zope.annotation",
        "zope.component",
        "zope.interface",
        "zope.schema",
        "Zope",
    ],
    extras_require={
        "test": [
            "plone.app.contenttypes",
            "plone.app.testing",
            "plone.app.dexterity",
            "plone.testing",
        ],
    },
    entry_points="""
      [z3c.autoinclude.plugin]
      target = plone
      """,
)
