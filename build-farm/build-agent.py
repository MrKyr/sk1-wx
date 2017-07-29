#!/usr/bin/env python
#
# -*- coding: utf-8 -*-
#
#   Crossplatform build agent for VirtualBox build farm
#
#   Copyright (C) 2017 by Igor E. Novikov
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

#   SYNOPSIS
#   Agent assumes that git, compiler, python, dev-packages have been installed
#   on current build platform.
#
#   Agent gets on start following args:
#       project - unique project name
#       project2 - additional project name (msw/macos builds)
#       git_url - main repository URL
#       git_url2 - additional repository URL (msw/macos builds)
#       ftp_url - upload url (ftp://username:password@host:port)
#       timestamp - optional build marker (like 20170624)

import sys, os, platform


class Error(Exception): pass


DATASET = {
    'project': 'sk1-wx',
    'project2': 'sk1-wx-msw',
    'git_url': 'https://github.com/sk1project/sk1-wx',
    'git_url2': 'https://github.com/sk1project/sk1-wx-msw',
    'ftp_url': 'ftp://builder:password@192.168.0.102',
    'timestamp': '',
    'script': 'setup-sk1.py',
}

WINDOWS = 'Windows'
LINUX = 'Linux'
MACOS = 'Darwin'


def is_msw():
    return platform.system() == WINDOWS


def is_linux():
    return platform.system() == LINUX


def is_macos():
    return platform.system() == MACOS


def is_path(path):
    return os.path.lexists(path)


MINT = 'LinuxMint'
UBUNTU = 'Ubuntu'
DEBIAN = 'debian'
FEDORA = 'fedora'
OPENSUSE = 'SuSE'

MARKERS = {
    MINT: 'mint',
    UBUNTU: 'ubuntu',
    DEBIAN: 'debian',
    FEDORA: 'fc',
    OPENSUSE: 'opensuse',
}


def is_deb():
    return platform.dist()[0] in [MINT, UBUNTU, DEBIAN]


def is_debian():
    return platform.dist()[0] == DEBIAN


def is_ubuntu():
    return platform.dist()[0] == UBUNTU


def is_rpm():
    return platform.dist()[0] in [FEDORA, OPENSUSE]


def get_marker():
    if is_linux():
        if is_deb():
            ver = platform.dist()[1]
            if is_debian(): ver = ver.split('.')[0]
            marker = '_%s_%s_' % (MARKERS[platform.dist()[0]], ver)
            if DATASET['timestamp']:
                marker = '_%s%s' % (DATASET['timestamp'], marker)
            return marker
        elif is_rpm():
            ver = platform.dist()[1].split('.')[0]
            marker = MARKERS[platform.dist()[0]] + ver
            if DATASET['timestamp']:
                marker = '%s.%s' % (DATASET['timestamp'], marker)
            return marker
        return MARKERS[platform.dist()[0]]
    elif is_msw():
        return 'win'
    return 'macos'


def get_package(path):
    files = []
    items = os.listdir(path)
    for item in items:
        if os.path.isfile(item):
            files.append(item)
    if is_deb():    
        if len(files) == 1 and files[0].endswith('.deb'):
            return files[0]        
    elif is_rpm():
        for item in files:
            if item.endswith('.rpm') and not item.endswith('src.rpm'):
                return item
    raise Error('Build failed!')

# ------------ Build script ------------------

# CLI args processing
if len(sys.argv) > 1:
    args = sys.argv[1:]
    for item in args:
        if '=' in item:
            key, value = item.split('=')[:2]
            if value[0] in ('"', "'"): value = value[1:]
            if value[-1] in ('"', "'"): value = value[:-1]
            DATASET[key] = value

BUILD_DIR = os.path.expanduser('~/buildfarm')
PROJECT_DIR = os.path.join(BUILD_DIR, DATASET['project'])
PROJECT2_DIR = os.path.join(BUILD_DIR, DATASET['project2'])
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
if is_msw: DIST_DIR = os.path.join(PROJECT2_DIR, 'dist')
url = DATASET['git_url']
url2 = DATASET['git_url2']
script = DATASET['script']
proj_name = DATASET['project']
proj2_name = DATASET['project2']

try:
    if not is_path(BUILD_DIR): os.mkdir(BUILD_DIR)

    if is_linux(): 
        if not is_path(PROJECT_DIR):
            os.system('cd %s;git clone %s %s' % (BUILD_DIR, url, proj_name))
        else:
            os.system('cd %s;git pull' % PROJECT_DIR)
        if is_path(DIST_DIR):
            os.system('rm -rf %s' % DIST_DIR)

        if is_deb():
            os.system('cd %s;python %s bdist_deb' % (PROJECT_DIR, script))

            old_name = get_package(DIST_DIR)
            prefix, suffix = old_name.split('_')
            new_name = prefix + get_marker() + suffix

        elif is_rpm():
            os.system('cd %s;python %s bdist_rpm' % (PROJECT_DIR, script))

            old_name = get_package(DIST_DIR)
            items=old_name.split('.')
            new_name = '.'.join(items[:-2] + [get_marker(),] + items[-2:])

        old_name = os.path.join(DIST_DIR, old_name)
        package_name = os.path.join(DIST_DIR, new_name)
        os.system('mv %s %s' % (old_name, package_name))
            
    elif is_msw():
        if not is_path(PROJECT_DIR):
            os.system('cd %s;git clone %s %s' % (BUILD_DIR, url, proj_name))
        else:
            os.system('cd %s;git pull' % PROJECT_DIR)
        if not is_path(PROJECT2_DIR):
            os.system('cd %s;git clone %s %s' % (BUILD_DIR, url, proj2_name))
        else:
            os.system('cd %s;git pull' % PROJECT2_DIR)
        if is_path(DIST_DIR):
            os.system('rm -rf %s' % DIST_DIR)

        os.system('cd %s;python %s bdist_msi' % (PROJECT2_DIR, script))
        os.system('cd %s;python %s bdist_portable' % (PROJECT2_DIR, script))
    elif is_macos():
        pass
except:
    sys.exit(1)
