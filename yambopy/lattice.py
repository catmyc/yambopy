# Copyright (c) 2015, Henrique Miranda
# All rights reserved.
#
# This file is part of the yambopy project
#
from yambopy import *
from itertools import product

def calculate_distances(kpoints):
    """
    take a list of k-points and calculate the distances between all of them
    """
    kpoints = np.array(kpoints)
    distances = [0]
    distance = 0
    for nk in range(1,len(kpoints)):
        distance += np.linalg.norm(kpoints[nk-1]-kpoints[nk])
        distances.append(distance)   
    return distances
 
def expand_kpts(kpts,syms):
    """ 
    Take a list of qpoints and symmetry operations and return the full brillouin zone
    with the corresponding index in the irreducible brillouin zone
    """
    full_kpts = []
    print "nkpoints:", len(kpts)
    for nk,k in enumerate(kpts):
        for sym in syms:
            full_kpts.append((nk,np.dot(sym,k)))

    return full_kpts

def isbetween(a,b,c,eps=1e-5):
    """ Check if c is between a and b
    """
    return np.isclose(np.linalg.norm(a-c)+np.linalg.norm(b-c)-np.linalg.norm(a-b),0,atol=eps)

def red_car(red,lat):
    """
    Convert reduced coordinates to cartesian
    """
    return np.array(map( lambda coord: coord[0]*lat[0]+coord[1]*lat[1]+coord[2]*lat[2], red))

def car_red(car,lat):
    """
    Convert cartesian coordinates to reduced
    """
    return np.array(map( lambda coord: np.linalg.solve(np.array(lat).T,coord), car))

def rec_lat(lat):
    """
    Calculate the reciprocal lattice vectors
    """
    a1,a2,a3 = np.array(lat)
    v = np.dot(a1,np.cross(a2,a3))
    b1 = np.cross(a2,a3)/v
    b2 = np.cross(a3,a1)/v
    b3 = np.cross(a1,a2)/v
    return np.array([b1,b2,b3])

def get_path(kmesh,path,debug=False):
    """
    get indexes of the kpoints in the the kmesh
    that fall along the path
    """
    kmesh = np.array(kmesh)
    path  = np.array(path)

    #find the points along the high symmetry lines
    bands_indexes = []

    #for all the paths
    for k in range(len(path)-1):

        # store here all the points in the path
        # key:   has the coordinates of the kpoint rounded to 4 decimal places
        # value: index of the kpoint
        #        the kpoint cordinate
        kpoints_in_path = []

        start_kpt = path[k]   #start point of the path
        end_kpt   = path[k+1] #end point of the path

        #iterate over all the kpoints
        for index, kpt in enumerate(kmesh):

            #if the point is collinear we add it
            if isbetween(start_kpt,end_kpt,kpt):
                value = [ index, np.linalg.norm(start_kpt-kpt), kpt ]
                kpoints_in_path.append( value )

        #sort the points acoording to distance to the start of the path
        kpoints_in_path = sorted(kpoints_in_path,key=lambda i: i[1])

        #for all the kpoints in the path
        for index, disp, kpt in kpoints_in_path:
            bands_indexes.append( index )
            if debug: print ("%12.8lf "*3)%tuple(kpt), index

    return np.array(bands_indexes)

def replicate_red_kmesh(kmesh,repx=range(1),repy=range(1),repz=range(1)):
    """
    copy a kmesh in the tree directions
    the kmesh has to be in reduced coordinates
    """
    kmesh = np.array(kmesh)
    kmesh_nkpoints = len(kmesh)

    kmesh_full = []
    kmesh_idx  = []
    for x,y,z in product(repx,repy,repz):
        kmesh_shift = kmesh + np.array([x,y,z])
        kmesh_full.append(kmesh_shift)
        kmesh_idx.append(range(kmesh_nkpoints))

    return np.vstack(kmesh_full), np.hstack(kmesh_idx)


def point_matching(a,b,double_check=True,debug=False,eps=1e-8):
    """
    Matches the points of list a to the points of list b
    using a nearest neighbour finding algorithm

    Arguments:

        double_check: after the nearest neighbours are assigned check further
        if the distance between points is within the precision eps

        eps: precision for the double check (default: 1e-8)

    """
    #karma
    from scipy.spatial import cKDTree
    from time import time
    a = np.array(a)
    b = np.array(b)
    start_time = time()

    #initialize thd kdtree
    kdtree = cKDTree(a, leafsize=10)
    map_b_to_a = []
    for xb in b:
        current_dist,index = kdtree.query(xb, k=1, distance_upper_bound=6)
        map_b_to_a.append(index)
    map_b_to_a = np.array(map_b_to_a)

    if debug: print "took %4.2lfs"%(time()-start_time)

    if double_check:
        for ib,ia in enumerate(map_b_to_a):
            dist = np.linalg.norm(a[ia]-b[ib])
            if dist > eps:
                raise ValueError('point a %d: %s is far away from points b %d: %s  dist: %lf'%(ia,str(a[ia]),ib,str(b[ib]),dist))

    return map_b_to_a


def calculate_distances(kpoints):
    """
    Take a list of k-points and calculate a list with the
    distances between them
    """
    kpoints = np.array(kpoints)
    bands_distances = [0]
    distance = 0
    for nk in range(1,len(kpoints)):
        distance += np.linalg.norm(kpoints[nk-1]-kpoints[nk])
        bands_distances.append(distance)
    return np.array(bands_distances)


