Skylab
######
:date: 2012-12-21 05:54
:tags: rackspace, build, deployment, api, cloud, server, python
:category: linux 

Building a Cloud in the Sky
===========================

This application was created to allow you to construct a Rackspace Private Cloud all running on the Public cloud.  The build will allow you test the Rackspace Private cloud software in a full featured environment.  This will give you access to the full suit of software including a Highly Available environment.

Prerequisites :
  * Python => 2.6 < 3.0
  * Python-Novaclient >= 2.15.0.0
  * Python-Neutronclient >= 2.3.1
  * Fabric >= 1.8.0
  * requests >= 2.1.0

--------

General Overview
^^^^^^^^^^^^^^^^

To use this application you will need the following:
  * A Rackspace Cloud Account
  * An Image you want to build with. Presently the only working image is Ubuntu 12.04, This is the default image.
  * A Region to build in
  

How to make it all go::

  skylab -U <USERNAME> -A <API-KEY> -R <REGION> build-lab


This application has several command line switches, run ``--help`` for more information on what all of the options are.


What will this application do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The application uses several api calls to build you a know good working environment. The application will create a minimum of three cloud server and one cloud network. Then the application will use fabric to bootstrap and setup all of the needed resources for the application that is being built.  Presently the application is hardcoded for the Rackspace Private cloud software release, the coded version is the tagged stable release at v4.2.1.


NOTICE
------

* This super **ALPHA** build and while working as expected and providing a functional build environment you can except wonkyness. 
* While I have provided a basic setup file for you to install the application it has not been thoroughly tested. The only tested entry into the application is when using the executable found in ``bin//skylab.local.py``
* This application was built by me for me and I am sharing it with you. This application is not a Rackspace sanctioned piece of software and has **Absolutely No** support via Rackspace or the Rackspace community.  If you have issues with this application and are kind enough to want to report them please create a github issue. 


--------


License :
  This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. See "README/LICENSE.txt" for full disclosure of the license associated with this product. Or goto http://www.gnu.org/licenses/

