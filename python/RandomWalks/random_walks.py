#!/usr/bin/env python

"""This module provides functionality implementing an absorbing Markov
chain. It can be used to calculate the expected length of a random
walk between any two points in a space, given the transition matrix on
the space. Also the lowest-cost path (treating low transition
probabilities as high edge traversal costs) and the shortest path (in
number of steps, disregarding probabilities)."""

import numpy as np
import random
import sys
import os
import itertools

# this import is from
# http://www.pysal.org/library/spatial_dynamics/ergodic.html: it
# implements the mean-first-passage-time algorithm, also known as the
# first-mean-passage-time, as described in Kemeny, John, G. and
# J. Laurie Snell (1976) Finite Markov Chains. Springer-Verlag,
# Berlin.
import ergodic

def normalise_by_row(d):
    """Normalise an array row-by-row, ie make each row sum to 1. This
    is useful when creating transition matrices on sub-graphs, or
    randomly-generating transition matrices, or for matrices created
    using a hill-climbing adjustment to transition probabilies: in
    such cases, the transition probabilities are adjusted to take
    account of fitness, so "bad" transitions (to worse fitness) are
    made less likely to be accepted, meaning that each row no longer
    sums to 1. By renormalising we get the true probability after (if
    necessary) multiple rounds of rejection and finally one
    acceptance."""
    for i in range(len(d)):
        sumval = np.sum(d[i])
        d[i] *= 1.0 / sumval
    check_row_sums(d)
    return d

def make_random_matrix(n):
    """Make a random transition matrix on n points."""
    tm = np.random.random((n, n))
    return normalise_by_row(tm)

def make_absorbing(tm, dest):
    """Given a transition matrix, disallow transitions away from the
    given destination -- ie make it an absorbing matrix."""
    for j in range(len(tm)):
        tm[dest, j] = 0.0
    tm[dest, dest] = 1.0
    return tm

def read_transition_matrix(filename):
    """Read a transition matrix from a file and return. The matrix
    will have been written in the right format by some Java code."""
    d = np.genfromtxt(filename)
    return d

def check_row_sums(d):
    # check that each row sums to 1, since each row is the
    # out-probabilities from a single individual. Allow a small margin
    # of error.
    epsilon = 0.000001
    for i, v in enumerate(d):
        if not (1.0 - epsilon < sum(v) < 1.0 + epsilon):
            print("Row doesn't sum to 1: " + str(i) + " " + str(sum(v)))
            assert False
    

def set_self_transition_zero(x):
    """Set cost/length of self-transition to zero."""
    # Was using this method:
    #
    # x *= (np.ones_like(x) - np.eye(len(x)))
    #
    # ... but it fails if infinities are involved. The following
    # method works ok.
    for i in range(len(x)):
        x[i][i] = 0.0
        

def get_mfpt(x):
    """Calculate mean-first-passage time of a given transition
    matrix. Set self-transitions to zero. Note that the pysal code
    (ergodic.py) calls it "first-mean-passage-time"."""
    # NB! The ergodic code expects a matrix, not a numpy array. Breaks
    # otherwise.
    x = np.matrix(x)
    x = np.array(ergodic.fmpt(x))
    set_self_transition_zero(x)
    return x
    
def test_matrix_size(n):
    """Test how big the tm can be before get_mfpt becomes
    slow. n = 4000 is fine, n = 10000 starts paging out (at least 30
    minutes)."""
    d = make_random_matrix(n)
    mfpt = get_mfpt(d)
    print("min", np.min(mfpt))
    print("max", np.max(mfpt))

def invert_probabilities(adj):
    """Convert a probability into an edge traversal cost. It's ok to
    ignore runtime floating point problems here, because they're only
    due to zero-probabilities, which result in infinite edge-traversal
    costs, which is what we want. Restore the "raise" behaviour
    afterward."""
    np.seterr(all='warn')
    retval = -np.log(adj)
    np.seterr(all='raise')
    return retval

def deinvert_probabilities(adj):
    """Convert an edge traversal cost into a probability."""
    return np.exp(-adj)

def test_floyd_warshall_random_data(n):
    """Test."""
    adj = make_random_matrix(n)
    return floyd_warshall_probabilities(adj)

def floyd_warshall_probabilities(adj):
    """For this to be useful, need to invert the transition matrix
    probabilities p somehow, so that low probabilities cause high edge
    traversal costs. See invert_ and deinvert_probabilities."""
    x = invert_probabilities(adj)
    x = floyd_warshall(x)
    set_self_transition_zero(x)
    return x
    
def floyd_warshall(adj):
    """Finds the shortest path between all pairs of nodes. For this to
    be useful, the edge weights have to have the right semantics: a
    small transition probability implies a large edge weight
    (cost). So if your edge weights are probabilities, use
    floyd_warshall_probabilities() instead: it performs the
    conversion.

    Concerning matrix size: n = 1000 works fine, n = 4000 starts
    paging out (at least 10 minutes) on my machine."""
    # from
    # http://www.depthfirstsearch.net/blog/2009/12/03/computing-all-shortest-paths-in-python/
    n = len(adj)
    for k in range(n):
        adj = np.minimum(adj, np.add.outer(adj[:,k],adj[k,:]))
    return adj


def floyd_warshall_nsteps(adj):
    """Disregard the transition probabilities, other than to see
    whether an edge traversal is allowed or not. Calculate the number
    of steps required to get from each point to each other."""
    x = discretize_probabilities(adj)
    x = floyd_warshall(x)
    set_self_transition_zero(x)
    return x
    
def discretize_probabilities(d):
    """Set the edge cost to 1 if there is a nonzero probability, and
    to infinity if there is a zero probability."""
    retval = np.ones_like(d, dtype=float)
    inf = np.infty
    for i in range(len(d)):
        for j in range(len(d)):
            if not d[i, j] > 0.0:
                retval[i, j] = inf
    return retval

def get_dtp(t):
    """Get D_TP, the distance based on transition probability. D_TP(x,
    y) is the log of TP(x, y), for x != y."""
    x = invert_probabilities(t)
    set_self_transition_zero(x)
    return x

def write_symmetric_remoteness(codename):
    """Read in the TP matrix and the MFPT one, and write out the
    symmetric versions. Maybe do STEPS and SP also?"""
    tp = np.genfromtxt(codename + "/TP.dat")
    mfpt = np.genfromtxt(codename + "/MFPT.dat")
    stp = 0.5 * (tp + tp.T)
    ct = 0.5 * (mfpt + mfpt.T)
    np.savetxt(codename + "/STP.dat", stp)
    np.savetxt(codename + "/CT.dat", ct)

def read_and_get_Von_Luxburg_approximations(codename):
    # assumes TP and MFPT have been calculated and written out already
    t = read_transition_matrix(codename + "/TP.dat")
    mfpt = np.genfromtxt(codename + "/MFPT.dat")
    ones = np.ones_like(t)
    n = t.shape[0]
    
    # d_v is the in-degree, which is the column sum. this
    # multiplication does the right thing
    d_v = np.sum(t, axis=0) * ones
    # transpose and repeat to get d_u
    d_u = d_v.T
    # vol(G) is sum of degrees, which we interpret in the direct case
    # as sum of out-degrees (which is anyway equal to sum of
    # in-degrees); because weights are transition probabilities, each
    # out-degree = 1; so vol(G) = n.
    vol_G = float(n)
    
    mfpt_vla = vol_G * 1.0 / d_v
    set_self_transition_zero(mfpt_vla)
    outfilename = codename + "/MFPT_VLA.dat"
    np.savetxt(outfilename, mfpt_vla)

    ct_vla = vol_G * (1.0 / d_u + 1.0 / d_v)
    set_self_transition_zero(ct_vla)
    outfilename = codename + "/CT_VLA.dat"
    np.savetxt(outfilename, ct_vla)

    R = mfpt / vol_G
    S = R - d_u - d_v
    # t is the adjacency matrix
    t_diag = np.sum(t * np.eye(n)) * ones
    t_ii = t_diag
    t_jj = t_diag.T
    u = 2 * t / (d_u * d_v) - t_ii / d_u**2  - t_jj / d_v**2
    C_amp = S + u
    set_self_transition_zero(C_amp)
    outfilename = codename + "/C_amp.dat"
    np.savetxt(outfilename, C_amp)
    

def Laplacian_matrix(A):
    """Copied from
    http://networkx.lanl.gov/_modules/networkx/linalg/laplacianmatrix.html. Eg

>>> A = np.array([[0, 1, 0, 0, 1, 0],
                  [1, 0, 1, 0, 1, 0],
                  [0, 1, 0, 1, 0, 0],
                  [0, 0, 1, 0, 1, 1], 
                  [1, 1, 0, 1, 0, 0],
                  [0, 0, 0, 1, 0, 0]])
>>> Laplacian_matrix(A)
array([[ 2., -1.,  0.,  0., -1.,  0.],
       [-1.,  3., -1.,  0., -1.,  0.],
       [ 0., -1.,  2., -1.,  0.,  0.],
       [ 0.,  0., -1.,  3., -1., -1.],
       [-1., -1.,  0., -1.,  3.,  0.],
       [ 0.,  0.,  0., -1.,  0.,  1.]])
"""
    I=np.identity(A.shape[0])
    D=I*np.sum(A,axis=1)
    L=D-A
    return L

def Yen_correction(m):
    """From Yen et al,
    http://link.springer.com/content/pdf/10.1007%2F978-3-540-71701-0_117.pdf,
    referred to by Von Luxburg et al."""
    L = np.linalg.pinv(Laplacian_matrix(m))
    sigma = np.std(L) # a normalising factor
    a = 7.0 # The value used by Yen et al, determined experimentally
    K_Yen = 1.0 / (1 + a * np.exp(-L / sigma))
    return K_Yen

def Brand_correction(m):
    """Placeholder. From Von Luxburg et al."""
    # assumes mfpt has been calculated and written out already
    # mfpt = np.genfromtxt(codename + "/MFPT.dat")
    # R = mfpt / vol_G
    n = m.shape[0]
    sum_all = np.sum(R)
    sum_ik_kj = np.zeros_like(R)

    # this is far too slow -- need to reformulate in matrix terms
    for i in range(n):
        for j in range(n):
            sum_ik_kj = sum(R[i][k] + R[k][j] for k in range(n))
    K = 1/2.0 * (-R + 1./n * (sum_ik + sum_kj) - 1.0/(n*n) * sum_all)
    K_B = K / np.sqrt(Kii * Kjj) # (need to express KiiKjj as a matrix)
    return K_B
    
def read_and_get_dtp_mfpt_sp_steps(codename):

    if os.path.exists(codename + "/TP_nonnormalised.dat"):
        t = read_transition_matrix(codename + "/TP_nonnormalised.dat")
        # it's a non-normalised matrix, possibly representing a
        # uniformly sampled sub-graph, a hill-climb-sampled graph, or
        # similar.
        t = normalise_by_row(t)
        outfilename = codename + "/TP.dat"
        np.savetxt(outfilename, t)
    else:
        t = read_transition_matrix(codename + "/TP.dat")
        check_row_sums(t)

    # This gets D_TP, which is just the transition probability inverted
    d = get_dtp(t)
    outfilename = codename + "/D_TP.dat"
    np.savetxt(outfilename, d)
    
    # This gets the mean first passage time, ie the expected length of
    # a random walk.
    f = get_mfpt(t)
    outfilename = codename + "/MFPT.dat"
    np.savetxt(outfilename, f)

    # This gets the cost of the shortest path between pairs. The cost
    # of an edge is the negative log of its probability.
    h = floyd_warshall_probabilities(t)
    outfilename = codename + "/SP.dat"
    np.savetxt(outfilename, h)

    # this gets the minimum number of steps required to go between
    # pairs, disregarding probabilities. Only interesting if some
    # edges are absent (ie edge probability is zero).
    p = floyd_warshall_nsteps(t)
    outfilename = codename + "/STEPS.dat"
    np.savetxt(outfilename, p)

def hamming_distance(x, y):
    return np.sum(x != y)
    
def generate_ga_tm(codename, pmut=None):
    """For a bitstring (genetic algorithm) representation of a given
    length, generate a transition matrix with the mutation probability
    pmut. Also generate the Hamming distances. If pmut=None (default),
    exactly one bitflip is performed per individual, rather than using
    a per-gene mutation probability."""
    
    length = int(codename.strip("/").split("_")[2])
    tm = np.zeros((2**length, 2**length))
    hm = np.zeros((2**length, 2**length))
    for i, indi in enumerate(itertools.product(*[(0, 1) for x in range(length)])):
        indi = np.array(indi, dtype='bool')
        for j, indj in enumerate(itertools.product(*[(0, 1) for y in range(length)])):
            indj = np.array(indj, dtype='bool')
            h = hamming_distance(indi, indj)
            hm[i][j] = h
            if pmut is None:
                if h == 1:
                    tm[i][j] = 1.0 / length # there are length inds at hamming distance 1
                    # else leave it at zero
            else:
                tm[i][j] = (pmut ** h) * ((1.0 - pmut) ** (length - h))
    outfilename = codename + "/TP.dat"
    np.savetxt(outfilename, tm)
    outfilename = codename + "/Hamming.dat"
    np.savetxt(outfilename, hm)
    
if __name__ == "__main__":
    cmd = sys.argv[1]
    codename = sys.argv[2]

    if cmd == "writeSymmetricRemoteness":
        write_symmetric_remoteness(codename)
    else:
        if "depth" in codename:
            # Matrices have already been generated by Java code.
            pass
        elif "per_ind" in codename:
            generate_ga_tm(codename)
        else:
            generate_ga_tm(codename, 0.1)
        read_and_get_dtp_mfpt_sp_steps(codename)
